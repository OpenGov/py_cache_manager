import pickle
import cPickle
import shutil
import os
import psutil
from collections import defaultdict

def dict_loader(*arg, **kwargs):
    return {}

def disabled_saver(*arg, **kwargs):
    pass
disabled_deleter = disabled_saver

def generate_pickle_path(cache_dir, cache_name):
    return os.path.join(cache_dir, cache_name + '.pkl')

def pickle_loader(cache_dir, cache_name):
    '''
    Default loader for any cache, this function loads from a pickle file based on cache name.
    '''
    try:
        with open(generate_pickle_path(cache_dir, cache_name), 'rb') as pkl_file:
            try:
                contents = cPickle.load(pkl_file)
            except:
                contents = pickle.load(pkl_file)
    except (IOError, EOFError, AttributeError):
        return None
    return contents

def ensure_directory(dirname):
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError:
            if not os.path.isdir(dirname):
                raise IOError('Unable to build cache directory: {}'.format(dirname))

def _exclude_zombie_procs(procs):
    alive_procs = []
    for p in procs:
        try:
            if p.status() != psutil.STATUS_ZOMBIE:
                alive_procs.append(p)
        except:
            pass
    return alive_procs

def fork_manage(cache_name, timeout, worker_preprocess, worker_action, terminated_cleanup=None):
    children = _exclude_zombie_procs([proc for proc in psutil.Process().children(recursive=False) 
            if proc.pid in fork_manage.seen_pids[cache_name]])
    cache_pids = set(child.pid for child in children)
    terminated_pids = fork_manage.seen_pids[cache_name] - cache_pids
    for pid in terminated_pids:
        # Slay the undead... they mingle with the living...
        try: os.waitpid(pid, 0)
        except OSError: pass
        if terminated_cleanup:
            terminated_cleanup(pid)
    fork_manage.seen_pids[cache_name] = cache_pids

    try:
        fork_pid = os.fork()
    except (AttributeError, OSError):
        # Windows has no fork... TODO make windows async saver
        worker_preprocess()
        worker_action()
        return

    if fork_pid != 0:
        cache_pids.add(fork_pid)
    else:
        try:
            pid = os.getpid()
            worker_preprocess(pid)

            # Refilter our zombies
            children = _exclude_zombie_procs(children)
            if children:
                gone, alive_and_undead = psutil.wait_procs(children, timeout=timeout)
                # Avoid killing processes that have since died
                alive = _exclude_zombie_procs(alive_and_undead)
                for p in alive:
                    print "Warning killing previous save for '{}' cache on pid {}".format(cache_name, p.pid)
                    p.kill()
            worker_action(pid)
        except Exception, e:
            print "Warning: ignored error in '{}' cache saver - {}".format(cache_name, repr(e))
        finally:
            # Exit aggresively -- we don't want cleanup to occur
            os._exit(0)
fork_manage.seen_pids=defaultdict(set)

def pickle_saver(cache_dir, cache_name, contents, async=False, async_timeout=60):
    try:
        ensure_directory(cache_dir)
        cache_path = generate_pickle_path(cache_dir, cache_name)

        def generate_temp_pickle(pid=None):
            temp_ext = '.tmp' + str(pid) if pid is not None else ''
            with open(cache_path + temp_ext, 'wb') as pkl_file:
                try:
                    cPickle.dump(contents, pkl_file)
                except:
                    pickle.dump(contents, pkl_file)

        def move_temp_pickle(pid=None):
            temp_ext = '.tmp' + str(pid) if pid is not None else ''
            shutil.move(cache_path + temp_ext, cache_path)

        def temp_pickle_cleanup(pid=None):
            temp_ext = '.tmp' + str(pid) if pid is not None else ''
            try: os.remove(cache_path + temp_ext)
            except OSError: pass

        if async:
            fork_manage(cache_name, async_timeout, generate_temp_pickle, move_temp_pickle, temp_pickle_cleanup)
        else:
            generate_temp_pickle()
            move_temp_pickle()
    except (IOError, EOFError):
        # TODO log real exception
        raise IOError('Unable to save {} cache'.format(cache_name))

def pickle_deleter(cache_dir, cache_name):
    try:
        os.remove(generate_pickle_path(cache_dir, cache_name))
    except OSError:
        pass

import pickle
from six.moves import cPickle
from six import iteritems
import shutil
import os
import sys
import psutil
import csv
import traceback

from .utils import random_name

if sys.version_info[0] == 2:
    text_read_mode = 'rU'
    text_write_mode = 'wb'
else:
    text_read_mode = 'r'
    text_write_mode = 'w'

def dict_loader(*arg, **kwargs):
    return {}

def disabled_saver(*arg, **kwargs):
    pass
disabled_deleter = disabled_saver

def generate_path(cache_dir, cache_name, extension):
    return os.path.join(cache_dir, '.'.join([cache_name, extension]))

def generate_pickle_path(cache_dir, cache_name):
    return generate_path(cache_dir, cache_name, 'pkl')

def generate_csv_path(cache_dir, cache_name):
    return generate_path(cache_dir, cache_name, 'csv')

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

def _tmp_pid_extensions(pid=None):
    extensions = ['tmp', random_name()]
    if pid:
        extensions.append(str(pid))
    return extensions

def fork_content_save(cache_name, contents, presaver, saver, cleaner, timeout, seen_pids):
    children = _exclude_zombie_procs([proc for proc in psutil.Process().children(recursive=False)
            if proc.pid in seen_pids[cache_name]])
    cache_pids = set(child.pid for child in children)
    terminated_pids = seen_pids[cache_name] - cache_pids
    for pid in terminated_pids:
        # Slay the undead... they mingle with the living...
        try: os.waitpid(pid, 0)
        except OSError: pass
        if cleaner:
            cleaner(cache_name, _tmp_pid_extensions(pid))
    seen_pids[cache_name] = cache_pids

    exts = _tmp_pid_extensions()
    try:
        fork_pid = os.fork()
    except OSError as e:
        print(("Warning, saving {} synchronously: {} ".format(cache_name, repr(e)) +
            "-- you're out of memory or you might be out of shared memory (check kernel.shmmax)"))
        if presaver:
            presaver(cache_name, contents, exts)
        saver(cache_name, contents, exts)
        return
    except AttributeError:
        # Windows has no fork... TODO make windows async saver
        if presaver:
            presaver(cache_name, contents, exts)
        saver(cache_name, contents, exts)
        return

    if fork_pid != 0:
        cache_pids.add(fork_pid)
    else:
        try:
            pid = os.getpid()
            pid_exts = _tmp_pid_extensions(pid)
        except Exception as e:
            print("Warning: ignored error in '{}' cache saver - {}".format(cache_name, repr(e)))
        try:
            if presaver:
                presaver(cache_name, contents, pid_exts)

            # Refilter our zombies
            children = _exclude_zombie_procs(children)
            if children:
                gone, alive_and_undead = psutil.wait_procs(children, timeout=timeout)
                # Avoid killing processes that have since died
                alive = _exclude_zombie_procs(alive_and_undead)
                for p in alive:
                    print("Warning killing previous save for '{}' cache on pid {}".format(cache_name, p.pid))
                    p.kill()
            saver(cache_name, contents, pid_exts)
        except Exception as e:
            if cleaner:
                try: cleaner(cache_name, contents, pid_exts)
                except: pass
            print("Warning: ignored error in '{}' cache saver - {}".format(cache_name, repr(e)))
        finally:
            # Exit aggresively -- we don't want cleanup to occur
            os._exit(0)

def pickle_saver(cache_dir, cache_name, contents):
    tmp_exts = ['tmp', random_name()]
    try:
        try:
            pickle_pre_saver(cache_dir, cache_name, contents, tmp_exts)
            pickle_mover(cache_dir, cache_name, contents, tmp_exts)
        except (IOError, EOFError):
            traceback.print_exc()
            raise IOError('Unable to save {} cache'.format(cache_name))
    except:
        try: pickle_cleaner(cache_dir, cache_name, tmp_exts)
        except: pass
        raise

def pickle_pre_saver(cache_dir, cache_name, contents, extensions):
    ensure_directory(cache_dir)
    cache_path = generate_pickle_path(cache_dir, cache_name)
    with open('.'.join([cache_path] + extensions), 'wb') as pkl_file:
        try:
            cPickle.dump(contents, pkl_file)
        except:
            # We do this because older cPickle was incorrectly raising exceptions
            pickle.dump(contents, pkl_file)

def pickle_mover(cache_dir, cache_name, contents, extensions):
    cache_path = generate_pickle_path(cache_dir, cache_name)
    shutil.move('.'.join([cache_path] + extensions), cache_path)

def pickle_cleaner(cache_dir, cache_name, extensions):
    cache_path = generate_pickle_path(cache_dir, cache_name)
    try: os.remove('.'.join([cache_path] + extensions))
    except OSError: pass

def pickle_deleter(cache_dir, cache_name):
    try:
        os.remove(generate_pickle_path(cache_dir, cache_name))
    except OSError:
        pass

def pickle_loader(cache_dir, cache_name):
    '''
    Default loader for any cache, this function loads from a pickle file based on cache name.
    '''
    contents = None
    try:
        with open(generate_pickle_path(cache_dir, cache_name), 'rb') as pkl_file:
            try:
                contents = cPickle.load(pkl_file)
            except:
                exc_info = sys.exc_info()
                try: contents = pickle.load(pkl_file)
                except (IndexError, AttributeError): pass
                if contents is None:
                    raise exc_info[1].with_traceback(exc_info[2])
    except (IOError, EOFError):
        return None
    return contents

def csv_saver(cache_dir, cache_name, contents, row_builder=None):
    tmp_exts = ['tmp', random_name()]
    try:
        try:
            csv_pre_saver(cache_dir, cache_name, contents, tmp_exts, row_builder)
            csv_mover(cache_dir, cache_name, contents, tmp_exts)
        except (IOError, EOFError):
            traceback.print_exc()
            raise IOError('Unable to save {} cache'.format(cache_name))
    except:
        try: csv_cleaner(cache_dir, cache_name, tmp_exts)
        except: pass
        raise

def csv_pre_saver(cache_dir, cache_name, contents, extensions, row_builder=None):
    ensure_directory(cache_dir)
    cache_path = generate_csv_path(cache_dir, cache_name)
    with open('.'.join([cache_path] + extensions), text_write_mode) as csv_file:
        writer = csv.writer(csv_file, dialect='excel', quoting=csv.QUOTE_MINIMAL)
        for key, value in iteritems(contents):
            writer.writerow(row_builder(key, value) if row_builder else [key, value])

def csv_mover(cache_dir, cache_name, contents, extensions):
    cache_path = generate_csv_path(cache_dir, cache_name)
    shutil.move('.'.join([cache_path] + extensions), cache_path)

def csv_cleaner(cache_dir, cache_name, extensions):
    cache_path = generate_csv_path(cache_dir, cache_name)
    try: os.remove('.'.join([cache_path] + extensions))
    except OSError: pass

def csv_loader(cache_dir, cache_name, row_reader=None):
    contents = {}
    try:
        with open(generate_csv_path(cache_dir, cache_name), text_read_mode) as csv_file:
            reader = csv.reader(csv_file, dialect='excel', quoting=csv.QUOTE_MINIMAL)
            for row in reader:
                if row:
                    key, val = row_reader(row) if row_reader else (row[0], row[1])
                    contents[key] = val
    except (IOError, EOFError):
        return None
    return contents

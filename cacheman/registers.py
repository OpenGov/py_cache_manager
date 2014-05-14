import pickle
import cPickle
import shutil
import os
import psutil

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

def fork_manage(worker_preprocess, worker_action):
    children = psutil.Process(os.getpid()).children(recursive=False)

    try:
        fork_pid = os.fork()
    except (AttributeError, OSError):
        # Windows has no fork... TODO make windows async saver
        worker_preprocess()
        worker_action()
        return

    if fork_pid == 0:
        try:
            pid = os.getpid()
            worker_preprocess(pid)

            for child in children:
                try: child.wait(timeout=60)
                except OSError: pass # Continue if process disappears
            worker_action(pid)
        except Exception, e:
            print "Warning ignored error in saver {}".format(repr(e))
        finally:
            # Exit aggresively -- we don't want cleanup to occur
            os._exit(0)

def pickle_saver(cache_dir, cache_name, contents, async=False):
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

        if async:
            fork_manage(generate_temp_pickle, move_temp_pickle)
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

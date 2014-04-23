import pickle
import shutil
import os

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
                raise IOError('Unable to build cache directories for %s cache' % cache_name)

def pickle_saver(cache_dir, cache_name, contents):
    try:
        ensure_directory(cache_dir)
        cache_path = generate_pickle_path(cache_dir, cache_name)
        with open(cache_path + '.tmp', 'wb') as pkl_file:
            pickle.dump(contents, pkl_file)
        shutil.move(cache_path + '.tmp', cache_path)
    except (IOError, EOFError):
        # TODO log real exception
        raise IOError('Unable to save %s cache' % cache_name)

def pickle_deleter(cache_dir, cache_name):
    try:
        os.remove(generate_pickle_path(cache_dir, cache_name))
    except OSError:
        pass

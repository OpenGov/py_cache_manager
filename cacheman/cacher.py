import os
import pickle
import tempfile
from collections import defaultdict

DEFAULT_CACHEMAN = 'general_cacher'

def get_cache_manager(manager_name=None):
    if manager_name is None:
        # Don't grab this from default args in case someone changes DEFAULT_CACHEMAN
        manager_name = DEFAULT_CACHEMAN
    if manager_name not in get_cache_manager.managers:
        # Need name argument, so can't use defaultdict easily
        get_cache_manager.managers[manager_name] = CacheManager(manager_name)
    return get_cache_manager.managers[manager_name]
get_cache_manager.managers = {}

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
        with open(generate_pickle_path(cache_dir, cache_name), 'wb') as pkl_file:
            pickle.dump(contents, pkl_file)
    except (IOError, EOFError):
        # TODO log real exception
        raise IOError('Unable to save %s cache' % cache_name)

def pickle_deleter(cache_dir, cache_name):
    try:
        os.remove(generate_pickle_path(cache_dir, cache_name))
    except OSError:
        pass

def mem_loader(cache_name=None):
    return {}

def mem_saver(cache_name=None, contents=None):
    pass
disabled_deleter = mem_saver

class CacheManager():
    def manager_pickle_loader(self, cache_name):
        return pickle_loader(self.cache_dir, cache_name)

    def manager_pickle_saver(self, cache_name, contents):
        return pickle_saver(self.cache_dir, cache_name, contents)

    def manager_pickle_deleter(self, cache_name):
        return pickle_deleter(self.cache_dir, cache_name)

    def __init__(self, manager_name):
        self.name = manager_name
        self.cache_dir = os.path.join(tempfile.gettempdir(), self.name)
        self.cache_by_name = {}
        self.cache_loaders = defaultdict(lambda: self.manager_pickle_loader)
        self.cache_savers = defaultdict(lambda: self.manager_pickle_saver)
        self.cache_builders = defaultdict(lambda: mem_loader)
        self.cache_pre_processor = {}
        self.cache_post_processor = {}
        self.cache_validator = {}
        self.cache_deleter = defaultdict(lambda: self.manager_pickle_deleter)
        self.cache_rebuilds = {}
        self.cache_dependents = defaultdict(set)
        self.registered = set()
        self.cache_trackers = [self.cache_by_name, self.cache_loaders, self.cache_savers,
                self.cache_builders, self.cache_pre_processor, self.cache_post_processor,
                self.cache_validator, self.cache_deleter, self.cache_rebuilds, self.cache_dependents]

    def __del__(self):
        pass # Python cleanup will kill this before it finishes destroy caches...
        # try:
        #     self.save_all_cache_contents()
        # except TypeError:
        #     pass # Skip when modules have been unloaded underneath the del call

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.save_all_cache_contents()

    def _load_cache(self, cache_name, loader, post_process=None, validator=None):
        cache = loader(cache_name)
        if cache is None or (validator and not validator(cache)):
            return None

        if post_process:
            cache = post_process(cache)
        return cache

    def _save_cache(self, cache_name, saver, contents, pre_process=None):
        if pre_process:
            contents = pre_process(contents)
        return saver(cache_name, contents) or contents

    def _build_cache(self, cache_name, builder, saver, pre_process=None, post_process=None):
        cache = builder()
        self._save_cache(cache_name, saver, cache, pre_process)

        if cache_name in self.cache_rebuilds:
            # Clear state the rebuild flag as we've just built the cache
            del self.cache_rebuilds[cache_name]

        if post_process:
            cache = post_process(cache)

        for depedent in self._dependents(cache_name):
            # Dependent caches are now out of date
            self.invalidate_cache_and_saved_contents(depedent)

        return cache

    def _load_or_build_cache(self, cache_name, loader, builder, saver, pre_process=None,
                             post_process=None, validator=None):
        cache = self._load_cache(cache_name, loader, post_process, validator)
        loaded = cache is not None
        if not loaded:
            cache = self._build_cache(cache_name, builder, saver, pre_process, post_process)
        return loaded, cache

    def set_cache_directory(self, dirname):
        self.cache_dir = os.path.abspath(dirname)
        return self.cache_dir

    def get_cache_directory(self):
        return self.cache_dir

    def retrieve_cache(self, cache_name, clear_cache=False):
        '''
        Loads or builds a cache using any registered post_process, custom_builder, and validator hooks.
        If a cache has already been generated it will return the pre-loaded cache content.
        '''
        if clear_cache:
            self.invalidate_cache(cache_name)
        rebuild = bool(self.cache_rebuilds.get(cache_name))
        cache = self.cache_by_name.get(cache_name)

        if cache is None or rebuild:
            if rebuild:
                cache = self._build_cache(cache_name,
                    builder=self.cache_builders[cache_name],
                    saver=self.cache_savers[cache_name],
                    pre_process=self.cache_pre_processor.get(cache_name),
                    post_process=self.cache_post_processor.get(cache_name))
            else:
                loaded, cache = self._load_or_build_cache(cache_name,
                    loader=self.cache_loaders[cache_name],
                    builder=self.cache_builders[cache_name],
                    saver=self.cache_savers[cache_name],
                    pre_process=self.cache_pre_processor.get(cache_name),
                    post_process=self.cache_post_processor.get(cache_name),
                    validator=self.cache_validator.get(cache_name))

        self.cache_by_name[cache_name] = cache
        # Incase the cache was all defaults and never explicitly registered
        self.registered.add(cache_name)
        return cache

    def cache_built(self, cache_name):
        return self.cache_by_name.get(cache_name) is not None

    def cache_registered(self, cache_name):
        return cache_name in self.registered

    def register_cache(self, cache_name, contents=None, persistent=True):
        self.registered.add(cache_name)
        if contents is not None:
            self.cache_by_name[cache_name] = contents
        if not persistent:
            # Replace default pickle loader/saver/deleter
            self.register_loader(cache_name, mem_loader)
            self.register_saver(cache_name, mem_saver)
            self.register_deleter(cache_name, disabled_deleter)
        return contents

    def register_loader(self, cache_name, loader):
        self.registered.add(cache_name)
        self.cache_loaders[cache_name] = loader

    def register_builder(self, cache_name, builder):
        self.registered.add(cache_name)
        self.cache_builders[cache_name] = builder

    def register_saver(self, cache_name, saver):
        self.registered.add(cache_name)
        self.cache_savers[cache_name] = saver

    def register_deleter(self, cache_name, deleter):
        self.registered.add(cache_name)
        self.cache_deleter[cache_name] = deleter

    def register_post_processor(self, cache_name, post_process):
        self.registered.add(cache_name)
        self.cache_post_processor[cache_name] = post_process

    def register_pre_processor(self, cache_name, pre_process):
        self.registered.add(cache_name)
        self.cache_pre_processor[cache_name] = pre_process

    def register_validator(self, cache_name, validator):
        self.registered.add(cache_name)
        self.cache_validator[cache_name] = validator

    def register_dependent_cache(self, cache_name, dependent_cache):
        self.registered.add(cache_name)
        self.registered.add(dependent_cache)
        self.cache_dependents[cache_name].add(dependent_cache)

    def _dependents(self, cache_name, apply_to_dependents=True, seen_dependents=None):
        if apply_to_dependents:
            for dependent in self.cache_dependents[cache_name]:
                if seen_dependents is None or dependent not in seen_dependents:
                    yield dependent

    def _add_seen_cache(self, cache_name, seen_caches):
        if seen_caches is None:
            seen_caches = set()
        seen_caches.add(cache_name)
        return seen_caches

    def deregister_cache(self, cache_name, apply_to_dependents=False, seen_caches=None):
        seen_caches = self._add_seen_cache(cache_name, seen_caches)

        # Recurse BEFORE removing registration or we won't iterate over decendents
        for depedent in self._dependents(cache_name, apply_to_dependents, seen_caches):
            self.deregister_cache(depedent, apply_to_dependents, seen_caches)

        self.registered.remove(cache_name)
        for cache_tracker in self.cache_trackers:
            if cache_name in cache_tracker:
                del cache_tracker[cache_name]

    def deregister_all_caches(self):
        for cache_tracker in self.cache_trackers:
            for cache_name in cache_tracker.keys():
                if cache_name in self.registered:
                    self.registered.remove(cache_name)
                del cache_tracker[cache_name]

    def save_cache_contents(self, cache_name, apply_to_dependents=False, seen_caches=None):
        seen_caches = self._add_seen_cache(cache_name, seen_caches)
        cache = self.cache_by_name.get(cache_name)
        self._save_cache(cache_name,
            saver=self.cache_savers[cache_name],
            pre_process=self.cache_pre_processor.get(cache_name),
            contents=cache)

        for depedent in self._dependents(cache_name, apply_to_dependents, seen_caches):
            self.save_cache_contents(depedent, apply_to_dependents, seen_caches)

    def save_all_cache_contents(self):
        for cache_name in self.cache_by_name:
            self.save_cache_contents(cache_name)

    def delete_saved_content(self, cache_name, apply_to_dependents=True, seen_caches=None):
        '''
        Does NOT delete memory cache -- use invalidate_and_delete_all_saved_contents to delete both
        '''
        deleter = self.cache_deleter[cache_name]
        deleter(cache_name)

        for depedent in self._dependents(cache_name, apply_to_dependents, seen_caches):
            self.delete_saved_content(depedent, apply_to_dependents, seen_caches)

    def invalidate_cache(self, cache_name, apply_to_dependents=True, seen_caches=None):
        seen_caches = self._add_seen_cache(cache_name, seen_caches)
        if cache_name in self.cache_by_name:
            del self.cache_by_name[cache_name]
        for depedent in self._dependents(cache_name, apply_to_dependents, seen_caches):
            self.invalidate_cache(depedent, apply_to_dependents, seen_caches)

    def invalidate_cache_and_saved_contents(self, cache_name, apply_to_dependents=True, seen_caches=None):
        seen_caches = self._add_seen_cache(cache_name, seen_caches)
        self.cache_rebuilds[cache_name] = True

        self.invalidate_cache(cache_name, False)
        self.delete_saved_content(cache_name)

        for depedent in self._dependents(cache_name, apply_to_dependents, seen_caches):
            self.invalidate_cache_and_saved_contents(depedent, apply_to_dependents, seen_caches)

    def invalidate_and_delete_all_saved_contents(self):
        for cache_name in self.registered:
            self.invalidate_cache_and_saved_contents(cache_name)

    def reload_cache(self, cache_name, apply_to_dependents=False):
        return self.retrieve_cache(cache_name, True)

    def reload_all_caches(self):
        for cache_name in self.registered:
            self.reload_cache(cache_name)

    def rebuild_cache(self, cache_name, apply_to_dependents=False):
        self.invalidate_cache_and_saved_contents(cache_name, apply_to_dependents)
        return self.retrieve_cache(cache_name)

    def rebuild_all_caches(self):
        for cache_name in self.registered:
            self.rebuild_cache(cache_name)

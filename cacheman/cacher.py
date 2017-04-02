import os
import tempfile
from collections import defaultdict

from .cachewrap import CacheWrap, NonPersistentCache, PersistentCache
from .autosync import AutoSyncCache

DEFAULT_CACHEMAN = 'general_cacher'

def get_cache_manager(manager_name=None, base_cache_directory=None):
    if manager_name is None:
        # Don't grab this from default args in case someone changes DEFAULT_CACHEMAN
        manager_name = DEFAULT_CACHEMAN
    if manager_name not in _managers:
        # Need name argument, so can't use defaultdict easily
        _managers[manager_name] = CacheManager(manager_name, base_cache_directory)
    return _managers[manager_name]
_managers = {} # Labeled with leading underscore to trigger del before module cleanup

class CacheManager():
    def __init__(self, manager_name, base_cache_directory=None):
        self.name = manager_name
        self.cache_directory = os.path.join(base_cache_directory or tempfile.gettempdir(), self.name)
        self.cache_by_name = {}
        self.async_pid_cache = defaultdict(set) # Used for async cache tracking

    def __del__(self):
        self.save_all_cache_contents()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.save_all_cache_contents()

    def retrieve_cache(self, cache_name):
        '''
        Loads or builds a cache using any registered post_process, custom_builder, and validator hooks.
        If a cache has already been generated it will return the pre-loaded cache content.
        '''
        cache = self.cache_by_name.get(cache_name)
        if cache is None:
            return self.register_cache(cache_name)
        return cache

    def retrieve_raise(self, cache_name):
        cache = self.cache_by_name.get(cache_name)
        if cache is None:
            raise KeyError("No cache found with name {}".format(cache_name))
        return cache

    def register_cache(self, cache_name, contents=None):
        return self.register_custom_cache(cache_name, contents, persistent=True, autosync=True, nowrapper=False)

    def register_custom_cache(self, cache_name, contents=None, persistent=True, autosync=True, nowrapper=False, **kwargs):
        if nowrapper or isinstance(contents, CacheWrap):
            cache = contents
        elif not persistent:
            # Replace default pickle loader/saver/deleter
            cache = NonPersistentCache(cache_name, cache_manager=self, contents=contents, **kwargs)
        elif autosync:
            cache = AutoSyncCache(cache_name, cache_manager=self, contents=contents, **kwargs)
        else:
            cache = PersistentCache(cache_name, cache_manager=self, contents=contents, **kwargs)

        self.cache_by_name[cache_name] = cache
        return self.retrieve_cache(cache_name)

    def cache_registered(self, cache_name):
        return cache_name in self.cache_by_name

    def register_loader(self, cache_name, loader):
        cache = self.retrieve_cache(cache_name)
        cache.loader = loader
        return cache

    def register_builder(self, cache_name, builder):
        cache = self.retrieve_cache(cache_name)
        cache.builder = builder
        return cache

    def register_saver(self, cache_name, saver):
        cache = self.retrieve_cache(cache_name)
        cache.saver = saver
        return cache

    def register_deleter(self, cache_name, deleter):
        cache = self.retrieve_cache(cache_name)
        cache.deleter = deleter
        return cache

    def register_post_processor(self, cache_name, post_processor):
        cache = self.retrieve_cache(cache_name)
        cache.post_processor = post_processor
        return cache

    def register_pre_processor(self, cache_name, pre_processor):
        cache = self.retrieve_cache(cache_name)
        cache.pre_processor = pre_processor
        return cache

    def register_validator(self, cache_name, validator):
        cache = self.retrieve_cache(cache_name)
        cache.validator = validator
        return cache

    def register_dependent_cache(self, cache_name, dependent_cache):
        cache = self.retrieve_cache(cache_name)
        cache.add_dependent(dependent_cache)
        return cache

    def deregister_cache(self, cache_name, apply_to_dependents=False):
        if not self.cache_registered(cache_name):
            return
        cache = self.retrieve_cache(cache_name)
        cache.save(False)

        if apply_to_dependents:
            for dependent in cache._retrieve_dependent_caches():
                self.deregister_cache(dependent.name, apply_to_dependents)
        del self.cache_by_name[cache_name]

    def deregister_all_caches(self):
        for cache_name in list(self.cache_by_name.keys()):
            self.deregister_cache(cache_name, False)

    def save_cache_contents(self, cache_name, apply_to_dependents=False):
        cache = self.retrieve_cache(cache_name)
        cache.save(apply_to_dependents)
        return cache

    def save_all_cache_contents(self):
        for cache_name in self.cache_by_name:
            self.save_cache_contents(cache_name, False)

    def delete_saved_cache_content(self, cache_name, apply_to_dependents=True):
        '''
        Does NOT delete memory cache -- use invalidate_and_rebuild_cache to delete both
        '''
        cache = self.retrieve_cache(cache_name)
        cache.delete_saved_content(apply_to_dependents)
        return cache

    def delete_all_saved_cache_contents(self):
        for cache_name in self.cache_by_name:
            self.delete_saved_cache_content(cache_name, False)

    def invalidate_cache(self, cache_name, apply_to_dependents=True):
        cache = self.retrieve_cache(cache_name)
        cache.invalidate(apply_to_dependents)
        return cache

    def invalidate_and_rebuild_cache(self, cache_name, apply_to_dependents=True):
        cache = self.retrieve_cache(cache_name)
        cache.invalidate_and_rebuild(apply_to_dependents)
        return cache

    def invalidate_and_rebuild_all_caches(self):
        for cache_name in self.cache_by_name:
            self.invalidate_and_rebuild_cache(cache_name, False)

    def reload_cache(self, cache_name, apply_to_dependents=False):
        cache = self.retrieve_cache(cache_name)
        cache.load(apply_to_dependents)
        return cache

    def reload_all_caches(self):
        for cache_name in self.cache_by_name:
            self.reload_cache(cache_name, False)

    def reload_or_rebuild_cache(self, cache_name, apply_to_dependents=False):
        cache = self.retrieve_cache(cache_name)
        cache.load_or_build(apply_to_dependents)
        return cache

    def reload_or_rebuild_all_caches(self):
        for cache_name in self.cache_by_name:
            self.reload_or_rebuild_cache(cache_name, False)

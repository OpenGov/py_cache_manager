from collections import MutableMapping
from registers import *
import cacher

class CacheWrap(MutableMapping, object):
    '''
    A class designed to immitate the contents it holds with a capability to reload,
    rebuild, destroy, or save it's contents without disrupting any references to
    the cache object.
    '''
    
    CALLBACK_NAMES = ['loader', 'async_presaver', 'async_saver', 'async_cleaner', 'saver', 'builder', 'deleter',
                      'pre_processor', 'post_processor', 'validator']

    def __init__(self, cache_name, contents=None, dependents=None, cache_manager=None,
                 async=False, async_timeout=60, save_on_blank_cache=True, **kwargs):
        if cache_manager:
            self.manager = cache_manager
        else:
            self.manager = cacher.get_cache_manager()
        self.contents = contents
        self.name = cache_name
        self.dependents = set([self._convert_dependent_to_name(d) for d in dependents] if dependents else [])
        self.async = async
        self.async_timeout = async_timeout
        self.save_on_blank = save_on_blank_cache

        for name in CacheWrap.CALLBACK_NAMES:
            setattr(self, name, kwargs[name] if name in kwargs else getattr(self, name, None))

        if not self.manager.cache_registered(self.name):
            self.manager.register_cache(self.name, contents=self)

        if self.contents is None:
            self.load_or_build()

    def __del__(self):
        if not hasattr(self, 'delete_triggered'):
            # Avoid infinite recursion if dependent objects trigger delete chains
            self.delete_triggered = True
            self.save()
            if self.name in self.manager.cache_by_name:
                del self.manager.cache_by_name[self.name]

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.save()

    def __getattr__(self, name):
        '''
        If a method or attribute is missing, use the content's attributes
        '''
        for getter in ['__getattribute__', '__getattr__']:
            if hasattr(self.contents, getter):
                try:
                    return getattr(self.contents, getter)(name)
                except AttributeError:
                    pass
        raise AttributeError("'{}' and '{}' objects have no attribute '{}'".format(self.__class__.__name__, self.contents.__class__.__name__, name))

    def _check_contents_present(self):
        if self.contents is None:
            raise AttributeError("No cache contents defined for '{}'".format(self.name))

    def __contains__(self, *args, **kwargs):
        if self.contents is None:
            return False
        return self.contents.__contains__(*args, **kwargs)

    def __getitem__(self, *args, **kwargs):
        self._check_contents_present()
        return self.contents.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        self._check_contents_present()
        return self.contents.__setitem__(*args, **kwargs)

    def __delitem__(self, *args, **kwargs):
        self._check_contents_present()
        return self.contents.__delitem__(*args, **kwargs)

    def __iter__(self):
        self._check_contents_present()
        return self.contents.__iter__()

    def __len__(self):
        self._check_contents_present()
        return self.contents.__len__()

    def __str__(self):
        return "{}<{}>".format(self.__class__.__name__, self.contents.__str__())

    def __repr__(self):
        return "{}<{}>".format(self.__class__.__name__, self.contents.__repr__())

    def _manager_pickle_loader(self, name):
        return pickle_loader(self.manager.cache_directory, self.name)

    def _manager_pickle_saver(self, name, contents):
        return pickle_saver(self.manager.cache_directory, name, contents)

    def _manager_pickle_async_presaver(self, name, contents, extensions):
        return pickle_pre_saver(self.manager.cache_directory, name, contents, extensions)

    def _manager_pickle_async_mover(self, name, contents, extensions):
        return pickle_mover(self.manager.cache_directory, name, contents, extensions)

    def _manager_pickle_async_cleaner(self, name, extensions):
        return pickle_cleaner(self.manager.cache_directory, name, extensions)

    def _manager_pickle_deleter(self, name):
        return pickle_deleter(self.manager.cache_directory, name)

    def _retrieve_dependent_caches(self, seen_dependents=None):
        for dependent in self.dependents:
            if seen_dependents is None or dependent not in seen_dependents:
                cache = self.manager.retrieve_cache(dependent)
                if cache is not None:
                    yield cache

    def _add_seen_cache(self, seen_caches):
        if seen_caches is None:
            seen_caches = set()
        seen_caches.add(self.name)
        return seen_caches

    def _convert_dependent_to_name(self, dependent):
        return dependent if isinstance(dependent, basestring) else dependent.name

    def _pre_process(self, contents):
        if self.pre_processor:
            proc_contents = self.pre_processor(contents)
            if proc_contents is not None:
                contents = proc_contents
        return contents

    def _post_process(self, contents):
        if self.post_processor:
            proc_contents = self.post_processor(contents)
            if proc_contents is not None:
                contents = proc_contents
        return contents

    def _build(self):
        if not self.builder:
            self.contents = self._post_process(dict_loader())
        else:
            self.contents = self._post_process(self.builder(self.name))
        self.save()

        return self.contents

    def _async_save(self, name, contents):
        fork_content_save(name, contents, self.async_presaver, self.async_saver, self.async_cleaner,
            self.async_timeout, self.manager.async_pid_cache)

    def load(self, apply_to_dependents=False, seen_caches=None):
        if seen_caches and self.name in seen_caches:
            return
        seen_caches = self._add_seen_cache(seen_caches)

        if apply_to_dependents:
            for dependent in self._retrieve_dependent_caches(seen_caches):
                dependent.load(apply_to_dependents, seen_caches)

        if self.loader:
            self.contents = self.loader(self.name)

            if self.contents is None or (self.validator and not self.validator(self.contents)):
                self.contents = None
            else:
                self.contents = self._post_process(self.contents)
        else:
            self.contents = None

        return self.contents

    def save(self, apply_to_dependents=False, seen_caches=None):
        if seen_caches and self.name in seen_caches:
            return
        seen_caches = self._add_seen_cache(seen_caches)

        if apply_to_dependents:
            for dependent in self._retrieve_dependent_caches(seen_caches):
                dependent.save(apply_to_dependents, seen_caches)

        contents = self._pre_process(self.contents)
        if not self.save_on_blank and not contents:
            return contents

        # Determine if we're doing an async save or not
        saver = self._async_save if self.async else self.saver
        return (saver and saver(self.name, contents)) or contents

    def invalidate(self, apply_to_dependents=True, seen_caches=None):
        return self.load(apply_to_dependents, seen_caches)

    def delete_saved_content(self, apply_to_dependents=True, seen_caches=None):
        '''
        Does NOT delete memory cache -- use invalidate_and_rebuild to delete both
        '''
        if seen_caches and self.name in seen_caches:
            return
        seen_caches = self._add_seen_cache(seen_caches)

        if apply_to_dependents:
            for dependent in self._retrieve_dependent_caches(seen_caches):
                dependent.delete_saved_content(apply_to_dependents, seen_caches)

        if self.deleter:
            self.deleter(self.name)

    def invalidate_and_rebuild(self, apply_to_dependents=True, seen_caches=None):
        if seen_caches and self.name in seen_caches:
            return
        seen_caches = self._add_seen_cache(seen_caches)

        self.invalidate(False)
        self.delete_saved_content(False)
        self._build()

        if apply_to_dependents:
            for dependent in self._retrieve_dependent_caches(seen_caches):
                dependent.invalidate_and_rebuild(apply_to_dependents, seen_caches)

    def load_or_build(self, apply_to_dependents=True, seen_caches=None):
        if seen_caches and self.name in seen_caches:
            return
        seen_caches = self._add_seen_cache(seen_caches)

        if apply_to_dependents:
            for dependent in self._retrieve_dependent_caches(seen_caches):
                dependent.load_or_build(apply_to_dependents, seen_caches)

        loaded = self.load() is not None
        if not loaded:
            self._build()

        return loaded, self.contents

    def add_dependent(self, dependent):
        self.dependents.add(dependent)

class NonPersistentCache(CacheWrap):
    '''
    Currently CacheWrap acts like a NonPersistentCache by default, but it might change
    in the future.
    '''
    def __init__(self, cache_name, **kwargs):
        CacheWrap.__init__(self, cache_name, **kwargs)

    def loader(self, *args, **kwargs):
        return {}

    def builder(self, *args, **kwargs):
        return {}

class PersistentCache(CacheWrap):
    '''
    A persistent cache which saves and loads from pickle files.
    '''
    def __init__(self, cache_name, **kwargs):
        CacheWrap.__init__(self, cache_name, **kwargs)

    def loader(self, name):
        return self._manager_pickle_loader(name)

    def saver(self, name, contents):
        return self._manager_pickle_saver(name, contents)

    def deleter(self, name):
        return self._manager_pickle_deleter(name)

    def async_presaver(self, name, contents, extensions):
        return self._manager_pickle_async_presaver(name, contents, extensions)

    def async_saver(self, name, contents, extensions):
        return self._manager_pickle_async_mover(name, contents, extensions)

    def async_cleaner(self, name, extensions):
        return self._manager_pickle_async_cleaner(name, extensions)

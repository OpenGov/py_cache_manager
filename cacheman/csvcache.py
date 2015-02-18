import os

from .registers import *
from .cachewrap import CacheWrap
from .autosync import AutoSyncCacheBase

class CSVCache(CacheWrap):
    def __init__(self, cache_name, row_builder=None, row_reader=None, **kwargs):
        self.row_builder = row_builder
        self.row_reader = row_reader
        CacheWrap.__init__(self, cache_name, **kwargs)

    def saver(self, name, contents):
        return csv_saver(self.manager.cache_directory, name, contents, self.row_builder)

    def loader(self, name):
        return csv_loader(self.manager.cache_directory, name, self.row_reader)

    def deleter(self, name):
        try:
            os.remove(generate_csv_path(self.manager.cache_directory, name))
        except OSError:
            pass

    def async_presaver(self, name, contents, extensions):
        return csv_pre_saver(self.manager.cache_directory, name, contents, extensions, self.row_builder)

    def async_saver(self, name, contents, extensions):
        return csv_mover(self.manager.cache_directory, name, contents, extensions)

    def async_cleaner(self, name, extensions):
        return csv_cleaner(self.manager.cache_directory, name, extensions)

class AutoSyncCSVCache(AutoSyncCacheBase, CSVCache):
    '''
    AutoSyncCSVCache defaults to a csv basis.
    '''
    def __init__(self, cache_name, **kwargs):
        AutoSyncCacheBase.__init__(self, CSVCache, cache_name, **kwargs)

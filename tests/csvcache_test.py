# This import fixes sys.path issues
import parentpath

import unittest
from faketime import FakeTime
from cacheman import autosync
from cacheman.csvcache import CSVCache, AutoSyncCSVCache
from common import CacheCommonAsserter
from datetime import datetime, timedelta

class CSVCacheTest(CacheCommonAsserter, unittest.TestCase):
    def setUp(self):
        CacheCommonAsserter.setUp(self)
        self.faketime = FakeTime()
        autosync.datetime = self.faketime

    def tearDown(self):
        CacheCommonAsserter.tearDown(self)
        autosync.datetime = datetime

    def build_fast_sync_cache(self, cache_name):
        return AutoSyncCSVCache(cache_name, cache_manager=self.manager, 
                time_checks=[autosync.TimeCount(1, 2), autosync.TimeCount(5, 10)], time_bucket_size=1)

    @classmethod
    def setUpClass(cls):
        CacheCommonAsserter.cleanup()

    def test_basic_csv_cache(self):
        cache_name = self.check_cache_gone('csvcache', csv_path=True)

        cache = CSVCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        cache.save()

        self.check_cache(cache_name, True, csv_path=True)
        cache.load() # Reload
        self.check_cache(cache_name, True, csv_path=True)
        self.assertEqual(cache['foo'], 'bar')

        cache.delete_saved_content()
        self.check_cache_gone(cache_name, csv_path=True)
        cache.load_or_build()
        self.assert_contents_equal(cache, {})

    def test_custom_row_builder_reader(self):
        def tuple_key_expander(key, value):
            return list(key) + [value]

        def tuple_key_extractor(row):
            key = tuple(row[:-1])
            value = float(row[-1])
            return key, value

        cache_name = self.check_cache_gone('custom_builder', csv_path=True)

        cache = CSVCache(cache_name, cache_manager=self.manager,
                row_builder=tuple_key_expander, row_reader=tuple_key_extractor)
        cache[('foo', 'bar')] = 1
        cache.save()

        self.check_cache(cache_name, True, csv_path=True)
        cache.load() # Reload
        self.check_cache(cache_name, True, csv_path=True)
        self.assertEqual(cache[('foo', 'bar')], 1)

    def test_basic_autosync_actions(self):
        cache_name = self.check_cache_gone('csv_auto', csv_path=True)
        cache = AutoSyncCSVCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        self.assertEqual(cache['foo'], 'bar')

        cache.save() # No-op
        self.check_cache(cache_name, True, csv_path=True)
        cache.load() # Reload
        self.check_cache(cache_name, True, csv_path=True)
        self.assertEqual(cache['foo'], 'bar')
        self.assertTrue('foo' in cache)
        self.assertFalse('foo2' in cache)

        cache.delete_saved_content()
        cache.load()
        self.assertIsNone(cache.contents)
        cache.load_or_build()
        self.assert_contents_equal(cache, {})

    def test_auto_sync_csv(self):
        cache_name = self.check_cache_gone('csv_auto', csv_path=True)

        cache = self.build_fast_sync_cache(cache_name)
        self.assertEqual(len(cache.time_counts), 5)

        cache['not_enough'] = True
        cache.load()
        self.assert_contents_equal(cache, {})

        # Time counts should have cleared on load
        self.assertEqual(list(cache.time_counts), [0] * 5)

        cache['first'] = '1'
        cache['second'] = '2'
        cache.load()
        self.assert_contents_equal(cache, { 'first': '1', 'second': '2' })

        cache['first'] = 'overwritten'
        self.faketime.incr_time(timedelta(seconds=2))
        cache['second'] = 'overwritten'
        cache.load()
        # No save should have triggered
        self.assert_contents_equal(cache, { 'first': '1', 'second': '2' })

        cache.invalidate_and_rebuild()
        self.faketime.incr_time(timedelta(seconds=2))
        for count in xrange(10):
            cache[str(count)] = str(count)
        cache.load()
        # No save should have triggered save from second time window
        self.assert_contents_equal(cache, dict((str(i), str(i)) for i in xrange(10)))

if __name__ == '__main__':
    unittest.main()

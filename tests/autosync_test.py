# This import fixes sys.path issues
from . import parentpath

import unittest
from .faketime import FakeTime
from datetime import datetime, timedelta
from cacheman import autosync
from .common import CacheCommonAsserter

class AutoSyncCacheTest(CacheCommonAsserter, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        CacheCommonAsserter.__init__(self)
        unittest.TestCase.__init__(self, *args, **kwargs)

    def setUp(self):
        CacheCommonAsserter.setUp(self)
        self.faketime = FakeTime()
        autosync.datetime = self.faketime

    def tearDown(self):
        CacheCommonAsserter.tearDown(self)
        autosync.datetime = datetime

    def build_fast_sync_cache(self, cache_name):
        return autosync.AutoSyncCache(cache_name, cache_manager=self.manager,
                time_checks=[autosync.TimeCount(1, 2), autosync.TimeCount(5, 10)], time_bucket_size=1)

    def test_basic_cache_actions(self):
        cache_name = 'basics'
        cache = autosync.AutoSyncCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        self.assertEqual(cache['foo'], 'bar')

        cache.save() # No-op
        self.check_cache(cache_name, True)
        cache.load() # Reload
        self.check_cache(cache_name, True)
        self.assertEqual(cache['foo'], 'bar')
        self.assertTrue('foo' in cache)
        self.assertFalse('foo2' in cache)

        cache.delete_saved_content()
        cache.load()
        self.assertIsNone(cache.contents)
        cache.load_or_build()
        self.assert_contents_equal(cache, {})

    def test_auto_sync_time_windows(self):
        cache_name = 'auto'
        cache = self.build_fast_sync_cache(cache_name)
        self.assertEqual(len(cache.time_counts), 5)

        cache['not_enough'] = True
        cache.load()
        self.assert_contents_equal(cache, {})

        # Time counts should have cleared on load
        self.assertEqual(list(cache.time_counts), [0] * 5)

        cache['first'] = 1
        cache['second'] = 2
        cache.load()
        self.assert_contents_equal(cache, { 'first': 1, 'second': 2 })

        cache['first'] = 'overwritten'
        self.faketime.incr_time(timedelta(seconds=2))
        cache['second'] = 'overwritten'
        cache.load()
        # No save should have triggered
        self.assert_contents_equal(cache, { 'first': 1, 'second': 2 })

        cache.invalidate_and_rebuild()
        self.faketime.incr_time(timedelta(seconds=2))
        for count in range(10):
            cache[count] = count
        cache.load()
        # No save should have triggered save from second time window
        self.assert_contents_equal(cache, dict((i, i) for i in range(10)))

    def test_out_of_window(self):
        cache_name = 'out_of_bounds'
        cache = self.build_fast_sync_cache(cache_name)
        self.assertEqual(len(cache.time_counts), 5)

        # Should ignore edit counts from after window
        cache.track_edit(edit_time=self.faketime.now() + timedelta(seconds=1))
        self.assertEqual(list(cache.time_counts), [0] * 5)

        cache.track_edit(edit_time=self.faketime.now() + timedelta(days=5))
        self.assertEqual(list(cache.time_counts), [0] * 5)

        # Should respect edit counts from inside window
        cache.track_edit(edit_time=self.faketime.now())
        self.assertEqual(list(cache.time_counts), [0] * 4 + [1])

        # Should ignore edit counts from before window
        cache.track_edit(edit_time=self.faketime.now() - timedelta(days=1))
        self.assertEqual(list(cache.time_counts), [0] * 4 + [1])

    def test_window_cycling(self):
        cache_name = 'cycle'
        cache = self.build_fast_sync_cache(cache_name)
        self.assertEqual(len(cache.time_counts), 5)

        cache.track_edit(edit_time=self.faketime.now())
        self.assertEqual(list(cache.time_counts), [0] * 4 + [1])

        self.faketime.incr_time(timedelta(seconds=1))
        cache.track_edit()
        self.assertEqual(list(cache.time_counts), [0] * 3 + [1] * 2)

        self.faketime.incr_time(timedelta(seconds=3))
        cache.time_shift_buckets()
        self.assertEqual(list(cache.time_counts), [1] * 2 + [0] * 3)

        # All values should have moved out of window now
        self.faketime.incr_time(timedelta(seconds=2))
        cache.time_shift_buckets()
        self.assertEqual(list(cache.time_counts), [0] * 5)

        # Cycling the whole window shouldn't crash
        self.faketime.incr_time(timedelta(seconds=10))
        cache.time_shift_buckets()
        self.assertEqual(list(cache.time_counts), [0] * 5)

if __name__ == '__main__':
    unittest.main()

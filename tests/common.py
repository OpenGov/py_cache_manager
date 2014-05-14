# This import fixes sys.path issues
import parentpath

import os
import glob
from cacheman import cacher
from cacheman.registers import generate_pickle_path

class CacheCommonAsserter(object):
    TEST_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'test_data')

    @classmethod
    def cleanup(cls):
        # Cleanup any left-over failed content from last test run
        for f in glob.glob(os.path.join(CacheCommonAsserter.TEST_CACHE_DIR, '*.pkl*')):
            os.remove(f)

    def setUp(self):
        self.manager = cacher.CacheManager('self')
        self.manager.cache_directory = CacheCommonAsserter.TEST_CACHE_DIR

    def tearDown(self):
        self.manager.delete_all_saved_cache_contents()
        del self.manager

    def assert_contents_equal(self, cache, check_contents):
        self.assertIsNotNone(cache.contents)
        if isinstance(cache.contents, dict):
            self.assertDictEqual(cache.contents, check_contents)
        elif isinstance(cache.contents, list):
            self.assertListEqual(cache.contents, check_contents)
        else:
            self.assertEqual(cache.contents, check_contents)

    def check_cache(self, cache_name, presence):
        assertion = self.assertTrue if presence else self.assertFalse
        cache_path = generate_pickle_path(CacheCommonAsserter.TEST_CACHE_DIR, cache_name)
        assertion(os.path.isfile(cache_path))
        self.assertFalse(os.path.isfile(cache_path + '.tmp'))
        return cache_name

    def check_cache_gone(self, cache_name):
        return self.check_cache(cache_name, False)

# This import fixes sys.path issues
from . import parentpath

import os
import sys
import glob
import string
import random
import psutil
import tempfile
from cacheman import cacher
from cacheman.utils import random_name
from cacheman.registers import generate_pickle_path, generate_csv_path

class CacheCommonAsserter(object):
    def __init__(self):
        self.test_cache_base_dir = os.path.join(tempfile.gettempdir(), 'test_data')
        self.test_cache_key = random_name()
        self.test_cache_dir = os.path.join(self.test_cache_base_dir, self.test_cache_key)

    def cleanup(self):
        # Cleanup any left-over failed content from last test run
        for proc in psutil.Process().children(recursive=False):
            try: os.waitpid(proc.pid, 0)
            except OSError: pass
        for f in glob.glob(os.path.join(self.test_cache_dir, '*.pkl*')):
            os.remove(f)
        for f in glob.glob(os.path.join(self.test_cache_dir, '*.csv*')):
            os.remove(f)

    def setUp(self):
        self.manager = cacher.CacheManager(self.test_cache_key, self.test_cache_base_dir)

    def tearDown(self):
        self.manager.delete_all_saved_cache_contents()
        self.cleanup()
        del self.manager

    def assert_contents_equal(self, cache, check_contents):
        if check_contents is not None:
            self.assertIsNotNone(cache.contents)
        if isinstance(cache.contents, dict):
            self.assertDictEqual(cache.contents, check_contents)
        elif isinstance(cache.contents, list):
            self.assertListEqual(cache.contents, check_contents)
        else:
            self.assertEqual(cache.contents, check_contents)

    def check_cache(self, cache_name, presence, csv_path=False):
        assertion = self.assertTrue if presence else self.assertFalse
        if csv_path:
            cache_path = generate_csv_path(self.test_cache_dir, cache_name)
        else:
            cache_path = generate_pickle_path(self.test_cache_dir, cache_name)
        assertion(os.path.isfile(cache_path))
        self.assertFalse(os.path.isfile(cache_path + '.tmp'))
        return cache_name

    def check_cache_gone(self, cache_name, csv_path=False):
        return self.check_cache(cache_name, False, csv_path)

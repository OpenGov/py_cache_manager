# This import fixes sys.path issues
import parentpath

import os
import copy
import glob
import unittest
from cacheman import cacher

class CacheManagerTest(unittest.TestCase):
    TEST_CACHE_DIR = os.path.join(os.path.dirname(__file__), 'test_data')

    @classmethod
    def setUpClass(cls):
        # Cleanup any left-over failed content from last test run
        for f in glob.glob(os.path.join(cls.TEST_CACHE_DIR, '*.pkl')):
            os.remove(f)

    def setUp(self):
        self.old_cache_dir = cacher.CACHE_DIR
        cacher.CACHE_DIR = CacheManagerTest.TEST_CACHE_DIR
        self.manager = cacher.CacheManager()

    def tearDown(self):
        self.manager.invalidate_and_delete_all_saved_contents()
        self.manager.deregister_all_caches()
        del self.manager
        cacher.CACHE_DIR = self.old_cache_dir

    def check_cache_gone(self, cache_name):
        self.assertFalse(os.path.isfile(cacher.generate_pickle_path(cache_name)))
        return cache_name

    def register_foo_baz_bar(self, check_file=True):
        cache_one_name = self.check_cache_gone('foo_bar') if check_file else 'foo_bar'
        cache_two_name = self.check_cache_gone('baz_bar') if check_file else 'baz_bar'

        cache_one = self.manager.register_cache(cache_one_name, { 'foo': 'bar' })
        cache_two = self.manager.register_cache(cache_two_name, { 'baz': 'bar' })

        return cache_one_name, cache_two_name

    def test_default_builder(self):
        cache_name = self.check_cache_gone('no_registers')
        self.assertEqual(self.manager.retrieve_cache(cache_name), {})

    def test_default_saver_and_loader(self):
        cache_name = self.check_cache_gone('no_registers')

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)

        cache = self.manager.reload_cache(cache_name)
        self.assertTrue(os.path.isfile(cacher.generate_pickle_path(cache_name)))
        self.assertDictEqual(cache, { 'foo': 'bar' })

    def test_content_invalidation(self):
        cache_name = self.check_cache_gone('no_registers')
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.invalidate_cache(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), {})

        cache = self.manager.reload_cache(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), {})

        # Ensure invalidate_cache doesn't destroy saved content
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache['baz'] = 'not saved'
        self.manager.invalidate_cache(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        cache['baz'] = 'not saved'
        cache = self.manager.reload_cache(cache_name)
        self.assertDictEqual(cache, { 'foo': 'bar' })

    def test_content_invalidation_and_deletion(self):
        cache_name = self.check_cache_gone('no_registers')
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_cache(cache_name)
        self.assertDictEqual(cache, { 'foo': 'bar' })

        self.manager.invalidate_cache_and_saved_contents(cache_name)
        cache_name = self.check_cache_gone('no_registers')
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), {})

    def test_all_content_invalidation_and_deletion(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.save_all_cache_contents()
        self.manager.reload_all_caches()
        self.assertDictEqual(self.manager.retrieve_cache(cache_one_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.retrieve_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.invalidate_and_delete_all_saved_contents()
        cache_one_name = self.check_cache_gone(cache_one_name)
        cache_two_name = self.check_cache_gone(cache_two_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_one_name), {})
        self.assertDictEqual(self.manager.retrieve_cache(cache_two_name), {})

    def register_crashers(self, cache_name):
        def crasher(*args, **kwargs): raise AttributeError("Failed to deregister")

        self.manager.register_loader(cache_name, crasher)
        self.manager.register_builder(cache_name, crasher)
        self.manager.register_saver(cache_name, crasher)
        self.manager.register_post_processor(cache_name, crasher)
        self.manager.register_pre_processor(cache_name, crasher)
        self.manager.register_post_processor(cache_name, crasher)
        self.manager.register_validator(cache_name, crasher)
        self.manager.register_deleter(cache_name, crasher)

    def test_deregistering(self):
        cache_name = self.check_cache_gone('foo_bar')
        self.manager.register_cache(cache_name, { 'foo': 'bar' })
        # Persist for later asserts
        self.manager.save_cache_contents(cache_name)

        self.register_crashers(cache_name)

        # This should skip straight to the registered cache
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.manager.invalidate_cache(cache_name)
        self.assertRaises(AttributeError, self.manager.retrieve_cache, cache_name)
        self.assertRaises(AttributeError, self.manager.reload_cache, cache_name)
        self.assertRaises(AttributeError, self.manager.rebuild_cache, cache_name)

        self.manager.deregister_cache(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), {})

    def test_deregistering_all(self):
        '''
        Deregistering all has different logic inside than for looping on deregister_cache.
        '''
        cache_one_name = self.check_cache_gone('foo_bar_one')
        cache_two_name = self.check_cache_gone('foo_bar_two')
        for cache_name in [cache_one_name, cache_two_name]:
            self.manager.register_cache(cache_name, { 'foo': 'bar' })

        # Persist for later asserts
        self.manager.save_all_cache_contents()

        self.register_crashers(cache_one_name)
        self.register_crashers(cache_two_name)

        # This should skip straight to the registered cache
        for cache_name in [cache_one_name, cache_two_name]:
            self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
            self.manager.invalidate_cache(cache_name)
            self.assertRaises(AttributeError, self.manager.retrieve_cache, cache_name)
            self.assertRaises(AttributeError, self.manager.reload_cache, cache_name)
            self.assertRaises(AttributeError, self.manager.rebuild_cache, cache_name)

        self.manager.deregister_all_caches()

        for cache_name in [cache_one_name, cache_two_name]:
            self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
            self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
            self.assertDictEqual(self.manager.rebuild_cache(cache_name), {})

    def test_register(self):
        cache_name = self.check_cache_gone('foo_baz_bar')
        cache = { 'foo': 'bar' }
        self.manager.register_cache(cache_name, cache)
        self.assertTrue(self.manager.cache_registered(cache_name))
        cache['baz'] = 'bar'
        # Make sure assignments register
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })

    def test_loader(self):
        cache_name = 'foo_bar'
        self.manager.register_loader(cache_name, lambda c: { 'foo': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        self.assertDictEqual(cache, { 'foo': 'bar' })
        cache['baz'] = 'bar'
        self.assertDictEqual(cache, { 'foo': 'bar', 'baz': 'bar' })
        # Loader now ignored saved content
        self.manager.save_cache_contents(cache_name)

        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), {})
        # Loader ignores persistent store, so rebuild shouldn't affect it
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_builder(self):
        cache_name = 'foo_bar'
        self.manager.register_builder(cache_name, lambda: { 'foo': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        self.assertDictEqual(cache, { 'foo': 'bar' })
        cache['baz'] = 'bar'
        self.assertDictEqual(cache, { 'foo': 'bar', 'baz': 'bar' })
        self.manager.save_cache_contents(cache_name)

        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), { 'foo': 'bar' })
        # Persistent state should be altered by the rebuild call
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_saver(self):
        cache_name = 'foo_bar'
        self.cache_store = {}
        def saver(cache_name, contents): self.cache_store = copy.copy(contents)

        self.manager.register_saver(cache_name, saver)
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.cache_store, {})
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.cache_store, { 'foo': 'bar' })

    def test_deleter(self):
        cache_name = 'foo_bar'
        self.deleted_cache = {}
        def deleter(cache_name):
            self.deleted_cache = self.manager.retrieve_cache(cache_name)
            cacher.pickle_deleter(cache_name)

        self.manager.register_deleter(cache_name, deleter)
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.deleted_cache, {})
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.deleted_cache, {})
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

        self.manager.delete_saved_content(cache_name)
        self.check_cache_gone(cache_name)
        self.assertDictEqual(self.deleted_cache, { 'foo': 'bar' })
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        # The file was nuked, so reloading should give us a new cache element
        self.assertDictEqual(self.manager.reload_cache(cache_name), {})

    def test_register_post_processor(self):
        cache_name = self.check_cache_gone('foo_bar')
        def post_proc(contents):
            contents['baz'] = 'bar'
            return contents

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.manager.register_post_processor(cache_name, post_proc)
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), { 'baz': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        cache['baz'] = 'foo'
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'baz': 'foo' })
        # Overwrites the changes we persisted
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'baz': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), { 'baz': 'bar' })

    def test_register_pre_processor(self):
        cache_name = self.check_cache_gone('foo_bar')
        def pre_proc(contents):
            contents['baz'] = 'bar'
            return contents

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.manager.register_pre_processor(cache_name, pre_proc)
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), { 'baz': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        cache['baz'] = 'foo'
        self.manager.save_cache_contents(cache_name)
        # Change ignored as pre_proc overwrites it
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'baz': 'bar' })

    def test_register_validator(self):
        cache_name = self.check_cache_gone('foo_bar')
        self.manager.register_validator(cache_name, lambda c: 'foo' in c)

        cache = self.manager.retrieve_cache(cache_name)
        self.assertDictEqual(cache, {})
        cache['baz'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_cache(cache_name)
        # Reload should cause a build as no 'foo' argument is present
        self.assertDictEqual(cache, {})

        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_dependent_save_and_delete(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)

        self.manager.save_cache_contents(cache_one_name, True)
        self.assertDictEqual(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        # Should persist second cache
        self.assertDictEqual(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.delete_saved_content(cache_one_name)
        cache_one = self.manager.reload_cache(cache_one_name)
        cache_two = self.manager.reload_cache(cache_two_name)
        self.assertDictEqual(cache_one, {})
        # Should nuke second cache
        self.assertDictEqual(cache_two, {})

    def test_dependent_invalidate(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)
        self.manager.save_all_cache_contents()
        cache_one = self.manager.retrieve_cache(cache_one_name)
        cache_two = self.manager.retrieve_cache(cache_two_name)
        cache_one['ignored'] = True
        cache_two['ignored'] = True

        self.manager.invalidate_cache(cache_one_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_one_name), { 'foo': 'bar' })
        # Should nuke second cache
        self.assertDictEqual(self.manager.retrieve_cache(cache_two_name), { 'baz': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.invalidate_cache_and_saved_contents(cache_one_name)
        self.assertDictEqual(self.manager.retrieve_cache(cache_one_name), {})
        # Should nuke second cache
        self.assertDictEqual(self.manager.retrieve_cache(cache_two_name), {})
        self.assertDictEqual(self.manager.reload_cache(cache_one_name), {})
        self.assertDictEqual(self.manager.reload_cache(cache_two_name), {})

    def test_dependent_deregister(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)
        self.manager.save_all_cache_contents()

        self.assertTrue(self.manager.cache_registered(cache_one_name))
        self.assertTrue(self.manager.cache_registered(cache_two_name))
        self.manager.deregister_cache(cache_one_name, True)
        self.assertFalse(self.manager.cache_registered(cache_one_name))
        self.assertFalse(self.manager.cache_registered(cache_two_name))

        # Regegister so we clear out the files during cleanup
        self.register_foo_baz_bar(False)

    def test_deregister_all(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.save_all_cache_contents()

        self.assertTrue(self.manager.cache_registered(cache_one_name))
        self.assertTrue(self.manager.cache_registered(cache_two_name))
        self.manager.deregister_all_caches()
        self.assertFalse(self.manager.cache_registered(cache_one_name))
        self.assertFalse(self.manager.cache_registered(cache_two_name))

        # Regegister so we clear out the files during cleanup
        self.register_foo_baz_bar(False)

    def test_chain_registrated_save(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        cache_three_name = self.check_cache_gone('grandchild')
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)
        self.manager.register_dependent_cache(cache_two_name, cache_three_name)
        cache_three = self.manager.register_cache(cache_three_name, { 'grand': 'child' })
        # Save first cache
        self.manager.save_cache_contents(cache_one_name, True)
        self.assertDictEqual(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })
        self.assertDictEqual(self.manager.reload_cache(cache_three_name), { 'grand': 'child' })

    def test_non_persistent_register(self):
        cache_name = self.check_cache_gone('foo_bar')
        cache = self.manager.register_cache(cache_name, { 'foo': 'bar' }, persistent=False)
        self.manager.save_cache_contents(cache_name)
        # No file should be created
        cache_name = self.check_cache_gone('foo_bar')

        cache['baz'] = 'bar'
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_cache(cache_name)
        # Saving shouldn't have persisted the data
        self.assertDictEqual(cache, {})
        cache['baz'] = 'bar'
        self.assertDictEqual(self.manager.retrieve_cache(cache_name), { 'baz': 'bar' })
        self.assertDictEqual(self.manager.rebuild_cache(cache_name), {})

if __name__ == '__main__':
    unittest.main()

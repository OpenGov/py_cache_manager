# This import fixes sys.path issues
import parentpath

import copy
import unittest
import psutil
import os
from cacheman import registers
from common import CacheCommonAsserter

class CacheManagerTest(CacheCommonAsserter, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CacheCommonAsserter.cleanup()

    def register_foo_baz_bar(self, check_file=True):
        cache_one_name = self.check_cache_gone('foo_bar') if check_file else 'foo_bar'
        cache_two_name = self.check_cache_gone('baz_bar') if check_file else 'baz_bar'

        self.manager.register_cache(cache_one_name, { 'foo': 'bar' })
        self.manager.register_cache(cache_two_name, { 'baz': 'bar' })

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
        self.check_cache(cache_name, True)
        self.assert_contents_equal(cache, { 'foo': 'bar' })

    def test_default_saver_overwrite(self):
        cache_name = self.check_cache_gone('no_registers')

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        self.check_cache(cache_name, True)
        self.manager.save_cache_contents(cache_name)
        self.check_cache(cache_name, True)

        cache['foo'] = 'baz'
        self.manager.save_cache_contents(cache_name)

        cache = self.manager.reload_cache(cache_name)
        self.check_cache(cache_name, True)
        self.assert_contents_equal(cache, { 'foo': 'baz' })

    def test_content_invalidation(self):
        cache_name = self.check_cache_gone('no_registers')
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.invalidate_cache(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), {})

        cache = self.manager.reload_cache(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), {})

        # Ensure invalidate_cache doesn't destroy saved content
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache['baz'] = 'not saved'
        self.manager.invalidate_cache(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        cache['baz'] = 'not saved'
        cache = self.manager.reload_cache(cache_name)
        self.assert_contents_equal(cache, { 'foo': 'bar' })

    def test_content_invalidation_and_deletion(self):
        cache_name = self.check_cache_gone('no_registers')
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_cache(cache_name)
        self.assert_contents_equal(cache, { 'foo': 'bar' })

        self.manager.delete_saved_cache_content(cache_name)
        cache_name = self.check_cache_gone('no_registers')
        self.manager.invalidate_and_rebuild_cache(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), {})

    def test_all_content_invalidation_and_deletion(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.save_all_cache_contents()
        self.manager.reload_all_caches()
        self.assert_contents_equal(self.manager.retrieve_cache(cache_one_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.retrieve_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.delete_all_saved_cache_contents()
        cache_one_name = self.check_cache_gone(cache_one_name)
        cache_two_name = self.check_cache_gone(cache_two_name)
        self.manager.invalidate_and_rebuild_all_caches()
        self.assert_contents_equal(self.manager.retrieve_cache(cache_one_name), {})
        self.assert_contents_equal(self.manager.retrieve_cache(cache_two_name), {})

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

    def clear_registers(self, cache_name):
        self.manager.register_loader(cache_name, None)
        self.manager.register_builder(cache_name, None)
        self.manager.register_saver(cache_name, None)
        self.manager.register_post_processor(cache_name, None)
        self.manager.register_pre_processor(cache_name, None)
        self.manager.register_post_processor(cache_name, None)
        self.manager.register_validator(cache_name, None)
        self.manager.register_deleter(cache_name, None)

    def test_deregistering(self):
        cache_name = self.check_cache_gone('foo_bar')
        self.manager.register_cache(cache_name, { 'foo': 'bar' })
        # Persist for later asserts
        self.manager.save_cache_contents(cache_name)

        self.register_crashers(cache_name)

        # This should skip straight to the registered cache
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertRaises(AttributeError, self.manager.reload_cache, cache_name)
        self.assertRaises(AttributeError, self.manager.invalidate_and_rebuild_cache, cache_name)

        # Manager will crash trying to save if we use deregister
        self.clear_registers(cache_name)
        self.manager.deregister_cache(cache_name)

        self.assertFalse(self.manager.cache_registered(cache_name))
        self.assertRaises(KeyError, self.manager.retrieve_raise, cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), {})

        self.clear_registers(cache_name)

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
            self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
            self.assertRaises(AttributeError, self.manager.invalidate_cache, cache_name)
            self.assertRaises(AttributeError, self.manager.reload_cache, cache_name)
            self.assertRaises(AttributeError, self.manager.invalidate_and_rebuild_cache, cache_name)

        self.clear_registers(cache_one_name)
        self.clear_registers(cache_two_name)
        self.manager.deregister_all_caches()
        self.assertFalse(self.manager.cache_registered(cache_one_name))
        self.assertFalse(self.manager.cache_registered(cache_two_name))
        self.assertRaises(KeyError, self.manager.retrieve_raise, cache_one_name)
        self.assertRaises(KeyError, self.manager.retrieve_raise, cache_two_name)

        for cache_name in [cache_one_name, cache_two_name]:
            self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
            self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
            self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), {})

    def test_register(self):
        cache_name = self.check_cache_gone('foo_baz_bar')
        cache = { 'foo': 'bar' }
        self.manager.register_cache(cache_name, cache)
        self.assertTrue(self.manager.cache_registered(cache_name))
        cache['baz'] = 'bar'
        # Make sure assignments register
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })

    def test_loader(self):
        cache_name = 'foo_bar'
        cache = self.manager.register_loader(cache_name, lambda *args: { 'foo': 'bar' })
        cache.load()

        self.assert_contents_equal(cache, { 'foo': 'bar' })
        cache['baz'] = 'bar'
        self.assert_contents_equal(cache, { 'foo': 'bar', 'baz': 'bar' })
        # Loader now ignored saved content
        self.manager.save_cache_contents(cache_name)

        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), {})
        # Loader ignores persistent store, so rebuild shouldn't affect it
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_builder(self):
        cache_name = 'foo_bar'
        cache = self.manager.register_builder(cache_name, lambda *args: { 'foo': 'bar' })
        self.manager.invalidate_and_rebuild_cache(cache_name)

        self.assert_contents_equal(cache, { 'foo': 'bar' })
        cache['baz'] = 'bar'
        self.assert_contents_equal(cache, { 'foo': 'bar', 'baz': 'bar' })
        self.manager.save_cache_contents(cache_name)

        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), { 'foo': 'bar' })
        # Persistent state should be altered by the rebuild call
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_saver(self):
        cache_name = 'foo_bar'
        self.cache_store = {}
        def saver(cache_name, contents): self.cache_store = copy.copy(contents)

        cache = self.manager.register_saver(cache_name, saver)
        cache['foo'] = 'bar'

        self.assert_contents_equal(cache, { 'foo': 'bar' })
        self.assertDictEqual(self.cache_store, {})
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.cache_store, { 'foo': 'bar' })

    def test_deleter(self):
        cache_name = 'foo_bar'
        self.deleted_cache = {}
        def deleter(cache_name):
            self.deleted_cache = self.manager.retrieve_cache(cache_name)
            registers.pickle_deleter(CacheCommonAsserter.TEST_CACHE_DIR, cache_name)

        self.manager.register_deleter(cache_name, deleter)
        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assertDictEqual(self.deleted_cache, {})
        self.manager.save_cache_contents(cache_name)
        self.assertDictEqual(self.deleted_cache, {})
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

        self.manager.delete_saved_cache_content(cache_name)
        self.check_cache_gone(cache_name)
        self.assert_contents_equal(self.deleted_cache, { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        # The file was nuked, so reloading should give us a blank cache
        self.assertIsNone(self.manager.reload_cache(cache_name).contents)

    def test_register_post_processor(self):
        cache_name = self.check_cache_gone('foo_bar')
        def post_proc(contents):
            contents['baz'] = 'bar'
            return contents

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.manager.register_post_processor(cache_name, post_proc)
        self.manager.save_cache_contents(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), { 'baz': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        cache['baz'] = 'foo'
        self.manager.save_cache_contents(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'baz': 'foo' })
        # Overwrites the changes we persisted
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'baz': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), { 'baz': 'bar' })

    def test_register_pre_processor(self):
        cache_name = self.check_cache_gone('foo_bar')
        def pre_proc(contents):
            contents['baz'] = 'bar'
            return contents

        cache = self.manager.retrieve_cache(cache_name)
        cache['foo'] = 'bar'

        self.manager.register_pre_processor(cache_name, pre_proc)
        self.manager.save_cache_contents(cache_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), { 'baz': 'bar' })

        cache = self.manager.retrieve_cache(cache_name)
        cache['baz'] = 'foo'
        self.manager.save_cache_contents(cache_name)
        # Change ignored as pre_proc overwrites it
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'baz': 'bar' })

    def test_register_validator(self):
        cache_name = self.check_cache_gone('foo_bar')
        self.manager.register_validator(cache_name, lambda c: 'foo' in c)

        cache = self.manager.retrieve_cache(cache_name)
        self.assert_contents_equal(cache, {})
        cache['baz'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_or_rebuild_cache(cache_name)
        # Reload should cause a build as no 'foo' argument is present
        self.assert_contents_equal(cache, {})

        cache['foo'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        self.assert_contents_equal(self.manager.reload_cache(cache_name), { 'foo': 'bar' })

    def test_dependent_save_and_delete(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)

        self.manager.save_cache_contents(cache_one_name, True)
        self.assert_contents_equal(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        # Should persist second cache
        self.assert_contents_equal(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.delete_saved_cache_content(cache_one_name)
        cache_one = self.manager.reload_or_rebuild_cache(cache_one_name, True)
        self.assert_contents_equal(cache_one, {})
        # Should nuke second cache
        self.assert_contents_equal(self.manager.retrieve_raise(cache_two_name), {})

    def test_dependent_invalidate(self):
        cache_one_name, cache_two_name = self.register_foo_baz_bar()
        self.manager.register_dependent_cache(cache_one_name, cache_two_name)
        self.manager.save_all_cache_contents()
        cache_one = self.manager.retrieve_cache(cache_one_name)
        cache_two = self.manager.retrieve_cache(cache_two_name)
        cache_one['ignored'] = True
        cache_two['ignored'] = True

        self.manager.invalidate_cache(cache_one_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_one_name), { 'foo': 'bar' })
        # Should nuke second cache
        self.assert_contents_equal(self.manager.retrieve_cache(cache_two_name), { 'baz': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })

        self.manager.invalidate_and_rebuild_cache(cache_one_name)
        self.assert_contents_equal(self.manager.retrieve_cache(cache_one_name), {})
        # Should nuke second cache
        self.assert_contents_equal(self.manager.retrieve_cache(cache_two_name), {})
        self.assert_contents_equal(self.manager.reload_cache(cache_one_name), {})
        self.assert_contents_equal(self.manager.reload_cache(cache_two_name), {})

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
        self.assert_contents_equal(self.manager.reload_cache(cache_one_name), { 'foo': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_two_name), { 'baz': 'bar' })
        self.assert_contents_equal(self.manager.reload_cache(cache_three_name), { 'grand': 'child' })

    def test_non_persistent_register(self):
        cache_name = self.check_cache_gone('foo_bar')
        cache = self.manager.register_custom_cache(cache_name, { 'foo': 'bar' }, persistent=False)
        self.manager.save_cache_contents(cache_name)
        # No file should be created
        cache_name = self.check_cache_gone('foo_bar')

        cache['baz'] = 'bar'
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'foo': 'bar', 'baz': 'bar' })
        self.manager.save_cache_contents(cache_name)
        cache = self.manager.reload_cache(cache_name)
        # Saving shouldn't have persisted the data
        self.assert_contents_equal(cache, {})
        cache['baz'] = 'bar'
        self.assert_contents_equal(self.manager.retrieve_cache(cache_name), { 'baz': 'bar' })
        self.assert_contents_equal(self.manager.invalidate_and_rebuild_cache(cache_name), {})

    def wait_async_complete(self):
        parent = psutil.Process(os.getpid())
        for child in parent.children(recursive=False):
            child.wait(timeout=10)

    def test_async_saver(self):
        cache_name = self.check_cache_gone('foo_bar')
        cache = self.manager.register_custom_cache(cache_name, { 'foo': 'bar' }, async=True)
        self.assertTrue(cache.async_saver)
        self.manager.save_cache_contents(cache_name)
        self.wait_async_complete()

        cache = self.manager.retrieve_cache(cache_name)
        cache['baz'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        self.wait_async_complete()

        cache = self.manager.reload_cache(cache_name)
        self.check_cache(cache_name, True)
        self.assert_contents_equal(cache, { 'foo': 'bar', 'baz': 'bar' })

    def test_async_saver_queue(self):
        cache_name = self.check_cache_gone('foo_bar')
        cache = self.manager.register_custom_cache(cache_name, { 'foo': 'bar' }, async=True)
        self.assertTrue(cache.async_saver)
        for _ in range(50):
            self.manager.save_cache_contents(cache_name)
        cache['baz'] = 'bar'
        self.manager.save_cache_contents(cache_name)
        self.wait_async_complete()

        cache = self.manager.reload_cache(cache_name)
        self.check_cache(cache_name, True)
        self.assert_contents_equal(cache, { 'foo': 'bar', 'baz': 'bar' })

if __name__ == '__main__':
    unittest.main()

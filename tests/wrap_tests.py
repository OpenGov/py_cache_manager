# This import fixes sys.path issues
from . import parentpath

import unittest
from cacheman.cachewrap import CacheWrap, NonPersistentCache, PersistentCache
from .common import CacheCommonAsserter

class CacheWrapTest(CacheCommonAsserter, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        CacheCommonAsserter.__init__(self)
        unittest.TestCase.__init__(self, *args, **kwargs)

    def assert_registrations_blank(self, cache, registration_names):
        for reg in registration_names:
            self.assertIsNone(getattr(cache, reg))

    def fake_registration(self, *args, **kwargs):
        return 'Some custom function'

    def test_self_registering_cache(self):
        for call_name in CacheWrap.CALLBACK_NAMES:
            cache_name = 'foo_' + call_name
            cache = CacheWrap(cache_name, cache_manager=self.manager,
                **{ call_name: self.fake_registration })

            registers = [reg for reg in CacheWrap.CALLBACK_NAMES if reg != call_name]
            self.assert_registrations_blank(cache, registers)
            callback = getattr(cache, call_name)
            self.assertIsNotNone(callback)
            self.assertEqual(callback(), self.fake_registration())

    def test_non_persistent_cache_wrap(self):
        cache_name = 'cache_wrap'

        cache = NonPersistentCache(cache_name, cache_manager=self.manager, contents={})
        cache['foo'] = 'bar'
        self.assertEqual(cache['foo'], 'bar')

        cache.save() # No-op
        self.check_cache_gone(cache_name)
        cache.load() # Clear

        self.check_cache_gone(cache_name)
        self.assertNotIn('foo', cache)

    def test_persistent_cache_wrap(self):
        cache_name = self.check_cache_gone('persistent')

        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={})
        cache['foo'] = 'bar'
        cache.save()

        self.check_cache(cache_name, True)
        cache.load() # Reload
        self.check_cache(cache_name, True)
        self.assertEqual(cache['foo'], 'bar')

    def test_content_driven_cache_wrap(self):
        cache_name = self.check_cache_gone('content')

        # Pass a non-empty list as content
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents=[''],
            builder=lambda *args: [])
        cache[0] = 'foo'
        cache.append('bar')
        cache.save()

        cache.load()
        self.assertTrue(isinstance(cache, PersistentCache))
        self.assertTrue(isinstance(cache.contents, list))
        self.check_cache(cache_name, True)
        self.assertEqual(cache[0], 'foo')
        self.assertEqual(cache[1], 'bar')

        cache.invalidate_and_rebuild()
        self.assertTrue(isinstance(cache, PersistentCache))
        self.assertTrue(isinstance(cache.contents, list))
        self.assert_contents_equal(cache, [])

    def test_load_on_init(self):
        cache_name = self.check_cache_gone('load_init')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' })
        cache.save()

        cache = PersistentCache(cache_name, cache_manager=self.manager)
        self.assertEqual(cache['foo'], 'bar')

    def test_build_on_init(self):
        cache_name = self.check_cache_gone('built')
        cache = NonPersistentCache(cache_name, cache_manager=self.manager, loader=None,
            builder=lambda *args: [])
        self.assertTrue(isinstance(cache.contents, list))
        self.assert_contents_equal(cache, [])

    def test_delete_save(self):
        cache_name = self.check_cache_gone('deleted')
        cache = PersistentCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        cache.__del__() # To avoid lazy deletion calls/reference counts
        self.check_cache(cache_name, True)

        cache = PersistentCache(cache_name, cache_manager=self.manager)
        self.assertEqual(cache['foo'], 'bar')

    def test_scoped_cache(self):
        cache_name = self.check_cache_gone('scoped')
        with PersistentCache(cache_name, cache_manager=self.manager) as cache:
            cache['foo'] = 'bar'
        self.check_cache(cache_name, True)

        # Should have saved contents in last scoping
        with PersistentCache(cache_name, cache_manager=self.manager) as cache:
            self.assertEqual(cache['foo'], 'bar')

    def test_contains(self):
        cache_name = self.check_cache_gone('contains')
        cache = NonPersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' })
        self.assertTrue('foo' in cache)
        self.assertFalse('foo2' in cache)

    def test_save_and_load(self):
        cache_name = self.check_cache_gone('save_load')
        cache = PersistentCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        cache.save()

        cache.contents = {}
        self.assert_contents_equal(cache, {})

        cache.load()
        self.assertEqual(cache['foo'], 'bar')

    def test_invalidate(self):
        cache_name = self.check_cache_gone('invalidate')
        cache = PersistentCache(cache_name, cache_manager=self.manager)
        cache['foo'] = 'bar'
        cache.save()
        cache['baz'] = 'bar'

        cache.invalidate() # Should reload
        self.assertEqual(cache['foo'], 'bar')
        self.assertNotIn('baz', cache)

    def test_delete_saved(self):
        cache_name = self.check_cache_gone('delete_saved')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' })

        cache.delete_saved_content()
        self.check_cache_gone(cache_name)
        self.assertEqual(cache['foo'], 'bar') # Shouldn't delete memory

        cache.load()
        self.assertIsNone(cache.contents) # No content to load

        cache.load_or_build()
        self.assert_contents_equal(cache, {})

    def test_invalidate_and_rebuild(self):
        cache_name = self.check_cache_gone('invalidate_rebuild')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' })
        cache.save()

        cache.invalidate_and_rebuild()
        self.assert_contents_equal(cache, {})

        cache.load() # Saved content should get replaced
        self.assert_contents_equal(cache, {})

    def test_load_or_build(self):
        cache_name = self.check_cache_gone('load_build')
        cache = CacheWrap(cache_name, cache_manager=self.manager, loader=lambda *args: ['loaded'],
            builder=lambda *args: ['built'])

        self.assert_contents_equal(cache, ['loaded'])
        cache.load_or_build()
        self.assert_contents_equal(cache, ['loaded'])
        cache.loader = None
        cache.load_or_build()
        self.assert_contents_equal(cache, ['built'])

    def test_validation(self):
        cache_name = self.check_cache_gone('validation')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' },
            validator=lambda *args: False, builder=lambda *args: ['built'])
        cache.save()

        cache.load_or_build() # Invalid load, force rebuild
        self.assert_contents_equal(cache, ['built'])
        cache[0] = 'changed'
        cache.save()

        cache.validator = lambda *args: True
        cache.load()
        self.assert_contents_equal(cache, ['changed'])

        # Raising an exception in validator should invalidate the cache
        cache.validator = lambda *args: args['not legal']
        cache.load()
        self.assert_contents_equal(cache, None)

    def test_dependents(self):
        dependent_cache_name = self.check_cache_gone('dependent')
        dependent_cache = PersistentCache(dependent_cache_name, cache_manager=self.manager)

        parent_cache_name = self.check_cache_gone('parent')
        parent_cache = PersistentCache(parent_cache_name, cache_manager=self.manager, dependents=[dependent_cache])

        dependent_cache['foo'] = 'bar'
        parent_cache.save(True)
        dependent_cache['foo'] = 'saved'

        parent_cache.load(True)
        self.assertEqual(dependent_cache['foo'], 'bar')

        dependent_cache['foo'] = 'invalid'
        parent_cache.invalidate(True)
        self.assertEqual(dependent_cache['foo'], 'bar')

        parent_cache.delete_saved_content(True)
        parent_cache.load(True)
        self.assertIsNone(dependent_cache.contents)

        parent_cache.load_or_build(True)
        self.assertDictEqual(dependent_cache.contents, {})
        dependent_cache['foo'] = 'bar'
        dependent_cache.save()

        parent_cache.invalidate_and_rebuild(True)
        self.assertDictEqual(dependent_cache.contents, {})

    def test_pre_processor(self):
        cache_name = self.check_cache_gone('pre_process')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' },
            pre_processor=lambda c: { 'foo2': c.get('foo', 'missing') })
        self.assert_contents_equal(cache, { 'foo': 'bar' })
        cache.save()
        # Preprocessor should have applied to save, but not cache
        self.assert_contents_equal(cache, { 'foo': 'bar' })

        cache.load() # Load the preprocessor changes
        self.assert_contents_equal(cache, { 'foo2': 'bar' })

    def test_post_processor(self):
        cache_name = self.check_cache_gone('post_process')
        cache = PersistentCache(cache_name, cache_manager=self.manager, contents={ 'foo': 'bar' },
            post_processor=lambda c: { 'foo2': c.get('foo', 'missing') })
        self.assert_contents_equal(cache, { 'foo': 'bar' })
        cache.save()
        # Postprocessor should not have applied to save or cache
        self.assert_contents_equal(cache, { 'foo': 'bar' })

        cache.load() # Load and apply postprocessor changes
        self.assert_contents_equal(cache, { 'foo2': 'bar' })

if __name__ == '__main__':
    unittest.main()

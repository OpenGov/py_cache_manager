# CacheMan
A Python interface for managing dependent caches.

'Ba-Bop-Ba-Dop-Bop'

## Description
This module acts as a dependency manager for caches and is ideal for instances
where a program has many repeated computations that could be safely persisted.
This usually entails a DB layer to house key value pairs. However, such a layer
is sometimes overkill and managing a DB along with a project can be more effort
than it's worth. That's where CacheMan comes in and provides an interface
through which you can define savers, loaders, builders, and dependencies with
disk-based defaults.

By default all caches will auto save when 10k changes occur over 60 seconds, 10
changes occur over 300 seconds (but after 60 seconds), or 1 change occurs within
900 seconds (after 300 seconds). This behavior can be changed by instantiating
an AutoSyncCache from the autosync submodule.

## Dependencies
allset -- for automatic module importing

## Features
* Drop in replacement for local memory dictionaries
* Default persistent pickle caches
* Non-persistent caching
* Cache load/save/delete hooks w/ defaults
* Cache validation hooks
* Cache builder hooks
* Dependent invalidation
* Auto-Syncing caches

## How to use
Below are some simple examples for how to use the repository.

### Setting up a simple persistent cache
    from cacheman import cacher

    manager = cacher.get_cache_manager() # Optional manager name argument can be used here
    cache = manager.register_cache('my_simple_cache') # You now have a cache!
    print cache.get('my_key') # `None` first run, 'my_value' if this code was executed earlier
    cache['my_key'] = 'my_value'
    cache.save() # Changes are now persisted to disk
    manager.save_cache_contents('my_simple_cache') # Alternative way to save a cache

### Non-persistent caches
    from cacheman import cacher

    manager = cacher.get_cache_manager()
    cache = manager.register_custom_cache('my_simple_cache', persistent=False) # You cache won't save to disk
    cache.save() # This is a no-op

### Registering hooks
    from cacheman import cacher
    from cacheman import cachewrap

    def my_saver(cache_name, contents):
        print("Save requested on {} cache content: {}".format(cache_name, contents))

    def my_loader(cache_name):
        return { 'load': 'faked' }

    manager = cacher.get_cache_manager()

    cache = cachewrap.PersistentCache('my_cache', saver=my_saver, loader=my_loader)
    # Can also use manager to set savers/loaders
    #manager.retrieve_cache('my_cache')
    #manager.register_saver('my_cache', my_saver)
    #manager.register_loader('my_cache', my_loader)

    cache.save() # Will print 'Save ... : { 'load': 'faked' }'
    cache['new'] = 'real' # Add something to the cache
    cache.save() # Will print 'Save ... : { 'load': 'faked', 'new': 'real' }'


### Dependent caches
    from cacheman import cacher

    manager = cacher.get_cache_manager()
    edge_cache = manager.retrieve_cache('edge_cache')
    root_cache = manager.register_cache('root_cache')
    manager.register_dependent_cache('root_cache', 'edge_cache')

    def set_processed_value():
        # Computes and caches 'processed' from root's 'raw' value
        processed = edge_cache.get('processed')
        if processed is None:
            processed = (root_cache.get('raw') or 0) * 5
            edge_cache['processed'] = processed
        return processed

    # A common problem with caching computed or dependent values:
    print set_processed_value() # 0 without raw value
    root_cache['raw'] = 1
    print set_processed_value() # still 0 because it's cache in edge

    # Now we use cache invalidation to tell downstream caches they're no longer valid
    root_cache.invalidate() # Invalidates dependent caches
    print edge_cache # Prints {} even though we only invalidated the root_cache
    root_cache['raw'] = 1
    print set_processed_value() # Now 5 because the edge was cleared before the request
    print edge_cache # Can see {'processed': 5} propogated

### Setting cache directory
    from cacheman import cacher

    manager = cacher.get_cache_manager()
    # Default cache directory is '/tmp/general_cacher' or 'user\appadata\local\temp\general_cache'
    manager.cache_directory = 'secret/cache/location' # All pickle caches now save here

    cache = manager.register_cache('my_cache')
    cache['new'] = 'real' # Add something to the cache
    cache.save('my_cache') # Will save contents to 'secret/cache/location/my_cache.pkl'

## Navigating the Repo
### cacheman
Package wrapper for the repo.

### tests
All unit tests for the repo.

## Language Preferences
* Google Style Guide
* Object Oriented (with a few exceptions)

## TODO
V2.1
* cPickle with fallback to pickle by default
* Better argument checks

## Author
Author(s): Matthew Seal

&copy; Copyright 2013, [OpenGov](http://opengov.com)

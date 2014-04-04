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

## Dependencies
None -- cacheman is a standalone module using only built-in libraries.

## Features
* Drop in replacement for local memory dictionaries
* Default persistent pickle caches
* Non-persistent caching
* Cache load/save/delete hooks w/ defaults
* Cache validation hooks
* Cache builder hooks
* Dependent invalidation

## How to use

### Setting up a simple persistent cache
    from cacheman import cacher

    manager = cacher.get_cache_manager() # Optional manager name argument can be used here
    cache = manager.register_cache('my_simple_cache') # You now have a cache!
    print cache.get('my_key') # `None` first run, 'my_value' if this code was executed earlier
    cache['my_key'] = 'my_value'
    manager.save_cache_contents('my_simple_cache') # Changes are now persisted to disk

### Non-persistent caches
    from cacheman import cacher

    manager = cacher.get_cache_manager()
    cache = manager.register_cache('my_simple_cache', persistent=False) # You cache won't save to disk
    manager.save_cache_contents('my_cache') # This is a no-op

### Registering hooks
    from cacheman import cacher

    def my_saver(cache_name, contents):
        print("Save requested on {} cache content: {}".format(cache_name, contents))

    def my_loader(cache_name):
        return { 'load': 'faked' }

    manager = cacher.get_cache_manager()
    manager.register_saver('my_cache', my_saver)
    manager.register_loader('my_cache', my_loader)

    cache = manager.retrieve_cache('my_cache')
    manager.save_cache_contents('my_cache') # Will print 'Save ... : { 'load': 'faked' }'
    cache['new'] = 'real' # Add something to the cache
    manager.save_cache_contents('my_cache') # Will print 'Save ... : { 'load': 'faked', 'new': 'real' }'

### Dependent caches
    from cacheman import cacher

    manager = cacher.get_cache_manager()
    manager.register_dependent_cache('edge_cache', 'root_cache')
    root_cache = manager.register_cache('root_cache')

    def get_processed_value():
        # Computes and caches 'processed' from root's 'raw' value
        edge = manager.retrieve_cache('edge_cache')
        processed = edge.get('processed')
        if processed is None:
            root = manager.retrieve_cache('root_cache')
            processed = (root.get('raw') or 0) * 5
            edge['processed'] = processed
        return processed

    # A common problem with caching computed or dependent values:
    print get_processed_value() # 0 without raw value
    manager.retrieve_cache('root_cache')['raw'] = 1
    print get_processed_value() # still 0 because it's cache in edge

    # Now we use cache invalidation to tell downstream caches they're no longer valid
    manager.invalidate_cache('root_cache') # Invalidates dependent caches
    print manager.retrieve_cache('edge_cache') # Prints {} even though we only invalidated 'root_cache'
    manager.retrieve_cache('root_cache')['raw'] = 1
    print get_processed_value() # Now 5 because the edge was cleared before the request

### Setting cache directory
    manager = cacher.get_cache_manager()
    # Default cache directory is '/tmp/general_cacher' or 'user\appadata\local\temp\general_cache'
    manager.set_cache_directory('secret/cache/location') # All pickle caches now save here

    cache = manager.register_cache('my_cache')
    cache['new'] = 'real' # Add something to the cache
    manager.save_cache_contents('my_cache') # Will save contents to 'secret/cache/location/my_cache.pkl'

## Navigating the Repo
### cacheman
The cach mana

### tests
All unit tests for the repo.

## Language Preferences
* Google Style Guide
* Object Oriented (with a few exceptions)

## Author
Author(s): Matthew Seal

#### (C) Copyright 2013, [Opengov](http://opengov.com)

from collections import MutableMapping

class IgnoredDict(MutableMapping):
    '''
    A dictionary that never holds any content.
    '''
    def __getitem__(self, key):
        return {}.__getitem__(key)

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        {}.__delitem__(key)

    def __contains__(self, key):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return {}.__iter__()

    def __bool__(self):
        return False # Always return truey because we can't determine length
    __nonzero__ = __bool__

class SetAsDictWrap(MutableMapping):
    def __init__(self, wrapped_set):
        self.wrapped_set = wrapped_set

    def __getitem__(self, key):
        return None

    def __setitem__(self, key, value):
        self.wrapped_set.add(key)

    def __iter__(self):
        return self.wrapped_set.__iter__()

    def __len__(self):
        return self.wrapped_set.__len__()

    def __delitem__(self, key):
        self.wrapped_set.__delitem__(key)

    def __contains__(self, key):
        return self.wrapped_set.__contains__(key)

    def __getattr__(self, name):
        '''
        If a method or attribute is missing, use the content's attributes
        '''
        for getter in ['__getattribute__', '__getattr__']:
            if hasattr(self.wrapped_set, getter):
                try:
                    return getattr(self.wrapped_set, getter)(name)
                except AttributeError:
                    pass
        raise AttributeError("'{}' and '{}' objects have no attribute '{}'".format(
            self.__class__.__name__, self.wrapped_set.__class__.__name__, name))

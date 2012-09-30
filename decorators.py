#!/usr/bin/env python


class RequiresType(object):
    """
    Checks that the first (or position given by the keyword argument 'position'
    argument to the function is an instance of one of the types given in the
    positional decorator arguments
    """

    def __init__(self, *types, **kwargs):
        self.types = types
        self.position = 0
        if 'position' in kwargs:
            self.position = int(kwargs['position']) - 1

    def __call__(self, f):
        def wrapped_f(*args, **kwargs):
            if type(args[self.position]) not in self.types:
                raise TypeError("Invalid argument type '%s' at position %d. " + 
                        "Expected one of (%s)" % (
                            type(args[self.position]).__name__, self.position,
                            ", ".join([t.__name__ for t in self.types])))
            return f(*args, **kwargs)
        return wrapped_f

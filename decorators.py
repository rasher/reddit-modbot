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
        self.returnvalue = False
        if 'position' in kwargs:
            self.position = int(kwargs['position']) - 1
        if 'returnvalue' in kwargs:
            self.returnvalue = kwargs['returnvalue']

    def __call__(self, f):
        def wrapped_f(*args, **kwargs):
            if type(args[self.position]) not in self.types:
                return self.returnvalue
            return f(*args, **kwargs)
        return wrapped_f

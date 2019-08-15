import inspect
import wsme.api

APIPATH_MAXLEN = 20


class expose(object):
    def __init__(self, *args, **kwargs):
        self.signature = wsme.api.signature(*args, **kwargs)

    def __call__(self, func):
        return self.signature(func)

    @classmethod
    def with_method(cls, method, *args, **kwargs):
        kwargs['method'] = method
        return cls(*args, **kwargs)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.with_method('GET', *args, **kwargs)

    @classmethod
    def post(cls, *args, **kwargs):
        return cls.with_method('POST', *args, **kwargs)

    @classmethod
    def put(cls, *args, **kwargs):
        return cls.with_method('PUT', *args, **kwargs)

    @classmethod
    def delete(cls, *args, **kwargs):
        return cls.with_method('DELETE', *args, **kwargs)


class validate(object):
    """
    Decorator that define the arguments types of a function.


    Example::

        class MyController(object):
            @expose(str)
            @validate(datetime.date, datetime.time)
            def format(self, d, t):
                return d.isoformat() + ' ' + t.isoformat()
    """
    def __init__(self, *param_types):
        self.param_types = param_types

    def __call__(self, func):
        argspec = wsme.api.getargspec(func)
        fd = wsme.api.FunctionDefinition.get(func)
        fd.set_arg_types(argspec, self.param_types)
        return func


def scan_api(controller, path=[], objects=[]):
    """
    Recursively iterate a controller api entries.
    """
    for name in dir(controller):
        if name.startswith('_'):
            continue
        a = getattr(controller, name)
        if a in objects:
            continue
        if inspect.ismethod(a):
            if wsme.api.iswsmefunction(a):
                yield path + [name], a, []
        elif inspect.isclass(a):
            continue
        else:
            if len(path) > APIPATH_MAXLEN:
                raise ValueError("Path is too long: " + str(path))
            for i in scan_api(a, path + [name], objects + [a]):
                yield i

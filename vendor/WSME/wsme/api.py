import traceback
import functools
import inspect
import logging
import six

import wsme.exc
import wsme.types

from wsme import utils

log = logging.getLogger(__name__)


def iswsmefunction(f):
    return hasattr(f, '_wsme_definition')


def wrapfunc(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    wrapper._wsme_original_func = f
    return wrapper


def getargspec(f):
    f = getattr(f, '_wsme_original_func', f)
    return inspect.getargspec(f)


class FunctionArgument(object):
    """
    An argument definition of an api entry
    """
    def __init__(self, name, datatype, mandatory, default):
        #: argument name
        self.name = name

        #: Data type
        self.datatype = datatype

        #: True if the argument is mandatory
        self.mandatory = mandatory

        #: Default value if argument is omitted
        self.default = default

    def resolve_type(self, registry):
        self.datatype = registry.resolve_type(self.datatype)


class FunctionDefinition(object):
    """
    An api entry definition
    """
    def __init__(self, func):
        #: Function name
        self.name = func.__name__

        #: Function documentation
        self.doc = func.__doc__

        #: Return type
        self.return_type = None

        #: The function arguments (list of :class:`FunctionArgument`)
        self.arguments = []

        #: If the body carry the datas of a single argument, its type
        self.body_type = None

        #: Status code
        self.status_code = 200

        #: True if extra arguments should be ignored, NOT inserted in
        #: the kwargs of the function and not raise UnknownArgument
        #: exceptions
        self.ignore_extra_args = False

        #: name of the function argument to pass the host request object.
        #: Should be set by using the :class:`wsme.types.HostRequest` type
        #: in the function @\ :function:`signature`
        self.pass_request = False

        #: Dictionnary of protocol-specific options.
        self.extra_options = None

    @staticmethod
    def get(func):
        """
        Returns the :class:`FunctionDefinition` of a method.
        """
        if not hasattr(func, '_wsme_definition'):
            fd = FunctionDefinition(func)
            func._wsme_definition = fd

        return func._wsme_definition

    def get_arg(self, name):
        """
        Returns a :class:`FunctionArgument` from its name
        """
        for arg in self.arguments:
            if arg.name == name:
                return arg
        return None

    def resolve_types(self, registry):
        self.return_type = registry.resolve_type(self.return_type)
        self.body_type = registry.resolve_type(self.body_type)
        for arg in self.arguments:
            arg.resolve_type(registry)

    def set_options(self, body=None, ignore_extra_args=False, status_code=200,
                    rest_content_types=('json', 'xml'), **extra_options):
        self.body_type = body
        self.status_code = status_code
        self.ignore_extra_args = ignore_extra_args
        self.rest_content_types = rest_content_types
        self.extra_options = extra_options

    def set_arg_types(self, argspec, arg_types):
        args, varargs, keywords, defaults = argspec
        if args[0] == 'self':
            args = args[1:]
        arg_types = list(arg_types)
        if self.body_type is not None:
            arg_types.append(self.body_type)
        for i, argname in enumerate(args):
            datatype = arg_types[i]
            mandatory = defaults is None or i < (len(args) - len(defaults))
            default = None
            if not mandatory:
                default = defaults[i - (len(args) - len(defaults))]
            if datatype is wsme.types.HostRequest:
                self.pass_request = argname
            else:
                self.arguments.append(FunctionArgument(argname, datatype,
                                                       mandatory, default))


class signature(object):

    """Decorator that specify the argument types of an exposed function.

    :param return_type: Type of the value returned by the function
    :param argN: Type of the Nth argument
    :param body: If the function takes a final argument that is supposed to be
                 the request body by itself, its type.
    :param status_code: HTTP return status code of the function.
    :param ignore_extra_args: Allow extra/unknow arguments (default to False)

    Most of the time this decorator is not supposed to be used directly,
    unless you are not using WSME on top of another framework.

    If an adapter is used, it will provide either a specialised version of this
    decororator, either a new decorator named @wsexpose that takes the same
    parameters (it will in addition expose the function, hence its name).
    """

    def __init__(self, *types, **options):
        self.return_type = types[0] if types else None
        self.arg_types = []
        if len(types) > 1:
            self.arg_types.extend(types[1:])
        if 'body' in options:
            self.arg_types.append(options['body'])
        self.wrap = options.pop('wrap', False)
        self.options = options

    def __call__(self, func):
        argspec = getargspec(func)
        if self.wrap:
            func = wrapfunc(func)
        fd = FunctionDefinition.get(func)
        if fd.extra_options is not None:
            raise ValueError("This function is already exposed")
        fd.return_type = self.return_type
        fd.set_options(**self.options)
        if self.arg_types:
                fd.set_arg_types(argspec, self.arg_types)
        return func


sig = signature


class Response(object):
    """
    Object to hold the "response" from a view function
    """
    def __init__(self, obj, status_code=None, error=None,
                 return_type=wsme.types.Unset):
        #: Store the result object from the view
        self.obj = obj

        #: Store an optional status_code
        self.status_code = status_code

        #: Return error details
        #: Must be a dictionnary with the following keys: faultcode,
        #: faultstring and an optional debuginfo
        self.error = error

        #: Return type
        #: Type of the value returned by the function
        #: If the return type is wsme.types.Unset it will be ignored
        #: and the default return type will prevail.
        self.return_type = return_type


def format_exception(excinfo, debug=False):
    """Extract informations that can be sent to the client."""
    error = excinfo[1]
    code = getattr(error, 'code', None)
    if code and utils.is_valid_code(code) and utils.is_client_error(code):
        faultstring = (error.faultstring if hasattr(error, 'faultstring')
                       else six.text_type(error))
        r = dict(faultcode="Client",
                 faultstring=faultstring)
        log.debug("Client-side error: %s" % r['faultstring'])
        r['debuginfo'] = None
        return r
    else:
        faultstring = six.text_type(error)
        debuginfo = "\n".join(traceback.format_exception(*excinfo))

        log.error('Server-side error: "%s". Detail: \n%s' % (
            faultstring, debuginfo))

        r = dict(faultcode="Server", faultstring=faultstring)
        if debug:
            r['debuginfo'] = debuginfo
        else:
            r['debuginfo'] = None
        return r

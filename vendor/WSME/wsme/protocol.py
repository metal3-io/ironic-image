import weakref

import pkg_resources

from wsme.exc import ClientSideError


__all__ = [
    'CallContext',

    'register_protocol', 'getprotocol',
]

registered_protocols = {}


def _cfg(f):
    cfg = getattr(f, '_cfg', None)
    if cfg is None:
        f._cfg = cfg = {}
    return cfg


class expose(object):
    def __init__(self, path, content_type):
        self.path = path
        self.content_type = content_type

    def __call__(self, func):
        func.exposed = True
        cfg = _cfg(func)
        cfg['content-type'] = self.content_type
        cfg.setdefault('paths', []).append(self.path)
        return func


class CallContext(object):
    def __init__(self, request):
        self._request = weakref.ref(request)
        self.path = None

        self.func = None
        self.funcdef = None

    @property
    def request(self):
        return self._request()


class ObjectDict(object):
    def __init__(self, obj):
        self.obj = obj

    def __getitem__(self, name):
        return getattr(self.obj, name)


class Protocol(object):
    name = None
    displayname = None
    content_types = []

    def resolve_path(self, path):
        if '$' in path:
            from string import Template
            s = Template(path)
            path = s.substitute(ObjectDict(self))
        return path

    def iter_routes(self):
        for attrname in dir(self):
            attr = getattr(self, attrname)
            if getattr(attr, 'exposed', False):
                for path in _cfg(attr)['paths']:
                    yield self.resolve_path(path), attr

    def accept(self, request):
        return request.headers.get('Content-Type') in self.content_types

    def iter_calls(self, request):
        pass

    def extract_path(self, context):
        pass

    def read_arguments(self, context):
        pass

    def encode_result(self, context, result):
        pass

    def encode_sample_value(self, datatype, value, format=False):
        return ('none', 'N/A')

    def encode_sample_params(self, params, format=False):
        return ('none', 'N/A')

    def encode_sample_result(self, datatype, value, format=False):
        return ('none', 'N/A')


def register_protocol(protocol):
    registered_protocols[protocol.name] = protocol


def getprotocol(name, **options):
    protocol_class = registered_protocols.get(name)
    if protocol_class is None:
        for entry_point in pkg_resources.iter_entry_points(
                'wsme.protocols', name):
            if entry_point.name == name:
                protocol_class = entry_point.load()
        if protocol_class is None:
            raise ValueError("Cannot find protocol '%s'" % name)
        registered_protocols[name] = protocol_class
    return protocol_class(**options)


def media_type_accept(request, content_types):
    """Validate media types against request.method.

    When request.method is GET or HEAD compare with the Accept header.
    When request.method is POST, PUT or PATCH compare with the Content-Type
    header.
    When request.method is DELETE media type is irrelevant, so return True.
    """
    if request.method in ['GET', 'HEAD']:
        if request.accept:
            if request.accept.best_match(content_types):
                return True
            error_message = ('Unacceptable Accept type: %s not in %s'
                             % (request.accept, content_types))
            raise ClientSideError(error_message, status_code=406)
    elif request.method in ['PUT', 'POST', 'PATCH']:
        content_type = request.headers.get('Content-Type')
        if content_type:
            for ct in content_types:
                if request.headers.get('Content-Type', '').startswith(ct):
                    return True
            error_message = ('Unacceptable Content-Type: %s not in %s'
                             % (content_type, content_types))
            raise ClientSideError(error_message, status_code=415)
        else:
            raise ClientSideError('missing Content-Type header')
    elif request.method in ['DELETE']:
        return True
    return False

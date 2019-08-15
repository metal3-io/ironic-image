"""
WSME for cornice


Activate it::

    config.include('wsme.cornice')


And use it::

    @hello.get()
    @wsexpose(Message, wsme.types.text)
    def get_hello(who=u'World'):
        return Message(text='Hello %s' % who)
"""
from __future__ import absolute_import

import inspect
import sys

import wsme
from wsme.rest import json as restjson
from wsme.rest import xml as restxml
import wsme.runtime
import wsme.api
import functools

from wsme.rest.args import (
    args_from_args, args_from_params, args_from_body, combine_args
)


class WSMEJsonRenderer(object):
    def __init__(self, info):
        pass

    def __call__(self, data, context):
        response = context['request'].response
        response.content_type = 'application/json'
        if 'faultcode' in data:
            if 'orig_code' in data:
                response.status_code = data['orig_code']
            elif data['faultcode'] == 'Client':
                response.status_code = 400
            else:
                response.status_code = 500
            return restjson.encode_error(None, data)
        obj = data['result']
        if isinstance(obj, wsme.api.Response):
            response.status_code = obj.status_code
            if obj.error:
                return restjson.encode_error(None, obj.error)
            obj = obj.obj
        return restjson.encode_result(obj, data['datatype'])


class WSMEXmlRenderer(object):
    def __init__(self, info):
        pass

    def __call__(self, data, context):
        response = context['request'].response
        if 'faultcode' in data:
            if data['faultcode'] == 'Client':
                response.status_code = 400
            else:
                response.status_code = 500
            return restxml.encode_error(None, data)
        response.content_type = 'text/xml'
        return restxml.encode_result(data['result'], data['datatype'])


def get_outputformat(request):
    df = None
    if 'Accept' in request.headers:
        if 'application/json' in request.headers['Accept']:
            df = 'json'
        elif 'text/xml' in request.headers['Accept']:
            df = 'xml'
    if df is None and 'Content-Type' in request.headers:
        if 'application/json' in request.headers['Content-Type']:
            df = 'json'
        elif 'text/xml' in request.headers['Content-Type']:
            df = 'xml'
    return df if df else 'json'


def signature(*args, **kwargs):
    sig = wsme.signature(*args, **kwargs)

    def decorate(f):
        args = inspect.getargspec(f)[0]
        with_self = args[0] == 'self' if args else False
        f = sig(f)
        funcdef = wsme.api.FunctionDefinition.get(f)
        funcdef.resolve_types(wsme.types.registry)

        @functools.wraps(f)
        def callfunction(*args):
            if with_self:
                if len(args) == 1:
                    self = args[0]
                    request = self.request
                elif len(args) == 2:
                    self, request = args
                else:
                    raise ValueError("Cannot do anything with these arguments")
            else:
                request = args[0]
            request.override_renderer = 'wsme' + get_outputformat(request)
            try:
                args, kwargs = combine_args(funcdef, (
                    args_from_args(funcdef, (), request.matchdict),
                    args_from_params(funcdef, request.params),
                    args_from_body(funcdef, request.body, request.content_type)
                ))
                wsme.runtime.check_arguments(funcdef, args, kwargs)
                if funcdef.pass_request:
                    kwargs[funcdef.pass_request] = request
                if with_self:
                    args.insert(0, self)

                result = f(*args, **kwargs)
                return {
                    'datatype': funcdef.return_type,
                    'result': result
                }
            except Exception:
                try:
                    exception_info = sys.exc_info()
                    orig_exception = exception_info[1]
                    orig_code = getattr(orig_exception, 'code', None)
                    data = wsme.api.format_exception(exception_info)
                    if orig_code is not None:
                        data['orig_code'] = orig_code
                    return data
                finally:
                    del exception_info

        callfunction.wsme_func = f
        return callfunction
    return decorate


def scan_api(root=None):
    from cornice.service import get_services
    for service in get_services():
        for method, func, options in service.definitions:
            wsme_func = getattr(func, 'wsme_func')
            basepath = service.path.split('/')
            if basepath and not basepath[0]:
                del basepath[0]
            if wsme_func:
                yield (
                    basepath + [method.lower()],
                    wsme_func._wsme_definition
                )


def includeme(config):
    import pyramid.wsgi
    wsroot = wsme.WSRoot(scan_api=scan_api, webpath='/ws')
    wsroot.addprotocol('extdirect')
    config.add_renderer('wsmejson', WSMEJsonRenderer)
    config.add_renderer('wsmexml', WSMEXmlRenderer)
    config.add_route('wsme', '/ws/*path')
    config.add_view(pyramid.wsgi.wsgiapp(wsroot.wsgiapp()), route_name='wsme')

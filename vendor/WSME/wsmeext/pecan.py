from __future__ import absolute_import

import functools
import inspect
import sys

import wsme
import wsme.rest.args
import wsme.rest.json
import wsme.rest.xml

import pecan

from wsme.utils import is_valid_code


class JSonRenderer(object):
    @staticmethod
    def __init__(path, extra_vars):
        pass

    @staticmethod
    def render(template_path, namespace):
        if 'faultcode' in namespace:
            return wsme.rest.json.encode_error(None, namespace)
        return wsme.rest.json.encode_result(
            namespace['result'],
            namespace['datatype']
        )


class XMLRenderer(object):
    @staticmethod
    def __init__(path, extra_vars):
        pass

    @staticmethod
    def render(template_path, namespace):
        if 'faultcode' in namespace:
            return wsme.rest.xml.encode_error(None, namespace)
        return wsme.rest.xml.encode_result(
            namespace['result'],
            namespace['datatype']
        )


pecan.templating._builtin_renderers['wsmejson'] = JSonRenderer
pecan.templating._builtin_renderers['wsmexml'] = XMLRenderer

pecan_json_decorate = pecan.expose(
    template='wsmejson:',
    content_type='application/json',
    generic=False)
pecan_xml_decorate = pecan.expose(
    template='wsmexml:',
    content_type='application/xml',
    generic=False
)
pecan_text_xml_decorate = pecan.expose(
    template='wsmexml:',
    content_type='text/xml',
    generic=False
)


def wsexpose(*args, **kwargs):
    sig = wsme.signature(*args, **kwargs)

    def decorate(f):
        sig(f)
        funcdef = wsme.api.FunctionDefinition.get(f)
        funcdef.resolve_types(wsme.types.registry)

        @functools.wraps(f)
        def callfunction(self, *args, **kwargs):
            return_type = funcdef.return_type

            try:
                args, kwargs = wsme.rest.args.get_args(
                    funcdef, args, kwargs, pecan.request.params, None,
                    pecan.request.body, pecan.request.content_type
                )
                if funcdef.pass_request:
                    kwargs[funcdef.pass_request] = pecan.request
                result = f(self, *args, **kwargs)

                # NOTE: Support setting of status_code with default 201
                pecan.response.status = funcdef.status_code
                if isinstance(result, wsme.api.Response):
                    pecan.response.status = result.status_code

                    # NOTE(lucasagomes): If the return code is 204
                    # (No Response) we have to make sure that we are not
                    # returning anything in the body response and the
                    # content-length is 0
                    if result.status_code == 204:
                        return_type = None
                    elif not isinstance(result.return_type,
                                        wsme.types.UnsetType):
                        return_type = result.return_type

                    result = result.obj

            except Exception:
                try:
                    exception_info = sys.exc_info()
                    orig_exception = exception_info[1]
                    orig_code = getattr(orig_exception, 'code', None)
                    data = wsme.api.format_exception(
                        exception_info,
                        pecan.conf.get('wsme', {}).get('debug', False)
                    )
                finally:
                    del exception_info

                if orig_code and is_valid_code(orig_code):
                    pecan.response.status = orig_code
                else:
                    pecan.response.status = 500

                return data

            if return_type is None:
                pecan.request.pecan['content_type'] = None
                pecan.response.content_type = None
                return ''

            return dict(
                datatype=return_type,
                result=result
            )

        if 'xml' in funcdef.rest_content_types:
            pecan_xml_decorate(callfunction)
            pecan_text_xml_decorate(callfunction)
        if 'json' in funcdef.rest_content_types:
            pecan_json_decorate(callfunction)
        pecan.util._cfg(callfunction)['argspec'] = inspect.getargspec(f)
        callfunction._wsme_definition = funcdef
        return callfunction

    return decorate

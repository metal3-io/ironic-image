from __future__ import absolute_import

import functools
import logging
import sys
import inspect

import wsme
import wsme.api
import wsme.rest.json
import wsme.rest.xml
import wsme.rest.args
from wsme.utils import is_valid_code

import flask

log = logging.getLogger(__name__)


TYPES = {
    'application/json': wsme.rest.json,
    'application/xml': wsme.rest.xml,
    'text/xml': wsme.rest.xml
}


def get_dataformat():
    if 'Accept' in flask.request.headers:
        for t in TYPES:
            if t in flask.request.headers['Accept']:
                return TYPES[t]

    # Look for the wanted data format in the request.
    req_dataformat = getattr(flask.request, 'response_type', None)
    if req_dataformat in TYPES:
        return TYPES[req_dataformat]

    log.info('''Could not determine what format is wanted by the
             caller, falling back to json''')
    return wsme.rest.json


def signature(*args, **kw):
    sig = wsme.signature(*args, **kw)

    def decorator(f):
        args = inspect.getargspec(f)[0]
        ismethod = args and args[0] == 'self'
        sig(f)
        funcdef = wsme.api.FunctionDefinition.get(f)
        funcdef.resolve_types(wsme.types.registry)

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if ismethod:
                self, args = args[0], args[1:]
            args, kwargs = wsme.rest.args.get_args(
                funcdef, args, kwargs,
                flask.request.args, flask.request.form,
                flask.request.data,
                flask.request.mimetype
            )

            if funcdef.pass_request:
                kwargs[funcdef.pass_request] = flask.request

            dataformat = get_dataformat()

            try:
                if ismethod:
                    args = [self] + list(args)
                result = f(*args, **kwargs)

                # NOTE: Support setting of status_code with default 20
                status_code = funcdef.status_code
                if isinstance(result, wsme.api.Response):
                    status_code = result.status_code
                    result = result.obj

                res = flask.make_response(
                    dataformat.encode_result(
                        result,
                        funcdef.return_type
                    )
                )
                res.mimetype = dataformat.content_type
                res.status_code = status_code
            except Exception:
                try:
                    exception_info = sys.exc_info() or None
                    orig_exception = exception_info[1]
                    orig_code = getattr(orig_exception, 'code', None)
                    data = wsme.api.format_exception(exception_info)
                finally:
                    del exception_info

                res = flask.make_response(dataformat.encode_error(None, data))
                if orig_code and is_valid_code(orig_code):
                    res.status_code = orig_code
                elif data['faultcode'].lower() == 'client':
                    res.status_code = 400
                else:
                    res.status_code = 500
            return res

        wrapper.wsme_func = f
        return wrapper
    return decorator

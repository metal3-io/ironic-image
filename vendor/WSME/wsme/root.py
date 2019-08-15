import logging
import sys
import weakref

from six import u, b
import six

import webob

from wsme.exc import ClientSideError, UnknownFunction
from wsme.protocol import getprotocol
from wsme.rest import scan_api
from wsme import spore
import wsme.api
import wsme.types

log = logging.getLogger(__name__)

html_body = u("""
<html>
<head>
  <style type='text/css'>
    %(css)s
  </style>
</head>
<body>
%(content)s
</body>
</html>
""")


def default_prepare_response_body(request, results):
    r = None
    sep = None
    for value in results:
        if sep is None:
            if isinstance(value, six.text_type):
                sep = u('\n')
                r = u('')
            else:
                sep = b('\n')
                r = b('')
        else:
            r += sep
        r += value
    return r


class DummyTransaction:
    def commit(self):
        pass

    def abort(self):
        pass


class WSRoot(object):
    """
    Root controller for webservices.

    :param protocols: A list of protocols to enable (see :meth:`addprotocol`)
    :param webpath: The web path where the webservice is published.

    :type  transaction: A `transaction
                        <http://pypi.python.org/pypi/transaction>`_-like
                        object or ``True``.
    :param transaction: If specified, a transaction will be created and
                        handled on a per-call base.

                        This option *can* be enabled along with `repoze.tm2
                        <http://pypi.python.org/pypi/repoze.tm2>`_
                        (it will only make it void).

                        If ``True``, the default :mod:`transaction`
                        module will be imported and used.

    """
    __registry__ = wsme.types.registry

    def __init__(self, protocols=[], webpath='', transaction=None,
                 scan_api=scan_api):
        self._debug = True
        self._webpath = webpath
        self.protocols = []
        self._scan_api = scan_api

        self._transaction = transaction
        if self._transaction is True:
            import transaction
            self._transaction = transaction

        for protocol in protocols:
            self.addprotocol(protocol)

        self._api = None

    def wsgiapp(self):
        """Returns a wsgi application"""
        from webob.dec import wsgify
        return wsgify(self._handle_request)

    def begin(self):
        if self._transaction:
            return self._transaction.begin()
        else:
            return DummyTransaction()

    def addprotocol(self, protocol, **options):
        """
        Enable a new protocol on the controller.

        :param protocol: A registered protocol name or an instance
                         of a protocol.
        """
        if isinstance(protocol, str):
            protocol = getprotocol(protocol, **options)
        self.protocols.append(protocol)
        protocol.root = weakref.proxy(self)

    def getapi(self):
        """
        Returns the api description.

        :rtype: list of (path, :class:`FunctionDefinition`)
        """
        if self._api is None:
            self._api = [
                (path, f, f._wsme_definition, args)
                for path, f, args in self._scan_api(self)
            ]
            for path, f, fdef, args in self._api:
                fdef.resolve_types(self.__registry__)
        return [
            (path, fdef)
            for path, f, fdef, args in self._api
        ]

    def _get_protocol(self, name):
        for protocol in self.protocols:
            if protocol.name == name:
                return protocol

    def _select_protocol(self, request):
        log.debug("Selecting a protocol for the following request :\n"
                  "headers: %s\nbody: %s", request.headers.items(),
                  request.content_length and (
                      request.content_length > 512 and
                      request.body[:512] or
                      request.body) or '')
        protocol = None
        error = ClientSideError(status_code=406)
        path = str(request.path)
        assert path.startswith(self._webpath)
        path = path[len(self._webpath) + 1:]
        if 'wsmeproto' in request.params:
            return self._get_protocol(request.params['wsmeproto'])
        else:

            for p in self.protocols:
                try:
                    if p.accept(request):
                        protocol = p
                        break
                except ClientSideError as e:
                    error = e
            # If we could not select a protocol, we raise the last exception
            # that we got, or the default one.
            if not protocol:
                raise error
        return protocol

    def _do_call(self, protocol, context):
        request = context.request
        request.calls.append(context)
        try:
            if context.path is None:
                context.path = protocol.extract_path(context)

            if context.path is None:
                raise ClientSideError(u(
                    'The %s protocol was unable to extract a function '
                    'path from the request') % protocol.name)

            context.func, context.funcdef, args = \
                self._lookup_function(context.path)
            kw = protocol.read_arguments(context)
            args = list(args)

            txn = self.begin()
            try:
                result = context.func(*args, **kw)
                txn.commit()
            except Exception:
                txn.abort()
                raise

            else:
                # TODO make sure result type == a._wsme_definition.return_type
                return protocol.encode_result(context, result)

        except Exception as e:
            infos = wsme.api.format_exception(sys.exc_info(), self._debug)
            if isinstance(e, ClientSideError):
                request.client_errorcount += 1
                request.client_last_status_code = e.code
            else:
                request.server_errorcount += 1
            return protocol.encode_error(context, infos)

    def find_route(self, path):
        for p in self.protocols:
            for routepath, func in p.iter_routes():
                if path.startswith(routepath):
                    return routepath, func
        return None, None

    def _handle_request(self, request):
        res = webob.Response()
        res_content_type = None

        path = request.path
        if path.startswith(self._webpath):
            path = path[len(self._webpath):]
        routepath, func = self.find_route(path)
        if routepath:
            content = func()
            if isinstance(content, six.text_type):
                res.text = content
            elif isinstance(content, six.binary_type):
                res.body = content
            res.content_type = func._cfg['content-type']
            return res

        if request.path == self._webpath + '/api.spore':
            res.body = spore.getdesc(self, request.host_url)
            res.content_type = 'application/json'
            return res

        try:
            msg = None
            error_status = 500
            protocol = self._select_protocol(request)
        except ClientSideError as e:
            error_status = e.code
            msg = e.faultstring
            protocol = None
        except Exception as e:
            msg = ("Unexpected error while selecting protocol: %s" % str(e))
            log.exception(msg)
            protocol = None
            error_status = 500

        if protocol is None:
            if not msg:
                msg = ("None of the following protocols can handle this "
                       "request : %s" % ','.join((
                           p.name for p in self.protocols)))
            res.status = error_status
            res.content_type = 'text/plain'
            try:
                res.text = u(msg)
            except TypeError:
                res.text = msg
            log.error(msg)
            return res

        request.calls = []
        request.client_errorcount = 0
        request.client_last_status_code = None
        request.server_errorcount = 0

        try:

            context = None

            if hasattr(protocol, 'prepare_response_body'):
                prepare_response_body = protocol.prepare_response_body
            else:
                prepare_response_body = default_prepare_response_body

            body = prepare_response_body(request, (
                self._do_call(protocol, context)
                for context in protocol.iter_calls(request)))

            if isinstance(body, six.text_type):
                res.text = body
            else:
                res.body = body

            if len(request.calls) == 1:
                if hasattr(protocol, 'get_response_status'):
                    res.status = protocol.get_response_status(request)
                else:
                    if request.client_errorcount == 1:
                        res.status = request.client_last_status_code
                    elif request.client_errorcount:
                        res.status = 400
                    elif request.server_errorcount:
                        res.status = 500
                    else:
                        res.status = 200
            else:
                res.status = protocol.get_response_status(request)
                res_content_type = protocol.get_response_contenttype(request)
        except ClientSideError as e:
            request.server_errorcount += 1
            res.status = e.code
            res.text = e.faultstring
        except Exception:
            infos = wsme.api.format_exception(sys.exc_info(), self._debug)
            request.server_errorcount += 1
            res.text = protocol.encode_error(context, infos)
            res.status = 500

        if res_content_type is None:
            # Attempt to correctly guess what content-type we should return.
            ctypes = [ct for ct in protocol.content_types if ct]
            if ctypes:
                res_content_type = request.accept.best_match(ctypes)

        # If not we will attempt to convert the body to an accepted
        # output format.
        if res_content_type is None:
            if "text/html" in request.accept:
                res.text = self._html_format(res.body, protocol.content_types)
                res_content_type = "text/html"

        # TODO should we consider the encoding asked by
        # the web browser ?
        res.headers['Content-Type'] = "%s; charset=UTF-8" % res_content_type

        return res

    def _lookup_function(self, path):
        if not self._api:
            self.getapi()

        for fpath, f, fdef, args in self._api:
            if path == fpath:
                return f, fdef, args
        raise UnknownFunction('/'.join(path))

    def _html_format(self, content, content_types):
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_for_mimetype
            from pygments.formatters import HtmlFormatter

            lexer = None
            for ct in content_types:
                try:
                    lexer = get_lexer_for_mimetype(ct)
                    break
                except Exception:
                    pass

            if lexer is None:
                raise ValueError("No lexer found")
            formatter = HtmlFormatter()
            return html_body % dict(
                css=formatter.get_style_defs(),
                content=highlight(content, lexer, formatter).encode('utf8'))
        except Exception as e:
            log.warning(
                "Could not pygment the content because of the following "
                "error :\n%s" % e)
            return html_body % dict(
                css='',
                content=u('<pre>%s</pre>') %
                    content.replace(b('>'), b('&gt;'))
                           .replace(b('<'), b('&lt;')))

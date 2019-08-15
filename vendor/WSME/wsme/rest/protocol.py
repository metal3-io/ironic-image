import os.path
import logging

from wsme.utils import OrderedDict
from wsme.protocol import CallContext, Protocol, media_type_accept

import wsme.rest
import wsme.rest.args
import wsme.runtime

log = logging.getLogger(__name__)


class RestProtocol(Protocol):
    name = 'rest'
    displayname = 'REST'
    dataformats = ['json', 'xml']
    content_types = ['application/json', 'text/xml']

    def __init__(self, dataformats=None):
        if dataformats is None:
            dataformats = RestProtocol.dataformats

        self.dataformats = OrderedDict()
        self.content_types = []

        for dataformat in dataformats:
            __import__('wsme.rest.' + dataformat)
            dfmod = getattr(wsme.rest, dataformat)
            self.dataformats[dataformat] = dfmod
            self.content_types.extend(dfmod.accept_content_types)

    def accept(self, request):
        for dataformat in self.dataformats:
            if request.path.endswith('.' + dataformat):
                return True
        return media_type_accept(request, self.content_types)

    def iter_calls(self, request):
        context = CallContext(request)
        context.outformat = None
        ext = os.path.splitext(request.path.split('/')[-1])[1]
        inmime = request.content_type
        outmime = request.accept.best_match(self.content_types)

        outformat = None
        informat = None
        for dfname, df in self.dataformats.items():
            if ext == '.' + dfname:
                outformat = df
                if not inmime:
                    informat = df

        if outformat is None and request.accept:
            for dfname, df in self.dataformats.items():
                if outmime in df.accept_content_types:
                    outformat = df
                    if not inmime:
                        informat = df

        if outformat is None:
            for dfname, df in self.dataformats.items():
                if inmime == df.content_type:
                    outformat = df

        context.outformat = outformat
        context.outformat_options = {
            'nest_result': getattr(self, 'nest_result', False)
        }
        if not inmime and informat:
            inmime = informat.content_type
            log.debug("Inferred input type: %s" % inmime)
        context.inmime = inmime
        yield context

    def extract_path(self, context):
        path = context.request.path
        assert path.startswith(self.root._webpath)
        path = path[len(self.root._webpath):]
        path = path.strip('/').split('/')

        for dataformat in self.dataformats:
            if path[-1].endswith('.' + dataformat):
                path[-1] = path[-1][:-len(dataformat) - 1]

        # Check if the path is actually a function, and if not
        # see if the http method make a difference
        # TODO Re-think the function lookup phases. Here we are
        # doing the job that will be done in a later phase, which
        # is sub-optimal
        for p, fdef in self.root.getapi():
            if p == path:
                return path

        # No function at this path. Now check for function that have
        # this path as a prefix, and declared an http method
        for p, fdef in self.root.getapi():
            if len(p) == len(path) + 1 and p[:len(path)] == path and \
                    fdef.extra_options.get('method') == context.request.method:
                return p

        return path

    def read_arguments(self, context):
        request = context.request
        funcdef = context.funcdef

        body = None
        if request.content_length not in (None, 0, '0'):
            body = request.body
        if not body and '__body__' in request.params:
            body = request.params['__body__']

        args, kwargs = wsme.rest.args.combine_args(
            funcdef,
            (wsme.rest.args.args_from_params(funcdef, request.params),
             wsme.rest.args.args_from_body(funcdef, body, context.inmime))
        )
        wsme.runtime.check_arguments(funcdef, args, kwargs)
        return kwargs

    def encode_result(self, context, result):
        out = context.outformat.encode_result(
            result, context.funcdef.return_type,
            **context.outformat_options
        )
        return out

    def encode_error(self, context, errordetail):
        out = context.outformat.encode_error(
            context, errordetail
        )
        return out

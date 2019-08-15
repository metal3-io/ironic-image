import datetime
import decimal

from simplegeneric import generic

from wsme.exc import ClientSideError
from wsme.protocol import CallContext, Protocol, expose
from wsme.utils import parse_isodate, parse_isodatetime, parse_isotime
from wsme.rest.args import from_params
from wsme.types import iscomplex, isusertype, list_attributes, Unset
import wsme.types

try:
    import simplejson as json
except ImportError:
    import json  # noqa

from six import u


class APIDefinitionGenerator(object):
    tpl = """\
Ext.ns("%(rootns)s");

if (!%(rootns)s.wsroot) {
    %(rootns)s.wsroot = "%(webpath)s.
}

%(descriptors)s

Ext.syncRequire(['Ext.direct.*'], function() {
  %(providers)s
});
"""
    descriptor_tpl = """\
Ext.ns("%(fullns)s");

%(fullns)s.Descriptor = {
    "url": %(rootns)s.wsroot + "extdirect/router/%(ns)s",
    "namespace": "%(fullns)s",
    "type": "remoting",
    "actions": %(actions)s
    "enableBuffer": true
};
"""
    provider_tpl = """\
    Ext.direct.Manager.addProvider(%(fullns)s.Descriptor);
"""

    def __init__(self):
        pass

    def render(self, rootns, webpath, namespaces, fullns):
        descriptors = u('')
        for ns in sorted(namespaces):
            descriptors += self.descriptor_tpl % {
                'ns': ns,
                'rootns': rootns,
                'fullns': fullns(ns),
                'actions': '\n'.join((
                    ' ' * 4 + line
                    for line
                    in json.dumps(namespaces[ns], indent=4).split('\n')
                ))
            }

        providers = u('')
        for ns in sorted(namespaces):
            providers += self.provider_tpl % {
                'fullns': fullns(ns)
            }

        r = self.tpl % {
            'rootns': rootns,
            'webpath': webpath,
            'descriptors': descriptors,
            'providers': providers,
        }
        return r


@generic
def fromjson(datatype, value):
    if value is None:
        return None
    if iscomplex(datatype):
        newvalue = datatype()
        for attrdef in list_attributes(datatype):
            if attrdef.name in value:
                setattr(newvalue, attrdef.key,
                        fromjson(attrdef.datatype, value[attrdef.name]))
        value = newvalue
    elif isusertype(datatype):
        value = datatype.frombasetype(fromjson(datatype.basetype, value))
    return value


@generic
def tojson(datatype, value):
    if value is None:
        return value
    if iscomplex(datatype):
        d = {}
        for attrdef in list_attributes(datatype):
            attrvalue = getattr(value, attrdef.key)
            if attrvalue is not Unset:
                d[attrdef.name] = tojson(attrdef.datatype, attrvalue)
        value = d
    elif isusertype(datatype):
        value = tojson(datatype.basetype, datatype.tobasetype(value))
    return value


@fromjson.when_type(wsme.types.ArrayType)
def array_fromjson(datatype, value):
    return [fromjson(datatype.item_type, item) for item in value]


@tojson.when_type(wsme.types.ArrayType)
def array_tojson(datatype, value):
    if value is None:
        return value
    return [tojson(datatype.item_type, item) for item in value]


@fromjson.when_type(wsme.types.DictType)
def dict_fromjson(datatype, value):
    if value is None:
        return value
    return dict((
        (fromjson(datatype.key_type, key),
            fromjson(datatype.value_type, value))
        for key, value in value.items()
    ))


@tojson.when_type(wsme.types.DictType)
def dict_tojson(datatype, value):
    if value is None:
        return value
    return dict((
        (tojson(datatype.key_type, key),
            tojson(datatype.value_type, value))
        for key, value in value.items()
    ))


@tojson.when_object(wsme.types.bytes)
def bytes_tojson(datatype, value):
    if value is None:
        return value
    return value.decode('ascii')


# raw strings
@fromjson.when_object(wsme.types.bytes)
def bytes_fromjson(datatype, value):
    if value is not None:
        value = value.encode('ascii')
    return value


# unicode strings

@fromjson.when_object(wsme.types.text)
def text_fromjson(datatype, value):
    if isinstance(value, wsme.types.bytes):
        return value.decode('utf-8')
    return value


# datetime.time

@fromjson.when_object(datetime.time)
def time_fromjson(datatype, value):
    if value is None or value == '':
        return None
    return parse_isotime(value)


@tojson.when_object(datetime.time)
def time_tojson(datatype, value):
    if value is None:
        return value
    return value.isoformat()


# datetime.date

@fromjson.when_object(datetime.date)
def date_fromjson(datatype, value):
    if value is None or value == '':
        return None
    return parse_isodate(value)


@tojson.when_object(datetime.date)
def date_tojson(datatype, value):
    if value is None:
        return value
    return value.isoformat()


# datetime.datetime

@fromjson.when_object(datetime.datetime)
def datetime_fromjson(datatype, value):
    if value is None or value == '':
        return None
    return parse_isodatetime(value)


@tojson.when_object(datetime.datetime)
def datetime_tojson(datatype, value):
    if value is None:
        return value
    return value.isoformat()


# decimal.Decimal

@fromjson.when_object(decimal.Decimal)
def decimal_fromjson(datatype, value):
    if value is None:
        return value
    return decimal.Decimal(value)


@tojson.when_object(decimal.Decimal)
def decimal_tojson(datatype, value):
    if value is None:
        return value
    return str(value)


class ExtCallContext(CallContext):
    def __init__(self, request, namespace, calldata):
        super(ExtCallContext, self).__init__(request)
        self.namespace = namespace

        self.tid = calldata['tid']
        self.action = calldata['action']
        self.method = calldata['method']
        self.params = calldata['data']


class FormExtCallContext(CallContext):
    def __init__(self, request, namespace):
        super(FormExtCallContext, self).__init__(request)
        self.namespace = namespace

        self.tid = request.params['extTID']
        self.action = request.params['extAction']
        self.method = request.params['extMethod']
        self.params = []


class ExtDirectProtocol(Protocol):
    """
    ExtDirect protocol.

    For more detail on the protocol, see
    http://www.sencha.com/products/extjs/extdirect.

    .. autoattribute:: name
    .. autoattribute:: content_types
    """
    name = 'extdirect'
    displayname = 'ExtDirect'
    content_types = ['application/json', 'text/javascript']

    def __init__(self, namespace='', params_notation='named', nsfolder=None):
        self.namespace = namespace
        self.appns, self.apins = namespace.rsplit('.', 2) \
            if '.' in namespace else (namespace, '')
        self.default_params_notation = params_notation
        self.appnsfolder = nsfolder

    @property
    def api_alias(self):
        if self.appnsfolder:
            alias = '/%s/%s.js' % (
                self.appnsfolder,
                self.apins.replace('.', '/'))
            return alias

    def accept(self, req):
        path = req.path
        assert path.startswith(self.root._webpath)
        path = path[len(self.root._webpath):]

        return (
            path == self.api_alias or
            path == "/extdirect/api" or
            path.startswith("/extdirect/router")
        )

    def iter_calls(self, req):
        path = req.path

        assert path.startswith(self.root._webpath)
        path = path[len(self.root._webpath):].strip()

        assert path.startswith('/extdirect/router'), path
        path = path[17:].strip('/')

        if path:
            namespace = path.split('.')
        else:
            namespace = []

        if 'extType' in req.params:
            req.wsme_extdirect_batchcall = False
            yield FormExtCallContext(req, namespace)
        else:
            data = json.loads(req.body.decode('utf8'))
            req.wsme_extdirect_batchcall = isinstance(data, list)
            if not req.wsme_extdirect_batchcall:
                data = [data]
            req.callcount = len(data)

            for call in data:
                yield ExtCallContext(req, namespace, call)

    def extract_path(self, context):
        path = list(context.namespace)

        if context.action:
            path.append(context.action)

        path.append(context.method)

        return path

    def read_std_arguments(self, context):
        funcdef = context.funcdef
        notation = funcdef.extra_options.get('extdirect_params_notation',
                                             self.default_params_notation)
        args = context.params
        if notation == 'positional':
            kw = dict(
                (argdef.name, fromjson(argdef.datatype, arg))
                for argdef, arg in zip(funcdef.arguments, args)
            )
        elif notation == 'named':
            if len(args) == 0:
                args = [{}]
            elif len(args) > 1:
                raise ClientSideError(
                    "Named arguments: takes a single object argument")
            args = args[0]
            kw = dict(
                (argdef.name, fromjson(argdef.datatype, args[argdef.name]))
                for argdef in funcdef.arguments if argdef.name in args
            )
        else:
            raise ValueError("Invalid notation: %s" % notation)
        return kw

    def read_form_arguments(self, context):
        kw = {}
        for argdef in context.funcdef.arguments:
            value = from_params(argdef.datatype, context.request.params,
                                argdef.name, set())
            if value is not Unset:
                kw[argdef.name] = value
        return kw

    def read_arguments(self, context):
        if isinstance(context, ExtCallContext):
            kwargs = self.read_std_arguments(context)
        elif isinstance(context, FormExtCallContext):
            kwargs = self.read_form_arguments(context)
        wsme.runtime.check_arguments(context.funcdef, (), kwargs)
        return kwargs

    def encode_result(self, context, result):
        return json.dumps({
            'type': 'rpc',
            'tid': context.tid,
            'action': context.action,
            'method': context.method,
            'result': tojson(context.funcdef.return_type, result)
        })

    def encode_error(self, context, infos):
        return json.dumps({
            'type': 'exception',
            'tid': context.tid,
            'action': context.action,
            'method': context.method,
            'message': '%(faultcode)s: %(faultstring)s' % infos,
            'where': infos['debuginfo']})

    def prepare_response_body(self, request, results):
        r = ",\n".join(results)
        if request.wsme_extdirect_batchcall:
            return "[\n%s\n]" % r
        else:
            return r

    def get_response_status(self, request):
        return 200

    def get_response_contenttype(self, request):
        return "text/javascript"

    def fullns(self, ns):
        return ns and '%s.%s' % (self.namespace, ns) or self.namespace

    @expose('/extdirect/api', "text/javascript")
    @expose('${api_alias}', "text/javascript")
    def api(self):
        namespaces = {}
        for path, funcdef in self.root.getapi():
            if len(path) > 1:
                namespace = '.'.join(path[:-2])
                action = path[-2]
            else:
                namespace = ''
                action = ''
            if namespace not in namespaces:
                namespaces[namespace] = {}
            if action not in namespaces[namespace]:
                namespaces[namespace][action] = []
            notation = funcdef.extra_options.get('extdirect_params_notation',
                                                 self.default_params_notation)
            method = {
                'name': funcdef.name}

            if funcdef.extra_options.get('extdirect_formhandler', False):
                method['formHandler'] = True
            method['len'] = 1 if notation == 'named' \
                else len(funcdef.arguments)
            namespaces[namespace][action].append(method)
        webpath = self.root._webpath
        if webpath and not webpath.endswith('/'):
            webpath += '/'
        return APIDefinitionGenerator().render(
            namespaces=namespaces,
            webpath=webpath,
            rootns=self.namespace,
            fullns=self.fullns,
        )

    def encode_sample_value(self, datatype, value, format=False):
        r = tojson(datatype, value)
        content = json.dumps(r, ensure_ascii=False, indent=4 if format else 0,
                             sort_keys=format)
        return ('javascript', content)

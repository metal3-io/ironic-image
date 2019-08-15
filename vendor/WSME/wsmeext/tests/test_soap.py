import decimal
import datetime
import base64

import six

import wsme.tests.protocol

try:
    import xml.etree.ElementTree as et
except ImportError:
    import cElementTree as et  # noqa

import suds.cache
import suds.client
import suds.transport

import wsme.utils


class XDecimal(suds.xsd.sxbuiltin.XBuiltin):
    def translate(self, value, topython=True):
        if topython:
            if isinstance(value, six.string_types) and len(value):
                return decimal.Decimal(value)
        else:
            if isinstance(value, (decimal.Decimal, int, float)):
                return str(value)
            return value


suds.xsd.sxbuiltin.Factory.tags['decimal'] = XDecimal


class WebtestSudsTransport(suds.transport.Transport):
    def __init__(self, app):
        suds.transport.Transport.__init__(self)
        self.app = app

    def open(self, request):
        res = self.app.get(request.url, headers=request.headers)
        return six.BytesIO(res.body)

    def send(self, request):
        res = self.app.post(
            request.url,
            request.message,
            headers=dict((
                (key, str(value)) for key, value in request.headers.items()
            )),
            expect_errors=True
        )
        return suds.transport.Reply(
            res.status_int,
            dict(res.headers),
            res.body
        )


class SudsCache(suds.cache.Cache):
    def __init__(self):
        self.d = {}

    def get(self, id):
        return self.d.get(id)

    def getf(self, id):
        b = self.get(id)
        if b is not None:
            return six.StringIO(self.get(id))

    def put(self, id, bfr):
        self.d[id] = bfr

    def putf(self, id, fp):
        self.put(id, fp.read())

    def purge(self, id):
        try:
            del self.d[id]
        except KeyError:
            pass

    def clear(self, id):
        self.d = {}


sudscache = SudsCache()

tns = "http://foo.bar.baz/soap/"
typenamespace = "http://foo.bar.baz/types/"

soapenv_ns = 'http://schemas.xmlsoap.org/soap/envelope/'
xsi_ns = 'http://www.w3.org/2001/XMLSchema-instance'
body_qn = '{%s}Body' % soapenv_ns
fault_qn = '{%s}Fault' % soapenv_ns
faultcode_qn = '{%s}faultcode' % soapenv_ns
faultstring_qn = '{%s}faultstring' % soapenv_ns
faultdetail_qn = '{%s}detail' % soapenv_ns
type_qn = '{%s}type' % xsi_ns
nil_qn = '{%s}nil' % xsi_ns


def build_soap_message(method, params=""):
    message = """<?xml version="1.0"?>
<soap:Envelope
xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
soap:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">

  <soap:Body xmlns="%(typenamespace)s">
    <%(method)s>
        %(params)s
    </%(method)s>
  </soap:Body>

</soap:Envelope>
""" % dict(method=method, params=params, typenamespace=typenamespace)
    return message


python_types = {
    int: ('xs:int', str),
    float: ('xs:float', str),
    bool: ('xs:boolean', str),
    wsme.types.bytes: (
        'xs:string',
        lambda x: x.decode('ascii') if isinstance(x, wsme.types.bytes) else x
    ),
    wsme.types.text: ('xs:string', wsme.types.text),
    wsme.types.binary: (
        'xs:base64Binary',
        lambda x: base64.encodestring(x).decode('ascii')
    ),
    decimal.Decimal: ('xs:decimal', str),
    datetime.date: ('xs:date', datetime.date.isoformat),
    datetime.time: ('xs:time', datetime.time.isoformat),
    datetime.datetime: ('xs:dateTime', datetime.datetime.isoformat),
}

array_types = {
    wsme.types.bytes: "String_Array",
    wsme.types.text: "String_Array",
    int: "Int_Array",
    float: "Float_Array",
    bool: "Boolean_Array",
    datetime.datetime: "dateTime_Array"
}

if not six.PY3:
    array_types[long] = "Long_Array"  # noqa


def tosoap(tag, value):
    el = et.Element(tag)
    if isinstance(value, tuple):
        value, datatype = value
    else:
        datatype = type(value)
    if value is None:
        el.set('xsi:nil', 'true')
        return el
    if datatype in python_types:
        stype, conv = python_types[datatype]
        el.text = conv(value)
        el.set('xsi:type', stype)
    el.text = str(value)
    return el


def tosuds(client, value):
    if value is None:
        return None
    if isinstance(value, tuple):
        value, datatype = value
    else:
        datatype = type(value)
    if value is None:
        return None
    if isinstance(datatype, list):
        if datatype[0] in array_types:
            tname = array_types[datatype[0]]
        else:
            tname = datatype[0].__name__ + '_Array'
        o = client.factory.create('types:' + tname)
        o.item = [tosuds(client, (item, datatype[0])) for item in value]
        return o
    elif datatype in python_types:
        return python_types[datatype][1](value)
    else:
        o = client.factory.create('types:' + datatype.__name__)

        for attr in datatype._wsme_attributes:
            if attr.name in value:
                setattr(
                    o, attr.name,
                    tosuds(client, (value[attr.name], attr.datatype))
                )
        return o


def read_bool(value):
    return value == 'true'


soap_types = {
    'xs:string': wsme.types.text,
    'xs:int': int,
    'xs:long': int if six.PY3 else long,  # noqa
    'xs:float': float,
    'xs:decimal': decimal.Decimal,
    'xs:boolean': read_bool,
    'xs:date': wsme.utils.parse_isodate,
    'xs:time': wsme.utils.parse_isotime,
    'xs:dateTime': wsme.utils.parse_isodatetime,
    'xs:base64Binary': base64.decodestring,
}


def fromsoap(el):
    if el.get(nil_qn) == 'true':
        return None
    t = el.get(type_qn)
    if t == 'xs:string':
        return wsme.types.text(el.text if el.text else '')
    if t in soap_types:
        return soap_types[t](el.text)
    elif t and t.endswith('_Array'):
        return [fromsoap(i) for i in el]
    else:
        d = {}
        for child in el:
            name = child.tag
            assert name.startswith('{%s}' % typenamespace), name
            name = name[len(typenamespace) + 2:]
            d[name] = fromsoap(child)
        return d


def tobytes(value):
    if isinstance(value, wsme.types.text):
        value = value.encode()
    return value


def tobin(value):
    value = base64.decodestring(value.encode())
    return value


fromsuds_types = {
    wsme.types.binary: tobin,
    wsme.types.bytes: tobytes,
    decimal.Decimal: decimal.Decimal,
}


def fromsuds(dt, value):
    if value is None:
        return None
    if isinstance(dt, list):
        return [fromsuds(dt[0], item) for item in value.item]
    if wsme.types.isarray(dt):
        return [fromsuds(dt.item_type, item) for item in value.item]
    if wsme.types.isusertype(dt) and dt not in fromsuds_types:
        dt = dt.basetype
    if dt in fromsuds_types:
        print(dt, value)
        value = fromsuds_types[dt](value)
        print(value)
        return value
    if wsme.types.iscomplex(dt):
        d = {}
        for attrdef in dt._wsme_attributes:
            if not hasattr(value, attrdef.name):
                continue
            d[attrdef.name] = fromsuds(
                attrdef.datatype, getattr(value, attrdef.name)
            )
        return d
    return value


class TestSOAP(wsme.tests.protocol.ProtocolTestCase):
    protocol = 'soap'
    protocol_options = dict(tns=tns, typenamespace=typenamespace)
    ws_path = '/'
    _sudsclient = None

    def setUp(self):
        wsme.tests.protocol.ProtocolTestCase.setUp(self)

    def test_simple_call(self):
        message = build_soap_message('touch')
        print(message)
        res = self.app.post(
            self.ws_path,
            message,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            expect_errors=True
        )
        print(res.body)
        assert res.status.startswith('200')

    def call(self, fpath, _rt=None, _accept=None, _no_result_decode=False,
             **kw):

        if _no_result_decode or _accept or self._testMethodName in (
            'test_missing_argument', 'test_invalid_path', 'test_settext_empty',
            'test_settext_none'
        ):
            return self.raw_call(fpath, _rt, _accept, _no_result_decode, **kw)

        path = fpath.strip('/').split('/')
        methodname = ''.join([path[0]] + [i.capitalize() for i in path[1:]])

        m = getattr(self.sudsclient.service, methodname)
        kw = dict((
            (key, tosuds(self.sudsclient, value)) for key, value in kw.items()
        ))
        print(kw)
        try:
            return fromsuds(_rt, m(**kw))
        except suds.WebFault as exc:
            raise wsme.tests.protocol.CallException(
                exc.fault.faultcode,
                exc.fault.faultstring,
                getattr(exc.fault, 'detail', None) or None
            )

    def raw_call(self, fpath, _rt=None, _accept=None, _no_result_decode=False,
                 **kw):
        path = fpath.strip('/').split('/')
        methodname = ''.join([path[0]] + [i.capitalize() for i in path[1:]])
        # get the actual definition so we can build the adequate request
        if kw:
            el = et.Element('parameters')
            for key, value in kw.items():
                el.append(tosoap(key, value))

            params = six.b("\n").join(et.tostring(el) for el in el)
        else:
            params = ""
        methodname = ''.join([path[0]] + [i.capitalize() for i in path[1:]])
        message = build_soap_message(methodname, params)
        print(message)
        headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
        if _accept is not None:
            headers['Accept'] = _accept
        res = self.app.post(
            self.ws_path,
            message,
            headers=headers,
            expect_errors=True
        )
        print("Status: ", res.status, "Received:", res.body)

        if _no_result_decode:
            return res

        el = et.fromstring(res.body)
        body = el.find(body_qn)
        print(body)

        if res.status_int == 200:
            response_tag = '{%s}%sResponse' % (typenamespace, methodname)
            r = body.find(response_tag)
            result = r.find('{%s}result' % typenamespace)
            print("Result element: ", result)
            return fromsoap(result)
        elif res.status_int == 400:
            fault = body.find(fault_qn)
            raise wsme.tests.protocol.CallException(
                fault.find(faultcode_qn).text,
                fault.find(faultstring_qn).text,
                "")

        elif res.status_int == 500:
            fault = body.find(fault_qn)
            raise wsme.tests.protocol.CallException(
                fault.find(faultcode_qn).text,
                fault.find(faultstring_qn).text,
                fault.find(faultdetail_qn) is not None and
                fault.find(faultdetail_qn).text or None)

    @property
    def sudsclient(self):
        if self._sudsclient is None:
            self._sudsclient = suds.client.Client(
                self.ws_path + 'api.wsdl',
                transport=WebtestSudsTransport(self.app),
                cache=sudscache
            )
        return self._sudsclient

    def test_wsdl(self):
        c = self.sudsclient
        assert c.wsdl.tns[1] == tns, c.wsdl.tns

        sd = c.sd[0]

        assert len(sd.ports) == 1
        port, methods = sd.ports[0]
        self.assertEqual(len(methods), 51)

        methods = dict(methods)

        assert 'returntypesGettext' in methods
        print(methods)

        assert methods['argtypesSettime'][0][0] == 'value'

    def test_return_nesteddict(self):
        pass

    def test_setnesteddict(self):
        pass

    def test_return_objectdictattribute(self):
        pass

    def test_setnested_nullobj(self):
        pass  # TODO write a soap adapted version of this test.

import decimal
import datetime
import base64

from six import u, b
import six

import wsme.tests.protocol
from wsme.utils import parse_isodatetime, parse_isodate, parse_isotime
from wsme.types import isarray, isdict, isusertype, register_type

from wsme.rest.xml import fromxml, toxml

try:
    import xml.etree.ElementTree as et
except ImportError:
    import cElementTree as et  # noqa


def dumpxml(key, obj, datatype=None):
    el = et.Element(key)
    if isinstance(obj, tuple):
        obj, datatype = obj
    if isinstance(datatype, list):
        for item in obj:
            el.append(dumpxml('item', item, datatype[0]))
    elif isinstance(datatype, dict):
        key_type, value_type = list(datatype.items())[0]
        for item in obj.items():
            node = et.SubElement(el, 'item')
            node.append(dumpxml('key', item[0], key_type))
            node.append(dumpxml('value', item[1], value_type))
    elif datatype == wsme.types.binary:
        el.text = base64.encodestring(obj).decode('ascii')
    elif isinstance(obj, wsme.types.bytes):
        el.text = obj.decode('ascii')
    elif isinstance(obj, wsme.types.text):
        el.text = obj
    elif type(obj) in (int, float, bool, decimal.Decimal):
        el.text = six.text_type(obj)
    elif type(obj) in (datetime.date, datetime.time, datetime.datetime):
        el.text = obj.isoformat()
    elif isinstance(obj, type(None)):
        el.set('nil', 'true')
    elif hasattr(datatype, '_wsme_attributes'):
        for attr in datatype._wsme_attributes:
            name = attr.name
            if name not in obj:
                continue
            o = obj[name]
            el.append(dumpxml(name, o, attr.datatype))
    elif type(obj) == dict:
        for name, value in obj.items():
            el.append(dumpxml(name, value))
    print(obj, datatype, et.tostring(el))
    return el


def loadxml(el, datatype):
    print(el, datatype, len(el))
    if el.get('nil') == 'true':
        return None
    if isinstance(datatype, list):
        return [loadxml(item, datatype[0]) for item in el.findall('item')]
    elif isarray(datatype):
        return [
            loadxml(item, datatype.item_type) for item in el.findall('item')
        ]
    elif isinstance(datatype, dict):
        key_type, value_type = list(datatype.items())[0]
        return dict((
            (loadxml(item.find('key'), key_type),
                loadxml(item.find('value'), value_type))
            for item in el.findall('item')
        ))
    elif isdict(datatype):
        return dict((
            (loadxml(item.find('key'), datatype.key_type),
                loadxml(item.find('value'), datatype.value_type))
            for item in el.findall('item')
        ))
    elif isdict(datatype):
        return dict((
            (loadxml(item.find('key'), datatype.key_type),
                loadxml(item.find('value'), datatype.value_type))
            for item in el.findall('item')
        ))
    elif len(el):
        d = {}
        for attr in datatype._wsme_attributes:
            name = attr.name
            child = el.find(name)
            print(name, attr, child)
            if child is not None:
                d[name] = loadxml(child, attr.datatype)
        print(d)
        return d
    else:
        if datatype == wsme.types.binary:
            return base64.decodestring(el.text.encode('ascii'))
        if isusertype(datatype):
            datatype = datatype.basetype
        if datatype == datetime.date:
            return parse_isodate(el.text)
        if datatype == datetime.time:
            return parse_isotime(el.text)
        if datatype == datetime.datetime:
            return parse_isodatetime(el.text)
        if datatype == wsme.types.text:
            return datatype(el.text if el.text else u(''))
        if datatype == bool:
            return el.text.lower() != 'false'
        if datatype is None:
            return el.text
        if datatype is wsme.types.bytes:
            return el.text.encode('ascii')
        return datatype(el.text)


class TestRestXML(wsme.tests.protocol.RestOnlyProtocolTestCase):
    protocol = 'restxml'

    def call(self, fpath, _rt=None, _accept=None, _no_result_decode=False,
             body=None, **kw):
        if body:
            el = dumpxml('body', body)
        else:
            el = dumpxml('parameters', kw)
        content = et.tostring(el)
        headers = {
            'Content-Type': 'text/xml',
        }
        if _accept is not None:
            headers['Accept'] = _accept
        res = self.app.post(
            '/' + fpath,
            content,
            headers=headers,
            expect_errors=True)
        print("Received:", res.body)

        if _no_result_decode:
            return res

        el = et.fromstring(res.body)
        if el.tag == 'error':
            raise wsme.tests.protocol.CallException(
                el.find('faultcode').text,
                el.find('faultstring').text,
                el.find('debuginfo') is not None and
                el.find('debuginfo').text or None
            )

        else:
            return loadxml(et.fromstring(res.body), _rt)

    def test_encode_sample_value(self):
        class MyType(object):
            aint = int
            atext = wsme.types.text

        register_type(MyType)

        value = MyType()
        value.aint = 5
        value.atext = u('test')

        language, sample = wsme.rest.xml.encode_sample_value(
            MyType, value, True)
        print(language, sample)

        assert language == 'xml'
        assert sample == b("""<value>
  <aint>5</aint>
  <atext>test</atext>
</value>""")

    def test_encode_sample_params(self):
        lang, content = wsme.rest.xml.encode_sample_params(
            [('a', int, 2)], True)
        assert lang == 'xml', lang
        assert content == b('<parameters>\n  <a>2</a>\n</parameters>'), content

    def test_encode_sample_result(self):
        lang, content = wsme.rest.xml.encode_sample_result(int, 2, True)
        assert lang == 'xml', lang
        assert content == b('<result>2</result>'), content

    def test_nil_fromxml(self):
        for dt in (
                str, [int], {int: str}, bool,
                datetime.date, datetime.time, datetime.datetime):
            e = et.Element('value', nil='true')
            assert fromxml(dt, e) is None

    def test_nil_toxml(self):
        for dt in (
                wsme.types.bytes,
                [int], {int: str}, bool,
                datetime.date, datetime.time, datetime.datetime):
            x = et.tostring(toxml(dt, 'value', None))
            assert x == b('<value nil="true" />'), x

    def test_unset_attrs(self):
        class AType(object):
            someattr = wsme.types.bytes

        wsme.types.register_type(AType)

        x = et.tostring(toxml(AType, 'value', AType()))
        assert x == b('<value />'), x

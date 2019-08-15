# coding=utf-8

import unittest
import warnings
import datetime
import decimal
import six

from six import u, b

from webtest import TestApp

from wsme import WSRoot, Unset
from wsme import expose, validate
import wsme.types
import wsme.utils

warnings.filterwarnings('ignore', module='webob.dec')

binarysample = b('\x00\xff\x43')

try:
    1 / 0
except ZeroDivisionError as e:
    zerodivisionerrormsg = str(e)


class CallException(RuntimeError):
    def __init__(self, faultcode, faultstring, debuginfo):
        self.faultcode = faultcode
        self.faultstring = faultstring
        self.debuginfo = debuginfo

    def __str__(self):
        return 'faultcode=%s, faultstring=%s, debuginfo=%s' % (
            self.faultcode, self.faultstring, self.debuginfo
        )


myenumtype = wsme.types.Enum(wsme.types.bytes, 'v1', 'v2')


class NestedInner(object):
    aint = int

    def __init__(self, aint=None):
        self.aint = aint


class NestedOuter(object):
    inner = NestedInner
    inner_array = wsme.types.wsattr([NestedInner])
    inner_dict = {wsme.types.text: NestedInner}

    def __init__(self):
        self.inner = NestedInner(0)


class NamedAttrsObject(object):
    def __init__(self, v1=Unset, v2=Unset):
        self.attr_1 = v1
        self.attr_2 = v2

    attr_1 = wsme.types.wsattr(int, name='attr.1')
    attr_2 = wsme.types.wsattr(int, name='attr.2')


class CustomObject(object):
    aint = int
    name = wsme.types.text


class ExtendedInt(wsme.types.UserType):
    basetype = int
    name = "Extended integer"


class NestedInnerApi(object):
    @expose(bool)
    def deepfunction(self):
        return True


class NestedOuterApi(object):
    inner = NestedInnerApi()


class ReturnTypes(object):
    @expose(wsme.types.bytes)
    def getbytes(self):
        return b("astring")

    @expose(wsme.types.text)
    def gettext(self):
        return u('\xe3\x81\xae')

    @expose(int)
    def getint(self):
        return 2

    @expose(float)
    def getfloat(self):
        return 3.14159265

    @expose(decimal.Decimal)
    def getdecimal(self):
        return decimal.Decimal('3.14159265')

    @expose(datetime.date)
    def getdate(self):
        return datetime.date(1994, 1, 26)

    @expose(bool)
    def getbooltrue(self):
        return True

    @expose(bool)
    def getboolfalse(self):
        return False

    @expose(datetime.time)
    def gettime(self):
        return datetime.time(12, 0, 0)

    @expose(datetime.datetime)
    def getdatetime(self):
        return datetime.datetime(1994, 1, 26, 12, 0, 0)

    @expose(wsme.types.binary)
    def getbinary(self):
        return binarysample

    @expose(NestedOuter)
    def getnested(self):
        n = NestedOuter()
        return n

    @expose([wsme.types.bytes])
    def getbytesarray(self):
        return [b("A"), b("B"), b("C")]

    @expose([NestedOuter])
    def getnestedarray(self):
        return [NestedOuter(), NestedOuter()]

    @expose({wsme.types.bytes: NestedOuter})
    def getnesteddict(self):
        return {b('a'): NestedOuter(), b('b'): NestedOuter()}

    @expose(NestedOuter)
    def getobjectarrayattribute(self):
        obj = NestedOuter()
        obj.inner_array = [NestedInner(12), NestedInner(13)]
        return obj

    @expose(NestedOuter)
    def getobjectdictattribute(self):
        obj = NestedOuter()
        obj.inner_dict = {
            '12': NestedInner(12),
            '13': NestedInner(13)
        }
        return obj

    @expose(myenumtype)
    def getenum(self):
        return b('v2')

    @expose(NamedAttrsObject)
    def getnamedattrsobj(self):
        return NamedAttrsObject(5, 6)


class ArgTypes(object):
    def assertEqual(self, a, b):
        if not (a == b):
            raise AssertionError('%s != %s' % (a, b))

    def assertIsInstance(self, value, v_type):
        assert isinstance(value, v_type), ("%s is not instance of type %s" %
                                           (value, v_type))

    @expose(wsme.types.bytes)
    @validate(wsme.types.bytes)
    def setbytes(self, value):
        print(repr(value))
        self.assertEqual(type(value), wsme.types.bytes)
        return value

    @expose(wsme.types.text)
    @validate(wsme.types.text)
    def settext(self, value):
        print(repr(value))
        self.assertEqual(type(value), wsme.types.text)
        return value

    @expose(wsme.types.text)
    @validate(wsme.types.text)
    def settextnone(self, value):
        print(repr(value))
        self.assertEqual(type(value), type(None))
        return value

    @expose(bool)
    @validate(bool)
    def setbool(self, value):
        print(repr(value))
        self.assertEqual(type(value), bool)
        return value

    @expose(int)
    @validate(int)
    def setint(self, value):
        print(repr(value))
        self.assertEqual(type(value), int)
        return value

    @expose(float)
    @validate(float)
    def setfloat(self, value):
        print(repr(value))
        self.assertEqual(type(value), float)
        return value

    @expose(decimal.Decimal)
    @validate(decimal.Decimal)
    def setdecimal(self, value):
        print(repr(value))
        self.assertEqual(type(value), decimal.Decimal)
        return value

    @expose(datetime.date)
    @validate(datetime.date)
    def setdate(self, value):
        print(repr(value))
        self.assertEqual(type(value), datetime.date)
        return value

    @expose(datetime.time)
    @validate(datetime.time)
    def settime(self, value):
        print(repr(value))
        self.assertEqual(type(value), datetime.time)
        return value

    @expose(datetime.datetime)
    @validate(datetime.datetime)
    def setdatetime(self, value):
        print(repr(value))
        self.assertEqual(type(value), datetime.datetime)
        return value

    @expose(wsme.types.binary)
    @validate(wsme.types.binary)
    def setbinary(self, value):
        print(repr(value))
        self.assertEqual(type(value), six.binary_type)
        return value

    @expose([wsme.types.bytes])
    @validate([wsme.types.bytes])
    def setbytesarray(self, value):
        print(repr(value))
        self.assertEqual(type(value), list)
        self.assertEqual(type(value[0]), wsme.types.bytes)
        return value

    @expose([wsme.types.text])
    @validate([wsme.types.text])
    def settextarray(self, value):
        print(repr(value))
        self.assertEqual(type(value), list)
        self.assertEqual(type(value[0]), wsme.types.text)
        return value

    @expose([datetime.datetime])
    @validate([datetime.datetime])
    def setdatetimearray(self, value):
        print(repr(value))
        self.assertEqual(type(value), list)
        self.assertEqual(type(value[0]), datetime.datetime)
        return value

    @expose(NestedOuter)
    @validate(NestedOuter)
    def setnested(self, value):
        print(repr(value))
        self.assertEqual(type(value), NestedOuter)
        return value

    @expose([NestedOuter])
    @validate([NestedOuter])
    def setnestedarray(self, value):
        print(repr(value))
        self.assertEqual(type(value), list)
        self.assertEqual(type(value[0]), NestedOuter)
        return value

    @expose({wsme.types.bytes: NestedOuter})
    @validate({wsme.types.bytes: NestedOuter})
    def setnesteddict(self, value):
        print(repr(value))
        self.assertEqual(type(value), dict)
        self.assertEqual(type(list(value.keys())[0]), wsme.types.bytes)
        self.assertEqual(type(list(value.values())[0]), NestedOuter)
        return value

    @expose(myenumtype)
    @validate(myenumtype)
    def setenum(self, value):
        print(value)
        self.assertEqual(type(value), wsme.types.bytes)
        return value

    @expose(NamedAttrsObject)
    @validate(NamedAttrsObject)
    def setnamedattrsobj(self, value):
        print(value)
        self.assertEqual(type(value), NamedAttrsObject)
        self.assertEqual(value.attr_1, 10)
        self.assertEqual(value.attr_2, 20)
        return value

    @expose(CustomObject)
    @validate(CustomObject)
    def setcustomobject(self, value):
        self.assertIsInstance(value, CustomObject)
        self.assertIsInstance(value.name, wsme.types.text)
        self.assertIsInstance(value.aint, int)
        return value

    @expose(ExtendedInt())
    @validate(ExtendedInt())
    def setextendedint(self, value):
        self.assertEqual(isinstance(value, ExtendedInt.basetype), True)
        return value


class BodyTypes(object):
    def assertEqual(self, a, b):
        if not (a == b):
            raise AssertionError('%s != %s' % (a, b))

    @expose(int, body={wsme.types.text: int})
    @validate(int)
    def setdict(self, body):
        print(body)
        self.assertEqual(type(body), dict)
        self.assertEqual(type(body['test']), int)
        self.assertEqual(body['test'], 10)
        return body['test']

    @expose(int, body=[int])
    @validate(int)
    def setlist(self, body):
        print(body)
        self.assertEqual(type(body), list)
        self.assertEqual(type(body[0]), int)
        self.assertEqual(body[0], 10)
        return body[0]


class WithErrors(object):
    @expose()
    def divide_by_zero(self):
        1 / 0


class MiscFunctions(object):
    @expose(int)
    @validate(int, int)
    def multiply(self, a, b):
        return a * b


class WSTestRoot(WSRoot):
    argtypes = ArgTypes()
    returntypes = ReturnTypes()
    bodytypes = BodyTypes()
    witherrors = WithErrors()
    nested = NestedOuterApi()
    misc = MiscFunctions()

    def reset(self):
        self._touched = False

    @expose()
    def touch(self):
        self._touched = True


class ProtocolTestCase(unittest.TestCase):
    protocol_options = {}

    def assertTypedEquals(self, a, b, convert):
        if isinstance(a, six.string_types):
            a = convert(a)
        if isinstance(b, six.string_types):
            b = convert(b)
        self.assertEqual(a, b)

    def assertDateEquals(self, a, b):
        self.assertTypedEquals(a, b, wsme.utils.parse_isodate)

    def assertTimeEquals(self, a, b):
        self.assertTypedEquals(a, b, wsme.utils.parse_isotime)

    def assertDateTimeEquals(self, a, b):
        self.assertTypedEquals(a, b, wsme.utils.parse_isodatetime)

    def assertIntEquals(self, a, b):
        self.assertTypedEquals(a, b, int)

    def assertFloatEquals(self, a, b):
        self.assertTypedEquals(a, b, float)

    def assertDecimalEquals(self, a, b):
        self.assertTypedEquals(a, b, decimal.Decimal)

    def setUp(self):
        if self.__class__.__name__ != 'ProtocolTestCase':
            self.root = WSTestRoot()
            self.root.getapi()
            self.root.addprotocol(self.protocol, **self.protocol_options)

            self.app = TestApp(self.root.wsgiapp())

    def test_invalid_path(self):
        try:
            res = self.call('invalid_function')
            print(res)
            assert "No error raised"
        except CallException as e:
            self.assertEqual(e.faultcode, 'Client')
            self.assertEqual(e.faultstring.lower(),
                             u('unknown function name: invalid_function'))

    def test_serverside_error(self):
        try:
            res = self.call('witherrors/divide_by_zero')
            print(res)
            assert "No error raised"
        except CallException as e:
            self.assertEqual(e.faultcode, 'Server')
            self.assertEqual(e.faultstring, zerodivisionerrormsg)
            assert e.debuginfo is not None

    def test_serverside_error_nodebug(self):
        self.root._debug = False
        try:
            res = self.call('witherrors/divide_by_zero')
            print(res)
            assert "No error raised"
        except CallException as e:
            self.assertEqual(e.faultcode, 'Server')
            self.assertEqual(e.faultstring, zerodivisionerrormsg)
            assert e.debuginfo is None

    def test_touch(self):
        r = self.call('touch')
        assert r is None, r

    def test_return_bytes(self):
        r = self.call('returntypes/getbytes', _rt=wsme.types.bytes)
        self.assertEqual(r, b('astring'))

    def test_return_text(self):
        r = self.call('returntypes/gettext', _rt=wsme.types.text)
        self.assertEqual(r, u('\xe3\x81\xae'))

    def test_return_int(self):
        r = self.call('returntypes/getint')
        self.assertIntEquals(r, 2)

    def test_return_float(self):
        r = self.call('returntypes/getfloat')
        self.assertFloatEquals(r, 3.14159265)

    def test_return_decimal(self):
        r = self.call('returntypes/getdecimal')
        self.assertDecimalEquals(r, '3.14159265')

    def test_return_bool_true(self):
        r = self.call('returntypes/getbooltrue', _rt=bool)
        assert r

    def test_return_bool_false(self):
        r = self.call('returntypes/getboolfalse', _rt=bool)
        assert not r

    def test_return_date(self):
        r = self.call('returntypes/getdate')
        self.assertDateEquals(r, datetime.date(1994, 1, 26))

    def test_return_time(self):
        r = self.call('returntypes/gettime')
        self.assertTimeEquals(r, datetime.time(12))

    def test_return_datetime(self):
        r = self.call('returntypes/getdatetime')
        self.assertDateTimeEquals(r, datetime.datetime(1994, 1, 26, 12))

    def test_return_binary(self):
        r = self.call('returntypes/getbinary', _rt=wsme.types.binary)
        self.assertEqual(r, binarysample)

    def test_return_nested(self):
        r = self.call('returntypes/getnested', _rt=NestedOuter)
        self.assertEqual(r, {'inner': {'aint': 0}})

    def test_return_bytesarray(self):
        r = self.call('returntypes/getbytesarray', _rt=[six.binary_type])
        self.assertEqual(r, [b('A'), b('B'), b('C')])

    def test_return_nestedarray(self):
        r = self.call('returntypes/getnestedarray', _rt=[NestedOuter])
        self.assertEqual(r, [{'inner': {'aint': 0}}, {'inner': {'aint': 0}}])

    def test_return_nesteddict(self):
        r = self.call('returntypes/getnesteddict',
                      _rt={wsme.types.bytes: NestedOuter})
        self.assertEqual(r, {
            b('a'): {'inner': {'aint': 0}},
            b('b'): {'inner': {'aint': 0}}
        })

    def test_return_objectarrayattribute(self):
        r = self.call('returntypes/getobjectarrayattribute', _rt=NestedOuter)
        self.assertEqual(r, {
            'inner': {'aint': 0},
            'inner_array': [{'aint': 12}, {'aint': 13}]
        })

    def test_return_objectdictattribute(self):
        r = self.call('returntypes/getobjectdictattribute', _rt=NestedOuter)
        self.assertEqual(r, {
            'inner': {'aint': 0},
            'inner_dict': {
                '12': {'aint': 12},
                '13': {'aint': 13}
            }
        })

    def test_return_enum(self):
        r = self.call('returntypes/getenum', _rt=myenumtype)
        self.assertEqual(r, b('v2'), r)

    def test_return_namedattrsobj(self):
        r = self.call('returntypes/getnamedattrsobj', _rt=NamedAttrsObject)
        self.assertEqual(r, {'attr.1': 5, 'attr.2': 6})

    def test_setbytes(self):
        assert self.call('argtypes/setbytes', value=b('astring'),
                         _rt=wsme.types.bytes) == b('astring')

    def test_settext(self):
        assert self.call('argtypes/settext', value=u('\xe3\x81\xae'),
                         _rt=wsme.types.text) == u('\xe3\x81\xae')

    def test_settext_empty(self):
        assert self.call('argtypes/settext', value=u(''),
                         _rt=wsme.types.text) == u('')

    def test_settext_none(self):
        self.assertEqual(
            None,
            self.call('argtypes/settextnone', value=None, _rt=wsme.types.text)
        )

    def test_setint(self):
        r = self.call('argtypes/setint', value=3, _rt=int)
        self.assertEqual(r, 3)

    def test_setfloat(self):
        assert self.call('argtypes/setfloat', value=3.54,
                         _rt=float) == 3.54

    def test_setbool_true(self):
        r = self.call('argtypes/setbool', value=True, _rt=bool)
        assert r

    def test_setbool_false(self):
        r = self.call('argtypes/setbool', value=False, _rt=bool)
        assert not r

    def test_setdecimal(self):
        value = decimal.Decimal('3.14')
        assert self.call('argtypes/setdecimal', value=value,
                         _rt=decimal.Decimal) == value

    def test_setdate(self):
        value = datetime.date(2008, 4, 6)
        r = self.call('argtypes/setdate', value=value,
                      _rt=datetime.date)
        self.assertEqual(r, value)

    def test_settime(self):
        value = datetime.time(12, 12, 15)
        r = self.call('argtypes/settime', value=value,
                      _rt=datetime.time)
        self.assertEqual(r, datetime.time(12, 12, 15))

    def test_setdatetime(self):
        value = datetime.datetime(2008, 4, 6, 12, 12, 15)
        r = self.call('argtypes/setdatetime', value=value,
                      _rt=datetime.datetime)
        self.assertEqual(r, datetime.datetime(2008, 4, 6, 12, 12, 15))

    def test_setbinary(self):
        value = binarysample
        r = self.call('argtypes/setbinary', value=(value, wsme.types.binary),
                      _rt=wsme.types.binary) == value
        print(r)

    def test_setnested(self):
        value = {'inner': {'aint': 54}}
        r = self.call('argtypes/setnested',
                      value=(value, NestedOuter),
                      _rt=NestedOuter)
        self.assertEqual(r, value)

    def test_setnested_nullobj(self):
        value = {'inner': None}
        r = self.call(
            'argtypes/setnested',
            value=(value, NestedOuter),
            _rt=NestedOuter
        )
        self.assertEqual(r, value)

    def test_setbytesarray(self):
        value = [b("1"), b("2"), b("three")]
        r = self.call('argtypes/setbytesarray',
                      value=(value, [wsme.types.bytes]),
                      _rt=[wsme.types.bytes])
        self.assertEqual(r, value)

    def test_settextarray(self):
        value = [u("1")]
        r = self.call('argtypes/settextarray',
                      value=(value, [wsme.types.text]),
                      _rt=[wsme.types.text])
        self.assertEqual(r, value)

    def test_setdatetimearray(self):
        value = [
            datetime.datetime(2008, 3, 6, 12, 12, 15),
            datetime.datetime(2008, 4, 6, 2, 12, 15),
        ]
        r = self.call('argtypes/setdatetimearray',
                      value=(value, [datetime.datetime]),
                      _rt=[datetime.datetime])
        self.assertEqual(r, value)

    def test_setnestedarray(self):
        value = [
            {'inner': {'aint': 54}},
            {'inner': {'aint': 55}},
        ]
        r = self.call('argtypes/setnestedarray',
                      value=(value, [NestedOuter]),
                      _rt=[NestedOuter])
        self.assertEqual(r, value)

    def test_setnesteddict(self):
        value = {
            b('o1'): {'inner': {'aint': 54}},
            b('o2'): {'inner': {'aint': 55}},
        }
        r = self.call('argtypes/setnesteddict',
                      value=(value, {six.binary_type: NestedOuter}),
                      _rt={six.binary_type: NestedOuter})
        print(r)
        self.assertEqual(r, value)

    def test_setenum(self):
        value = b('v1')
        r = self.call('argtypes/setenum', value=value,
                      _rt=myenumtype)
        self.assertEqual(r, value)

    def test_setnamedattrsobj(self):
        value = {'attr.1': 10, 'attr.2': 20}
        r = self.call('argtypes/setnamedattrsobj',
                      value=(value, NamedAttrsObject),
                      _rt=NamedAttrsObject)
        self.assertEqual(r, value)

    def test_nested_api(self):
        r = self.call('nested/inner/deepfunction', _rt=bool)
        assert r is True

    def test_missing_argument(self):
        try:
            r = self.call('argtypes/setdatetime')
            print(r)
            assert "No error raised"
        except CallException as e:
            self.assertEqual(e.faultcode, 'Client')
            self.assertEqual(e.faultstring, u('Missing argument: "value"'))

    def test_misc_multiply(self):
        self.assertEqual(self.call('misc/multiply', a=5, b=2, _rt=int), 10)

    def test_html_format(self):
        res = self.call('argtypes/setdatetime', _accept="text/html",
                        _no_result_decode=True)
        self.assertEqual(res.content_type, 'text/html')


class RestOnlyProtocolTestCase(ProtocolTestCase):
    def test_body_list(self):
        r = self.call('bodytypes/setlist', body=([10], [int]), _rt=int)
        self.assertEqual(r, 10)

    def test_body_dict(self):
        r = self.call('bodytypes/setdict',
                      body=({'test': 10}, {wsme.types.text: int}),
                      _rt=int)
        self.assertEqual(r, 10)

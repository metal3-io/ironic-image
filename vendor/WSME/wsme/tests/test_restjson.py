import base64
import datetime
import decimal

import wsme.tests.protocol

try:
    import simplejson as json
except ImportError:
    import json  # noqa

from wsme.rest.json import fromjson, tojson, parse
from wsme.utils import parse_isodatetime, parse_isotime, parse_isodate
from wsme.types import isarray, isdict, isusertype, register_type
from wsme.types import UserType, ArrayType, DictType
from wsme.rest import expose, validate
from wsme.exc import ClientSideError, InvalidInput


import six
from six import b, u

if six.PY3:
    from urllib.parse import urlencode
else:
    from urllib import urlencode  # noqa


def prepare_value(value, datatype):
    if isinstance(datatype, list):
        return [prepare_value(item, datatype[0]) for item in value]
    if isinstance(datatype, dict):
        key_type, value_type = list(datatype.items())[0]
        return dict((
            (prepare_value(item[0], key_type),
                prepare_value(item[1], value_type))
            for item in value.items()
        ))
    if datatype in (datetime.date, datetime.time, datetime.datetime):
        return value.isoformat()
    if datatype == decimal.Decimal:
        return str(value)
    if datatype == wsme.types.binary:
        return base64.encodestring(value).decode('ascii')
    if datatype == wsme.types.bytes:
        return value.decode('ascii')
    return value


def prepare_result(value, datatype):
    print(value, datatype)
    if value is None:
        return None
    if datatype == wsme.types.binary:
        return base64.decodestring(value.encode('ascii'))
    if isusertype(datatype):
        datatype = datatype.basetype
    if isinstance(datatype, list):
        return [prepare_result(item, datatype[0]) for item in value]
    if isarray(datatype):
        return [prepare_result(item, datatype.item_type) for item in value]
    if isinstance(datatype, dict):
        return dict((
            (prepare_result(item[0], list(datatype.keys())[0]),
                prepare_result(item[1], list(datatype.values())[0]))
            for item in value.items()
        ))
    if isdict(datatype):
        return dict((
            (prepare_result(item[0], datatype.key_type),
                prepare_result(item[1], datatype.value_type))
            for item in value.items()
        ))
    if datatype == datetime.date:
        return parse_isodate(value)
    if datatype == datetime.time:
        return parse_isotime(value)
    if datatype == datetime.datetime:
        return parse_isodatetime(value)
    if hasattr(datatype, '_wsme_attributes'):
        for attr in datatype._wsme_attributes:
            if attr.key not in value:
                continue
            value[attr.key] = prepare_result(value[attr.key], attr.datatype)
        return value
    if datatype == wsme.types.bytes:
        return value.encode('ascii')
    if type(value) != datatype:
        print(type(value), datatype)
        return datatype(value)
    return value


class CustomInt(UserType):
    basetype = int
    name = "custom integer"


class Obj(wsme.types.Base):
    id = int
    name = wsme.types.text


class NestedObj(wsme.types.Base):
    o = Obj


class CRUDResult(object):
    data = Obj
    message = wsme.types.text

    def __init__(self, data=wsme.types.Unset, message=wsme.types.Unset):
        self.data = data
        self.message = message


class MiniCrud(object):
    @expose(CRUDResult, method='PUT')
    @validate(Obj)
    def create(self, data):
        print(repr(data))
        return CRUDResult(data, u('create'))

    @expose(CRUDResult, method='GET', ignore_extra_args=True)
    @validate(Obj)
    def read(self, ref):
        print(repr(ref))
        if ref.id == 1:
            ref.name = u('test')
        return CRUDResult(ref, u('read'))

    @expose(CRUDResult, method='POST')
    @validate(Obj)
    def update(self, data):
        print(repr(data))
        return CRUDResult(data, u('update'))

    @expose(CRUDResult, wsme.types.text, body=Obj)
    def update_with_body(self, msg, data):
        print(repr(data))
        return CRUDResult(data, msg)

    @expose(CRUDResult, method='DELETE')
    @validate(Obj)
    def delete(self, ref):
        print(repr(ref))
        if ref.id == 1:
            ref.name = u('test')
        return CRUDResult(ref, u('delete'))


wsme.tests.protocol.WSTestRoot.crud = MiniCrud()


class TestRestJson(wsme.tests.protocol.RestOnlyProtocolTestCase):
    protocol = 'restjson'

    def call(self, fpath, _rt=None, _accept=None, _no_result_decode=False,
             body=None, **kw):
        if body:
            if isinstance(body, tuple):
                body, datatype = body
            else:
                datatype = type(body)
            body = prepare_value(body, datatype)
            content = json.dumps(body)
        else:
            for key in kw:
                if isinstance(kw[key], tuple):
                    value, datatype = kw[key]
                else:
                    value = kw[key]
                    datatype = type(value)
                kw[key] = prepare_value(value, datatype)
            content = json.dumps(kw)
        headers = {
            'Content-Type': 'application/json',
        }
        if _accept is not None:
            headers["Accept"] = _accept
        res = self.app.post(
            '/' + fpath,
            content,
            headers=headers,
            expect_errors=True)
        print("Received:", res.body)

        if _no_result_decode:
            return res

        r = json.loads(res.text)
        if res.status_int == 200:
            if _rt and r:
                r = prepare_result(r, _rt)
            return r
        else:
            raise wsme.tests.protocol.CallException(
                r['faultcode'],
                r['faultstring'],
                r.get('debuginfo')
            )

        return json.loads(res.text)

    def test_fromjson(self):
        assert fromjson(str, None) is None

    def test_keyargs(self):
        r = self.app.get('/argtypes/setint.json?value=2')
        print(r)
        assert json.loads(r.text) == 2

        nestedarray = 'value[0].inner.aint=54&value[1].inner.aint=55'
        r = self.app.get('/argtypes/setnestedarray.json?' + nestedarray)
        print(r)
        assert json.loads(r.text) == [
            {'inner': {'aint': 54}},
            {'inner': {'aint': 55}}]

    def test_form_urlencoded_args(self):
        params = {
            'value[0].inner.aint': 54,
            'value[1].inner.aint': 55
        }
        body = urlencode(params)
        r = self.app.post(
            '/argtypes/setnestedarray.json',
            body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        print(r)

        assert json.loads(r.text) == [
            {'inner': {'aint': 54}},
            {'inner': {'aint': 55}}]

    def test_body_and_params(self):
        r = self.app.post('/argtypes/setint.json?value=2', '{"value": 2}',
                          headers={"Content-Type": "application/json"},
                          expect_errors=True)
        print(r)
        assert r.status_int == 400
        assert json.loads(r.text)['faultstring'] == \
            "Parameter value was given several times"

    def test_inline_body(self):
        params = urlencode({'__body__': '{"value": 4}'})
        r = self.app.get('/argtypes/setint.json?' + params)
        print(r)
        assert json.loads(r.text) == 4

    def test_empty_body(self):
        params = urlencode({'__body__': ''})
        r = self.app.get('/returntypes/getint.json?' + params)
        print(r)
        assert json.loads(r.text) == 2

    def test_invalid_content_type_body(self):
        r = self.app.post('/argtypes/setint.json', '{"value": 2}',
                          headers={"Content-Type": "application/invalid"},
                          expect_errors=True)
        print(r)
        assert r.status_int == 415
        assert json.loads(r.text)['faultstring'] == \
            "Unknown mimetype: application/invalid"

    def test_invalid_json_body(self):
        r = self.app.post('/argtypes/setint.json', '{"value": 2',
                          headers={"Content-Type": "application/json"},
                          expect_errors=True)
        print(r)
        assert r.status_int == 400
        assert json.loads(r.text)['faultstring'] == \
            "Request is not in valid JSON format"

    def test_unknown_arg(self):
        r = self.app.post('/returntypes/getint.json', '{"a": 2}',
                          headers={"Content-Type": "application/json"},
                          expect_errors=True)
        print(r)
        assert r.status_int == 400
        assert json.loads(r.text)['faultstring'].startswith(
            "Unknown argument:"
        )

        r = self.app.get('/returntypes/getint.json?a=2', expect_errors=True)
        print(r)
        assert r.status_int == 400
        assert json.loads(r.text)['faultstring'].startswith(
            "Unknown argument:"
        )

    def test_set_custom_object(self):
        r = self.app.post(
            '/argtypes/setcustomobject',
            '{"value": {"aint": 2, "name": "test"}}',
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(r.status_int, 200)
        self.assertEqual(r.json, {'aint': 2, 'name': 'test'})

    def test_set_extended_int(self):
        r = self.app.post(
            '/argtypes/setextendedint',
            '{"value": 3}',
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(r.status_int, 200)
        self.assertEqual(r.json, 3)

    def test_unset_attrs(self):
        class AType(object):
            attr = int

        wsme.types.register_type(AType)

        j = tojson(AType, AType())
        assert j == {}

    def test_array_tojson(self):
        assert tojson([int], None) is None
        assert tojson([int], []) == []
        assert tojson([str], ['1', '4']) == ['1', '4']

    def test_dict_tojson(self):
        assert tojson({int: str}, None) is None
        assert tojson({int: str}, {5: '5'}) == {5: '5'}

    def test_None_tojson(self):
        for dt in (datetime.date, datetime.time, datetime.datetime,
                   decimal.Decimal):
            assert tojson(dt, None) is None

    def test_None_fromjson(self):
        for dt in (str, int, datetime.date, datetime.time, datetime.datetime,
                   decimal.Decimal, [int], {int: int}):
            assert fromjson(dt, None) is None

    def test_parse_valid_date(self):
        j = parse('{"a": "2011-01-01"}', {'a': datetime.date}, False)
        assert isinstance(j['a'], datetime.date)

    def test_invalid_root_dict_fromjson(self):
        try:
            parse('["invalid"]', {'a': ArrayType(str)}, False)
            assert False
        except Exception as e:
            assert isinstance(e, ClientSideError)
            assert e.msg == "Request must be a JSON dict"

    def test_invalid_list_fromjson(self):
        jlist = "invalid"
        try:
            parse('{"a": "%s"}' % jlist, {'a': ArrayType(str)}, False)
            assert False
        except Exception as e:
            assert isinstance(e, InvalidInput)
            assert e.fieldname == 'a'
            assert e.value == jlist
            assert e.msg == "Value not a valid list: %s" % jlist

    def test_invalid_dict_fromjson(self):
        jdict = "invalid"
        try:
            parse('{"a": "%s"}' % jdict, {'a': DictType(str, str)}, False)
            assert False
        except Exception as e:
            assert isinstance(e, InvalidInput)
            assert e.fieldname == 'a'
            assert e.value == jdict
            assert e.msg == "Value not a valid dict: %s" % jdict

    def test_invalid_date_fromjson(self):
        jdate = "2015-01-invalid"
        try:
            parse('{"a": "%s"}' % jdate, {'a': datetime.date}, False)
            assert False
        except Exception as e:
            assert isinstance(e, InvalidInput)
            assert e.fieldname == 'a'
            assert e.value == jdate
            assert e.msg == "'%s' is not a legal date value" % jdate

    def test_parse_valid_date_bodyarg(self):
        j = parse('"2011-01-01"', {'a': datetime.date}, True)
        assert isinstance(j['a'], datetime.date)

    def test_invalid_date_fromjson_bodyarg(self):
        jdate = "2015-01-invalid"
        try:
            parse('"%s"' % jdate, {'a': datetime.date}, True)
            assert False
        except Exception as e:
            assert isinstance(e, InvalidInput)
            assert e.fieldname == 'a'
            assert e.value == jdate
            assert e.msg == "'%s' is not a legal date value" % jdate

    def test_valid_str_to_builtin_fromjson(self):
        types = six.integer_types + (bool, float)
        value = '2'
        for t in types:
            for ba in True, False:
                jd = '%s' if ba else '{"a": %s}'
                i = parse(jd % value, {'a': t}, ba)
                self.assertEqual(
                    i, {'a': t(value)},
                    "Parsed value does not correspond for %s: "
                    "%s != {'a': %s}" % (
                        t, repr(i), repr(t(value))
                    )
                )
                self.assertIsInstance(i['a'], t)

    def test_valid_int_fromjson(self):
        value = 2
        for ba in True, False:
            jd = '%d' if ba else '{"a": %d}'
            i = parse(jd % value, {'a': int}, ba)
            self.assertEqual(i, {'a': 2})
            self.assertIsInstance(i['a'], int)

    def test_valid_num_to_float_fromjson(self):
        values = 2, 2.3
        for v in values:
            for ba in True, False:
                jd = '%f' if ba else '{"a": %f}'
                i = parse(jd % v, {'a': float}, ba)
                self.assertEqual(i, {'a': float(v)})
                self.assertIsInstance(i['a'], float)

    def test_invalid_str_to_buitin_fromjson(self):
        types = six.integer_types + (float, bool)
        value = '2a'
        for t in types:
            for ba in True, False:
                jd = '"%s"' if ba else '{"a": "%s"}'
                try:
                    parse(jd % value, {'a': t}, ba)
                    assert False, (
                        "Value '%s' should not parse correctly for %s." %
                        (value, t)
                    )
                except ClientSideError as e:
                    self.assertIsInstance(e, InvalidInput)
                    self.assertEqual(e.fieldname, 'a')
                    self.assertEqual(e.value, value)

    def test_ambiguous_to_bool(self):
        amb_values = ('', 'randomstring', '2', '-32', 'not true')
        for value in amb_values:
            for ba in True, False:
                jd = '"%s"' if ba else '{"a": "%s"}'
                try:
                    parse(jd % value, {'a': bool}, ba)
                    assert False, (
                        "Value '%s' should not parse correctly for %s." %
                        (value, bool)
                    )
                except ClientSideError as e:
                    self.assertIsInstance(e, InvalidInput)
                    self.assertEqual(e.fieldname, 'a')
                    self.assertEqual(e.value, value)

    def test_true_strings_to_bool(self):
        true_values = ('true', 't', 'yes', 'y', 'on', '1')
        for value in true_values:
            for ba in True, False:
                jd = '"%s"' if ba else '{"a": "%s"}'
                i = parse(jd % value, {'a': bool}, ba)
                self.assertIsInstance(i['a'], bool)
                self.assertTrue(i['a'])

    def test_false_strings_to_bool(self):
        false_values = ('false', 'f', 'no', 'n', 'off', '0')
        for value in false_values:
            for ba in True, False:
                jd = '"%s"' if ba else '{"a": "%s"}'
                i = parse(jd % value, {'a': bool}, ba)
                self.assertIsInstance(i['a'], bool)
                self.assertFalse(i['a'])

    def test_true_ints_to_bool(self):
        true_values = (1, 5, -3)
        for value in true_values:
            for ba in True, False:
                jd = '%d' if ba else '{"a": %d}'
                i = parse(jd % value, {'a': bool}, ba)
                self.assertIsInstance(i['a'], bool)
                self.assertTrue(i['a'])

    def test_false_ints_to_bool(self):
        value = 0
        for ba in True, False:
            jd = '%d' if ba else '{"a": %d}'
            i = parse(jd % value, {'a': bool}, ba)
            self.assertIsInstance(i['a'], bool)
            self.assertFalse(i['a'])

    def test_valid_simple_custom_type_fromjson(self):
        value = 2
        for ba in True, False:
            jd = '"%d"' if ba else '{"a": "%d"}'
            i = parse(jd % value, {'a': CustomInt()}, ba)
            self.assertEqual(i, {'a': 2})
            self.assertIsInstance(i['a'], int)

    def test_invalid_simple_custom_type_fromjson(self):
        value = '2b'
        for ba in True, False:
            jd = '"%s"' if ba else '{"a": "%s"}'
            try:
                i = parse(jd % value, {'a': CustomInt()}, ba)
                self.assertEqual(i, {'a': 2})
            except ClientSideError as e:
                self.assertIsInstance(e, InvalidInput)
                self.assertEqual(e.fieldname, 'a')
                self.assertEqual(e.value, value)
                self.assertEqual(
                    e.msg,
                    "invalid literal for int() with base 10: '%s'" % value
                )

    def test_parse_unexpected_attribute(self):
        o = {
            "id": "1",
            "name": "test",
            "other": "unknown",
            "other2": "still unknown",
        }
        for ba in True, False:
            jd = o if ba else {"o": o}
            try:
                parse(json.dumps(jd), {'o': Obj}, ba)
                raise AssertionError("Object should not parse correcty.")
            except wsme.exc.UnknownAttribute as e:
                self.assertEqual(e.attributes, set(['other', 'other2']))

    def test_parse_unexpected_nested_attribute(self):
        no = {
            "o": {
                "id": "1",
                "name": "test",
                "other": "unknown",
            },
        }
        for ba in False, True:
            jd = no if ba else {"no": no}
            try:
                parse(json.dumps(jd), {'no': NestedObj}, ba)
            except wsme.exc.UnknownAttribute as e:
                self.assertEqual(e.attributes, set(['other']))
                self.assertEqual(e.fieldname, "no.o")

    def test_nest_result(self):
        self.root.protocols[0].nest_result = True
        r = self.app.get('/returntypes/getint.json')
        print(r)
        assert json.loads(r.text) == {"result": 2}

    def test_encode_sample_value(self):
        class MyType(object):
            aint = int
            astr = str

        register_type(MyType)

        v = MyType()
        v.aint = 4
        v.astr = 's'

        r = wsme.rest.json.encode_sample_value(MyType, v, True)
        print(r)
        assert r[0] == ('javascript')
        assert r[1] == json.dumps({'aint': 4, 'astr': 's'}, ensure_ascii=False,
                                  indent=4, sort_keys=True)

    def test_bytes_tojson(self):
        assert tojson(wsme.types.bytes, None) is None
        assert tojson(wsme.types.bytes, b('ascii')) == u('ascii')

    def test_encode_sample_params(self):
        r = wsme.rest.json.encode_sample_params(
            [('a', int, 2)], True
        )
        assert r[0] == 'javascript', r[0]
        assert r[1] == '''{
    "a": 2
}''', r[1]

    def test_encode_sample_result(self):
        r = wsme.rest.json.encode_sample_result(
            int, 2, True
        )
        assert r[0] == 'javascript', r[0]
        assert r[1] == '''2'''

    def test_PUT(self):
        data = {"id": 1, "name": u("test")}
        content = json.dumps(dict(data=data))
        headers = {
            'Content-Type': 'application/json',
        }
        res = self.app.put(
            '/crud',
            content,
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")
        assert result['message'] == "create"

    def test_GET(self):
        headers = {
            'Accept': 'application/json',
        }
        res = self.app.get(
            '/crud?ref.id=1',
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")

    def test_GET_complex_accept(self):
        headers = {
            'Accept': 'text/html,application/xml;q=0.9,*/*;q=0.8'
        }
        res = self.app.get(
            '/crud?ref.id=1',
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")

    def test_GET_complex_choose_xml(self):
        headers = {
            'Accept': 'text/html,text/xml;q=0.9,*/*;q=0.8'
        }
        res = self.app.get(
            '/crud?ref.id=1',
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        assert res.content_type == 'text/xml'

    def test_GET_complex_accept_no_match(self):
        headers = {
            'Accept': 'text/html,application/xml;q=0.9'
        }
        res = self.app.get(
            '/crud?ref.id=1',
            headers=headers,
            status=406)
        print("Received:", res.body)
        assert res.body == b("Unacceptable Accept type: "
                             "text/html, application/xml;q=0.9 not in "
                             "['application/json', 'text/javascript', "
                             "'application/javascript', 'text/xml']")

    def test_GET_bad_simple_accept(self):
        headers = {
            'Accept': 'text/plain',
        }
        res = self.app.get(
            '/crud?ref.id=1',
            headers=headers,
            status=406)
        print("Received:", res.body)
        assert res.body == b("Unacceptable Accept type: text/plain not in "
                             "['application/json', 'text/javascript', "
                             "'application/javascript', 'text/xml']")

    def test_POST(self):
        headers = {
            'Content-Type': 'application/json',
        }
        res = self.app.post(
            '/crud',
            json.dumps(dict(data=dict(id=1, name=u('test')))),
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")
        assert result['message'] == "update"

    def test_POST_bad_content_type(self):
        headers = {
            'Content-Type': 'text/plain',
        }
        res = self.app.post(
            '/crud',
            json.dumps(dict(data=dict(id=1, name=u('test')))),
            headers=headers,
            status=415)
        print("Received:", res.body)
        assert res.body == b("Unacceptable Content-Type: text/plain not in "
                             "['application/json', 'text/javascript', "
                             "'application/javascript', 'text/xml']")

    def test_DELETE(self):
        res = self.app.delete(
            '/crud.json?ref.id=1',
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")
        assert result['message'] == "delete"

    def test_extra_arguments(self):
        headers = {
            'Accept': 'application/json',
        }
        res = self.app.get(
            '/crud?ref.id=1&extraarg=foo',
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")
        assert result['message'] == "read"

    def test_unexpected_extra_arg(self):
        headers = {
            'Content-Type': 'application/json',
        }
        data = {"id": 1, "name": "test"}
        content = json.dumps({"data": data, "other": "unexpected"})
        res = self.app.put(
            '/crud',
            content,
            headers=headers,
            expect_errors=True)
        self.assertEqual(res.status_int, 400)

    def test_unexpected_extra_attribute(self):
        """Expect a failure if we send an unexpected object attribute."""
        headers = {
            'Content-Type': 'application/json',
        }
        data = {"id": 1, "name": "test", "other": "unexpected"}
        content = json.dumps({"data": data})
        res = self.app.put(
            '/crud',
            content,
            headers=headers,
            expect_errors=True)
        self.assertEqual(res.status_int, 400)

    def test_body_arg(self):
        headers = {
            'Content-Type': 'application/json',
        }
        res = self.app.post(
            '/crud/update_with_body?msg=hello',
            json.dumps(dict(id=1, name=u('test'))),
            headers=headers,
            expect_errors=False)
        print("Received:", res.body)
        result = json.loads(res.text)
        print(result)
        assert result['data']['id'] == 1
        assert result['data']['name'] == u("test")
        assert result['message'] == "hello"

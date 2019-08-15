import base64
import datetime
import decimal

try:
    import simplejson as json
except ImportError:
    import json  # noqa

import wsme.tests.protocol
from wsme.utils import parse_isodatetime, parse_isodate, parse_isotime
from wsme.types import isarray, isdict, isusertype

import six

if six.PY3:
    from urllib.parse import urlencode
else:
    from urllib import urlencode  # noqa


def encode_arg(value):
    if isinstance(value, tuple):
        value, datatype = value
    else:
        datatype = type(value)

    if isinstance(datatype, list):
        value = [encode_arg((item, datatype[0])) for item in value]
    elif isinstance(datatype, dict):
        key_type, value_type = list(datatype.items())[0]
        value = dict((
            (encode_arg((key, key_type)),
                encode_arg((value, value_type)))
            for key, value in value.items()
        ))
    elif datatype in (datetime.date, datetime.time, datetime.datetime):
        value = value.isoformat()
    elif datatype == wsme.types.binary:
        value = base64.encodestring(value).decode('ascii')
    elif datatype == wsme.types.bytes:
        value = value.decode('ascii')
    elif datatype == decimal.Decimal:
        value = str(value)
    return value


def decode_result(value, datatype):
    if value is None:
        return None
    if datatype == wsme.types.binary:
        value = base64.decodestring(value.encode('ascii'))
        return value
    if isusertype(datatype):
        datatype = datatype.basetype
    if isinstance(datatype, list):
        value = [decode_result(item, datatype[0]) for item in value]
    elif isarray(datatype):
        value = [decode_result(item, datatype.item_type) for item in value]
    elif isinstance(datatype, dict):
        key_type, value_type = list(datatype.items())[0]
        value = dict((
            (decode_result(key, key_type),
                decode_result(value, value_type))
            for key, value in value.items()
        ))
    elif isdict(datatype):
        key_type, value_type = datatype.key_type, datatype.value_type
        value = dict((
            (decode_result(key, key_type),
                decode_result(value, value_type))
            for key, value in value.items()
        ))
    elif datatype == datetime.time:
        value = parse_isotime(value)
    elif datatype == datetime.date:
        value = parse_isodate(value)
    elif datatype == datetime.datetime:
        value = parse_isodatetime(value)
    elif hasattr(datatype, '_wsme_attributes'):
        for attr in datatype._wsme_attributes:
            if attr.key not in value:
                continue
            value[attr.key] = decode_result(value[attr.key], attr.datatype)
    elif datatype == decimal.Decimal:
        value = decimal.Decimal(value)
    elif datatype == wsme.types.bytes:
        value = value.encode('ascii')
    elif datatype is not None and type(value) != datatype:
        value = datatype(value)
    return value


class TestExtDirectProtocol(wsme.tests.protocol.ProtocolTestCase):
    protocol = 'extdirect'
    protocol_options = {
        'namespace': 'MyNS.api',
        'nsfolder': 'app'
    }

    def call(self, fname, _rt=None, _no_result_decode=False, _accept=None,
             **kw):
        path = fname.split('/')
        try:
            func, funcdef, args = self.root._lookup_function(path)
            arguments = funcdef.arguments
        except Exception:
            arguments = []
        if len(path) == 1:
            ns, action, fname = '', '', path[0]
        elif len(path) == 2:
            ns, action, fname = '', path[0], path[1]
        else:
            ns, action, fname = '.'.join(path[:-2]), path[-2], path[-1]
        print(kw)

        args = [
            dict(
                (arg.name, encode_arg(kw[arg.name]))
                for arg in arguments if arg.name in kw
            )
        ]
        print("args =", args)
        data = json.dumps({
            'type': 'rpc',
            'tid': 0,
            'action': action,
            'method': fname,
            'data': args,
        })
        print(data)
        headers = {'Content-Type': 'application/json'}
        if _accept:
            headers['Accept'] = _accept
        res = self.app.post('/extdirect/router/%s' % ns, data, headers=headers,
                            expect_errors=True)

        print(res.body)

        if _no_result_decode:
            return res

        data = json.loads(res.text)
        if data['type'] == 'rpc':
            r = data['result']
            return decode_result(r, _rt)
        elif data['type'] == 'exception':
            faultcode, faultstring = data['message'].split(': ', 1)
            debuginfo = data.get('where')
            raise wsme.tests.protocol.CallException(
                faultcode, faultstring, debuginfo)

    def test_api_alias(self):
        assert self.root._get_protocol('extdirect').api_alias == '/app/api.js'

    def test_get_api(self):
        res = self.app.get('/app/api.js')
        print(res.body)
        assert res.body

    def test_positional(self):
        self.root._get_protocol('extdirect').default_params_notation = \
            'positional'

        data = json.dumps({
            'type': 'rpc',
            'tid': 0,
            'action': 'misc',
            'method': 'multiply',
            'data': [2, 5],
        })
        headers = {'Content-Type': 'application/json'}
        res = self.app.post('/extdirect/router', data, headers=headers)

        print(res.body)

        data = json.loads(res.text)
        assert data['type'] == 'rpc'
        r = data['result']
        assert r == 10

    def test_batchcall(self):
        data = json.dumps([{
            'type': 'rpc',
            'tid': 1,
            'action': 'argtypes',
            'method': 'setdate',
            'data': [{'value': '2011-04-06'}],
        }, {
            'type': 'rpc',
            'tid': 2,
            'action': 'returntypes',
            'method': 'getbytes',
            'data': []
        }])
        print(data)
        headers = {'Content-Type': 'application/json'}
        res = self.app.post('/extdirect/router', data, headers=headers)

        print(res.body)

        rdata = json.loads(res.text)

        assert len(rdata) == 2

        assert rdata[0]['tid'] == 1
        assert rdata[0]['result'] == '2011-04-06'
        assert rdata[1]['tid'] == 2
        assert rdata[1]['result'] == 'astring'

    def test_form_call(self):
        params = {
            'value[0].inner.aint': 54,
            'value[1].inner.aint': 55,
            'extType': 'rpc',
            'extTID': 1,
            'extAction': 'argtypes',
            'extMethod': 'setnestedarray',
        }

        body = urlencode(params)
        r = self.app.post(
            '/extdirect/router',
            body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        print(r)

        assert json.loads(r.text) == {
            "tid": "1",
            "action": "argtypes",
            "type": "rpc",
            "method": "setnestedarray",
            "result": [{
                "inner": {
                    "aint": 54
                }
            }, {
                "inner": {
                    "aint": 55
                }
            }]
        }

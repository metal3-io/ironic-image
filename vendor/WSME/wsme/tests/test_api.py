# encoding=utf8

from six import b

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import webtest

from wsme import WSRoot, expose, validate
from wsme.rest import scan_api
from wsme import types
from wsme import exc
import wsme.api as wsme_api
import wsme.types

from wsme.tests.test_protocols import DummyProtocol


class TestController(unittest.TestCase):
    def test_expose(self):
        class MyWS(WSRoot):
            @expose(int)
            def getint(self):
                return 1

        assert MyWS.getint._wsme_definition.return_type == int

    def test_validate(self):
        class ComplexType(object):
            attr = int

        class MyWS(object):
            @expose(int)
            @validate(int, int, int)
            def add(self, a, b, c=0):
                return a + b + c

            @expose(bool)
            @validate(ComplexType)
            def setcplx(self, obj):
                pass

        MyWS.add._wsme_definition.resolve_types(wsme.types.registry)
        MyWS.setcplx._wsme_definition.resolve_types(wsme.types.registry)
        args = MyWS.add._wsme_definition.arguments

        assert args[0].name == 'a'
        assert args[0].datatype == int
        assert args[0].mandatory
        assert args[0].default is None

        assert args[1].name == 'b'
        assert args[1].datatype == int
        assert args[1].mandatory
        assert args[1].default is None

        assert args[2].name == 'c'
        assert args[2].datatype == int
        assert not args[2].mandatory
        assert args[2].default == 0

        assert types.iscomplex(ComplexType)

    def test_validate_enum_with_none(self):
        class Version(object):
            number = types.Enum(str, 'v1', 'v2', None)

        class MyWS(WSRoot):
            @expose(str)
            @validate(Version)
            def setcplx(self, version):
                pass

        r = MyWS(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/setcplx', params={'version': {'number': 'arf'}},
                            expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertTrue(
            res.json_body['faultstring'].startswith(
                "Invalid input for field/attribute number. Value: 'arf'. \
Value should be one of:"))
        self.assertIn('v1', res.json_body['faultstring'])
        self.assertIn('v2', res.json_body['faultstring'])
        self.assertIn('None', res.json_body['faultstring'])
        self.assertEqual(res.status_int, 400)

    def test_validate_enum_with_wrong_type(self):
        class Version(object):
            number = types.Enum(str, 'v1', 'v2', None)

        class MyWS(WSRoot):
            @expose(str)
            @validate(Version)
            def setcplx(self, version):
                pass

        r = MyWS(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/setcplx', params={'version': {'number': 1}},
                            expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertTrue(
            res.json_body['faultstring'].startswith(
                "Invalid input for field/attribute number. Value: '1'. \
Value should be one of:"))
        self.assertIn('v1', res.json_body['faultstring'])
        self.assertIn('v2', res.json_body['faultstring'])
        self.assertIn('None', res.json_body['faultstring'])
        self.assertEqual(res.status_int, 400)

    def test_scan_api(self):
        class NS(object):
            @expose(int)
            @validate(int, int)
            def multiply(self, a, b):
                return a * b

        class MyRoot(WSRoot):
            ns = NS()

        r = MyRoot()

        api = list(scan_api(r))
        assert len(api) == 1
        path, fd, args = api[0]
        assert path == ['ns', 'multiply']
        assert fd._wsme_definition.name == 'multiply'
        assert args == []

    def test_scan_subclass(self):
        class MyRoot(WSRoot):
            class SubClass(object):
                pass

        r = MyRoot()
        api = list(scan_api(r))

        assert len(api) == 0

    def test_scan_api_too_deep(self):
        class Loop(object):
            pass

        ell = Loop()
        for i in range(0, 21):
            nl = Loop()
            nl.ell = ell
            ell = nl

        class MyRoot(WSRoot):
            loop = ell

        r = MyRoot()

        try:
            list(scan_api(r))
            assert False, "ValueError not raised"
        except ValueError as e:
            assert str(e).startswith("Path is too long")

    def test_handle_request(self):
        class MyRoot(WSRoot):
            @expose()
            def touch(self):
                pass

        p = DummyProtocol()
        r = MyRoot(protocols=[p])

        app = webtest.TestApp(r.wsgiapp())

        res = app.get('/')

        assert p.lastreq.path == '/'
        assert p.hits == 1

        res = app.get('/touch?wsmeproto=dummy')

        assert p.lastreq.path == '/touch'
        assert p.hits == 2

        class NoPathProto(DummyProtocol):
            def extract_path(self, request):
                return None

        p = NoPathProto()
        r = MyRoot(protocols=[p])

        app = webtest.TestApp(r.wsgiapp())

        res = app.get('/', expect_errors=True)
        print(res.status, res.body)
        assert res.status_int == 400

    def test_no_available_protocol(self):
        r = WSRoot()

        app = webtest.TestApp(r.wsgiapp())

        res = app.get('/', expect_errors=True)
        print(res.status_int)
        assert res.status_int == 406
        print(res.body)
        assert res.body.find(
            b("None of the following protocols can handle this request")) != -1

    def test_return_content_type_guess(self):
        class DummierProto(DummyProtocol):
            content_types = ['text/xml', 'text/plain']

        r = WSRoot([DummierProto()])

        app = webtest.TestApp(r.wsgiapp())

        res = app.get('/', expect_errors=True, headers={
            'Accept': 'text/xml,q=0.8'})
        assert res.status_int == 400
        assert res.content_type == 'text/xml', res.content_type

        res = app.get('/', expect_errors=True, headers={
            'Accept': 'text/plain'})
        assert res.status_int == 400
        assert res.content_type == 'text/plain', res.content_type

    def test_double_expose(self):
        try:
            class MyRoot(WSRoot):
                @expose()
                @expose()
                def atest(self):
                    pass
            assert False, "A ValueError should have been raised"
        except ValueError:
            pass

    def test_multiple_expose(self):
        class MyRoot(WSRoot):
            def multiply(self, a, b):
                return a * b

            mul_int = expose(int, int, int, wrap=True)(multiply)

            mul_float = expose(
                float, float, float,
                wrap=True)(multiply)

            mul_string = expose(
                wsme.types.text, wsme.types.text, int,
                wrap=True)(multiply)

        r = MyRoot(['restjson'])

        app = webtest.TestApp(r.wsgiapp())

        res = app.get('/mul_int?a=2&b=5', headers={
            'Accept': 'application/json'
        })

        self.assertEqual(res.body, b('10'))

        res = app.get('/mul_float?a=1.2&b=2.9', headers={
            'Accept': 'application/json'
        })

        self.assertEqual(res.body, b('3.48'))

        res = app.get('/mul_string?a=hello&b=2', headers={
            'Accept': 'application/json'
        })

        self.assertEqual(res.body, b('"hellohello"'))

    def test_wsattr_mandatory(self):
        class ComplexType(object):
            attr = wsme.types.wsattr(int, mandatory=True)

        class MyRoot(WSRoot):
            @expose(int, body=ComplexType)
            @validate(ComplexType)
            def clx(self, a):
                return a.attr

        r = MyRoot(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/clx', params={}, expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertEqual(res.status_int, 400)

    def test_wsattr_readonly(self):
        class ComplexType(object):
            attr = wsme.types.wsattr(int, readonly=True)

        class MyRoot(WSRoot):
            @expose(int, body=ComplexType)
            @validate(ComplexType)
            def clx(self, a):
                return a.attr

        r = MyRoot(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/clx', params={'attr': 1005}, expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertIn('Cannot set read only field.',
                      res.json_body['faultstring'])
        self.assertIn('1005', res.json_body['faultstring'])
        self.assertEqual(res.status_int, 400)

    def test_wsattr_default(self):
        class ComplexType(object):
            attr = wsme.types.wsattr(wsme.types.Enum(str, 'or', 'and'),
                                     default='and')

        class MyRoot(WSRoot):
            @expose(int)
            @validate(ComplexType)
            def clx(self, a):
                return a.attr

        r = MyRoot(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/clx', params={}, expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertEqual(res.status_int, 400)

    def test_wsproperty_mandatory(self):
        class ComplexType(object):
            def foo(self):
                pass

            attr = wsme.types.wsproperty(int, foo, foo, mandatory=True)

        class MyRoot(WSRoot):
            @expose(int, body=ComplexType)
            @validate(ComplexType)
            def clx(self, a):
                return a.attr

        r = MyRoot(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/clx', params={}, expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertEqual(res.status_int, 400)

    def test_validate_enum_mandatory(self):
        class Version(object):
            number = wsme.types.wsattr(wsme.types.Enum(str, 'v1', 'v2'),
                                       mandatory=True)

        class MyWS(WSRoot):
            @expose(str)
            @validate(Version)
            def setcplx(self, version):
                pass

        r = MyWS(['restjson'])
        app = webtest.TestApp(r.wsgiapp())
        res = app.post_json('/setcplx', params={'version': {}},
                            expect_errors=True,
                            headers={'Accept': 'application/json'})
        self.assertEqual(res.status_int, 400)


class TestFunctionDefinition(unittest.TestCase):

    def test_get_arg(self):
        def myfunc(self):
            pass

        fd = wsme_api.FunctionDefinition(wsme_api.FunctionDefinition)
        fd.arguments.append(wsme_api.FunctionArgument('a', int, True, None))

        assert fd.get_arg('a').datatype is int
        assert fd.get_arg('b') is None


class TestFormatException(unittest.TestCase):

    def _test_format_exception(self, exception, debug=False):
        fake_exc_info = (None, exception, None)
        return wsme_api.format_exception(fake_exc_info, debug=debug)

    def test_format_client_exception(self):
        faultstring = 'boom'
        ret = self._test_format_exception(exc.ClientSideError(faultstring))
        self.assertIsNone(ret['debuginfo'])
        self.assertEqual('Client', ret['faultcode'])
        self.assertEqual(faultstring, ret['faultstring'])

    def test_format_client_exception_unicode(self):
        faultstring = u'\xc3\xa3o'
        ret = self._test_format_exception(exc.ClientSideError(faultstring))
        self.assertIsNone(ret['debuginfo'])
        self.assertEqual('Client', ret['faultcode'])
        self.assertEqual(faultstring, ret['faultstring'])

    def test_format_server_exception(self):
        faultstring = 'boom'
        ret = self._test_format_exception(Exception(faultstring))
        self.assertIsNone(ret['debuginfo'])
        self.assertEqual('Server', ret['faultcode'])
        self.assertEqual(faultstring, ret['faultstring'])

    def test_format_server_exception_unicode(self):
        faultstring = u'\xc3\xa3o'
        ret = self._test_format_exception(Exception(faultstring))
        self.assertIsNone(ret['debuginfo'])
        self.assertEqual('Server', ret['faultcode'])
        self.assertEqual(faultstring, ret['faultstring'])

    def test_format_server_exception_debug(self):
        faultstring = 'boom'
        ret = self._test_format_exception(Exception(faultstring), debug=True)
        # assert debuginfo is populated
        self.assertIsNotNone(ret['debuginfo'])
        self.assertEqual('Server', ret['faultcode'])
        self.assertEqual(faultstring, ret['faultstring'])

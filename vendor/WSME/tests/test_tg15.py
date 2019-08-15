import wsmeext.tg15
from wsme import WSRoot

from turbogears.controllers import RootController
import cherrypy

from wsmeext.tests import test_soap

import simplejson


class Subcontroller(object):
    @wsmeext.tg15.wsexpose(int, int, int)
    def add(self, a, b):
        return a + b


class Root(RootController):
    class UselessSubClass:
        # This class is here only to make sure wsmeext.tg1.scan_api
        # does its job properly
        pass

    sub = Subcontroller()

    ws = WSRoot(webpath='/ws')
    ws.addprotocol('soap',
        tns=test_soap.tns,
        typenamespace=test_soap.typenamespace,
        baseURL='/ws/'
    )
    ws = wsmeext.tg15.adapt(ws)

    @wsmeext.tg15.wsexpose(int)
    @wsmeext.tg15.wsvalidate(int, int)
    def multiply(self, a, b):
        return a * b

    @wsmeext.tg15.wsexpose(int)
    @wsmeext.tg15.wsvalidate(int, int)
    def divide(self, a, b):
        if b == 0:
            raise cherrypy.HTTPError(400, 'Cannot divide by zero!')
        return a / b


from turbogears import testutil


class TestController(testutil.TGTest):
    root = Root

#    def setUp(self):
#        "Tests the output of the index method"
#        self.app = testutil.make_app(self.root)
#        #print cherrypy.root
#        testutil.start_server()

#    def tearDown(self):
#        # implementation copied from turbogears.testutil.stop_server.
#        # The only change is that cherrypy.root is set to None
#        # AFTER stopTurbogears has been called so that wsmeext.tg15
#        # can correctly uninstall its filter.
#        if config.get("cp_started"):
#            cherrypy.server.stop()
#            config.update({"cp_started": False})
#
#        if config.get("server_started"):
#            startup.stopTurboGears()
#            config.update({"server_started": False})

    def test_restcall(self):
        response = self.app.post("/multiply",
            simplejson.dumps({'a': 5, 'b': 10}),
            {'Content-Type': 'application/json'}
        )
        print response
        assert simplejson.loads(response.body) == 50

        response = self.app.post("/multiply",
            simplejson.dumps({'a': 5, 'b': 10}),
            {'Content-Type': 'application/json', 'Accept': 'application/json'}
        )
        print response
        assert simplejson.loads(response.body) == 50

        response = self.app.post("/multiply",
            simplejson.dumps({'a': 5, 'b': 10}),
            {'Content-Type': 'application/json', 'Accept': 'text/javascript'}
        )
        print response
        assert simplejson.loads(response.body) == 50

        response = self.app.post("/multiply",
            simplejson.dumps({'a': 5, 'b': 10}),
            {'Content-Type': 'application/json',
             'Accept': 'text/xml'}
        )
        print response
        assert response.body == "<result>50</result>"

    def test_custom_clientside_error(self):
        response = self.app.post(
            "/divide",
            simplejson.dumps({'a': 5, 'b': 0}),
            {'Content-Type': 'application/json', 'Accept': 'application/json'},
            expect_errors=True
        )
        assert response.status_int == 400
        assert simplejson.loads(response.body) == {
            "debuginfo": None,
            "faultcode": "Client",
            "faultstring": "(400, 'Cannot divide by zero!')"
        }

        response = self.app.post(
            "/divide",
            simplejson.dumps({'a': 5, 'b': 0}),
            {'Content-Type': 'application/json', 'Accept': 'text/xml'},
            expect_errors=True
        )
        assert response.status_int == 400
        assert response.body == ("<error><faultcode>Client</faultcode>"
                                 "<faultstring>(400, 'Cannot divide by zero!')"
                                 "</faultstring><debuginfo /></error>")

    def test_soap_wsdl(self):
        wsdl = self.app.get('/ws/api.wsdl').body
        print wsdl
        assert 'multiply' in wsdl

    def test_soap_call(self):
        ts = test_soap.TestSOAP('test_wsdl')
        ts.app = self.app
        ts.ws_path = '/ws/'

        print ts.ws_path
        assert ts.call('multiply', a=5, b=10, _rt=int) == 50

    def test_scan_api_loops(self):
        class MyRoot(object):
            pass

        MyRoot.loop = MyRoot()

        root = MyRoot()

        api = list(wsmeext.tg1._scan_api(root))
        print(api)

        self.assertEqual(len(api), 0)

    def test_scan_api_maxlen(self):
        class ARoot(object):
            pass

        def make_subcontrollers(n):
            c = type('Controller%s' % n, (object,), {})
            return c

        c = ARoot
        for n in xrange(55):
            subc = make_subcontrollers(n)
            c.sub = subc()
            c = subc
        root = ARoot()
        self.assertRaises(ValueError, list, wsmeext.tg1._scan_api(root))

    def test_templates_content_type(self):
        self.assertEqual(
            "application/json",
            wsmeext.tg1.AutoJSONTemplate().get_content_type('dummy')
        )
        self.assertEqual(
            "text/xml",
            wsmeext.tg1.AutoXMLTemplate().get_content_type('dummy')
        )

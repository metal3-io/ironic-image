from six.moves import http_client
from test.tests import FunctionalTest
import json
import pecan
import six


used_status_codes = [400, 401, 403, 404, 500]
http_response_messages = {}
for code in used_status_codes:
    http_response_messages[code] = '%s %s' % (code, http_client.responses[code])

class TestWS(FunctionalTest):

    def test_get_all(self):
        self.app.get('/authors')

    def test_optional_array_param(self):
        r = self.app.get('/authors?q=a&q=b')
        l = json.loads(r.body.decode('utf-8'))
        assert len(l) == 2
        assert l[0]['firstname'] == 'a'
        assert l[1]['firstname'] == 'b'

    def test_optional_indexed_array_param(self):
        r = self.app.get('/authors?q[0]=a&q[1]=b')
        l = json.loads(r.body.decode('utf-8'))
        assert len(l) == 2
        assert l[0]['firstname'] == 'a'
        assert l[1]['firstname'] == 'b'

    def test_options_object_array_param(self):
        r = self.app.get('/authors?r.value=a&r.value=b')
        l = json.loads(r.body.decode('utf-8'))
        assert len(l) == 2
        assert l[0]['firstname'] == 'a'
        assert l[1]['firstname'] == 'b'

    def test_options_indexed_object_array_param(self):
        r = self.app.get('/authors?r[0].value=a&r[1].value=b')
        l = json.loads(r.body.decode('utf-8'))
        assert len(l) == 2
        assert l[0]['firstname'] == 'a'
        assert l[1]['firstname'] == 'b'

    def test_get_author(self):
        a = self.app.get(
            '/authors/1.json',
        )
        a = json.loads(a.body.decode('utf-8'))

        assert a['id'] == 1
        assert a['firstname'] == 'aname'

        a = self.app.get(
            '/authors/1.xml',
        )
        body = a.body.decode('utf-8')
        assert '<id>1</id>' in body
        assert '<firstname>aname</firstname>' in body

    def test_post_body_parameter_validation(self):
        res = self.app.post(
            '/authors', '{"firstname": "Robert"}',
            headers={"Content-Type": "application/json"},
            expect_errors=True
        )
        self.assertEqual(res.status_int, 400)
        a = json.loads(res.body.decode('utf-8'))
        self.assertEqual(a['faultcode'], 'Client')
        self.assertEqual(a['faultstring'], "I don't like this author!")

    def test_post_body_parameter(self):
        res = self.app.post(
            '/authors', '{"firstname": "test"}',
            headers={"Content-Type": "application/json"}
        )
        assert res.status_int == 201
        a = json.loads(res.body.decode('utf-8'))
        assert a['id'] == 10
        assert a['firstname'] == 'test'

    def test_put_parameter_validate(self):
        res = self.app.put(
            '/authors/foobar', '{"firstname": "test"}',
            headers={"Content-Type": "application/json"},
            expect_errors=True
        )
        self.assertEqual(res.status_int, 400)
        a = json.loads(res.body.decode('utf-8'))
        self.assertEqual(
            a['faultstring'],
            "Invalid input for field/attribute author_id. "
            "Value: 'foobar'. unable to convert to int. Error: invalid "
            "literal for int() with base 10: 'foobar'")

    def test_clientsideerror(self):
        expected_status_code = 400
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get(
            '/authors/999.json',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Client'

        res = self.app.get(
            '/authors/999.xml',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        assert '<faultcode>Client</faultcode>' in res.body.decode('utf-8')

    def test_custom_clientside_error(self):
        expected_status_code = 404
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get(
            '/authors/998.json',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Client'

        res = self.app.get(
            '/authors/998.xml',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        assert '<faultcode>Client</faultcode>' in res.body.decode('utf-8')

    def test_custom_non_http_clientside_error(self):
        expected_status_code = 500
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get(
            '/authors/997.json',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Server'

        res = self.app.get(
            '/authors/997.xml',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        assert '<faultcode>Server</faultcode>' in res.body.decode('utf-8')

    def test_clientsideerror_status_code(self):
        expected_status_code = 403
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get(
            '/authors/996.json',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Client'

        res = self.app.get(
            '/authors/996.xml',
            expect_errors=True
        )
        self.assertEqual(res.status, expected_status)
        assert '<faultcode>Client</faultcode>' in res.body.decode('utf-8')

    def test_non_default_response(self):
        expected_status_code = 401
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get(
            '/authors/911.json',
            expect_errors=True
        )
        self.assertEqual(res.status_int, expected_status_code)
        self.assertEqual(res.status, expected_status)

    def test_non_default_response_return_type(self):
        res = self.app.get(
            '/authors/913',
        )
        self.assertEqual(res.status_int, 200)
        self.assertEqual(res.body, b'"foo"')
        self.assertEqual(res.content_length, 5)

    def test_non_default_response_return_type_no_content(self):
        res = self.app.get(
            '/authors/912',
        )
        self.assertEqual(res.status_int, 204)
        self.assertEqual(res.body, b'')
        self.assertEqual(res.content_length, 0)

    def test_serversideerror(self):
        expected_status_code = 500
        expected_status = http_response_messages[expected_status_code]
        res = self.app.get('/divide_by_zero.json', expect_errors=True)
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Server'
        assert a['debuginfo'] is None

    def test_serversideerror_with_debug(self):
        expected_status_code = 500
        expected_status = http_response_messages[expected_status_code]
        pecan.set_config({'wsme': {'debug': True}})
        res = self.app.get('/divide_by_zero.json', expect_errors=True)
        self.assertEqual(res.status, expected_status)
        a = json.loads(res.body.decode('utf-8'))
        assert a['faultcode'] == 'Server'
        assert a['debuginfo'].startswith('Traceback (most recent call last):')

    def test_json_only(self):
        res = self.app.get('/authors/json_only.json')
        assert res.status_int == 200
        body = json.loads(res.body.decode('utf-8'))
        assert len(body) == 1
        assert body[0]['firstname'] == u"aname"
        assert body[0]['books'] == []
        assert body[0]['id'] == 1
        res = self.app.get('/authors/json_only.xml', expect_errors=True)

    def test_xml_only(self):
        res = self.app.get('/authors/xml_only.xml')
        assert res.status_int == 200
        assert '<id>1</id>' in res.body.decode('utf-8')
        assert '<firstname>aname</firstname>' in res.body.decode('utf-8')
        assert '<books />' in res.body.decode('utf-8')
        res = self.app.get('/authors/xml_only.json', expect_errors=True)

    def test_body_parameter(self):
        res = self.app.put(
            '/authors/1/books/2.json',
            '{"name": "Alice au pays des merveilles"}',
            headers={"Content-Type": "application/json"}
        )
        book = json.loads(res.body.decode('utf-8'))
        assert book['id'] == 2
        assert book['author']['id'] == 1

    def test_no_content_type_if_no_return_type(self):
        if six.PY3:
            self.skipTest(
                "This test does not work in Python 3 until https://review.openstack.org/#/c/48439/ is merged")
        res = self.app.delete('/authors/4')
        assert "Content-Type" not in res.headers, res.headers['Content-Type']

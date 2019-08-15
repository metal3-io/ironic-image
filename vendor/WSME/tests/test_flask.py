# encoding=utf8
import unittest
from flask import Flask, json, abort
import flask_restful as restful

from wsmeext.flask import signature
from wsme.api import Response
from wsme.types import Base, text


class Model(Base):
    id = int
    name = text


class Criterion(Base):
    op = text
    attr = text
    value = text

test_app = Flask(__name__)
api = restful.Api(test_app)


@test_app.route('/multiply')
@signature(int, int, int)
def multiply(a, b):
    return a * b


@test_app.route('/divide_by_zero')
@signature(None)
def divide_by_zero():
    return 1 / 0


@test_app.route('/models')
@signature([Model], [Criterion])
def list_models(q=None):
    if q:
        name = q[0].value
    else:
        name = 'first'
    return [Model(name=name)]


@test_app.route('/models/<name>')
@signature(Model, text)
def get_model(name):
    return Model(name=name)


@test_app.route('/models/<name>/secret')
@signature(Model, text)
def model_secret(name):
    abort(403)


@test_app.route('/models/<name>/custom-error')
@signature(Model, text)
def model_custom_error(name):
    class CustomError(Exception):
        code = 412
    raise CustomError("FOO!")


@test_app.route('/models', methods=['POST'])
@signature(Model, body=Model)
def post_model(body):
    return Model(name=body.name)


@test_app.route('/status_sig')
@signature(int, status_code=201)
def get_status_sig():
    return 1


@test_app.route('/status_response')
@signature(int)
def get_status_response():
    return Response(1, status_code=201)


class RestFullApi(restful.Resource):
    @signature(Model)
    def get(self):
        return Model(id=1, name=u"Gérard")

    @signature(int, body=Model)
    def post(self, model):
        return model.id

api.add_resource(RestFullApi, '/restful')


class FlaskrTestCase(unittest.TestCase):

    def setUp(self):
        test_app.config['TESTING'] = True
        self.app = test_app.test_client()

    def tearDown(self):
        pass

    def test_multiply(self):
        r = self.app.get('/multiply?a=2&b=5')
        assert r.data == b'10', r.data

    def test_get_model(self):
        resp = self.app.get('/models/test')
        assert resp.status_code == 200

    def test_list_models(self):
        resp = self.app.get('/models')
        assert resp.status_code == 200

    def test_array_parameter(self):
        resp = self.app.get('/models?q.op=%3D&q.attr=name&q.value=second')
        assert resp.status_code == 200
        self.assertEqual(
            resp.data, b'[{"name": "second"}]'
        )

    def test_post_model(self):
        resp = self.app.post('/models', data={"body.name": "test"})
        assert resp.status_code == 200
        resp = self.app.post(
            '/models',
            data=json.dumps({"name": "test"}),
            content_type="application/json"
        )
        assert resp.status_code == 200

    def test_get_status_sig(self):
        resp = self.app.get('/status_sig')
        assert resp.status_code == 201

    def test_get_status_response(self):
        resp = self.app.get('/status_response')
        assert resp.status_code == 201

    def test_custom_clientside_error(self):
        r = self.app.get(
            '/models/test/secret',
            headers={'Accept': 'application/json'}
        )
        assert r.status_code == 403, r.status_code
        assert '403 Forbidden:' in json.loads(r.data)['faultstring']

        r = self.app.get(
            '/models/test/secret',
            headers={'Accept': 'application/xml'}
        )
        assert r.status_code == 403, r.status_code
        assert r.data == (b"<error><faultcode>Client</faultcode>"
                          b"<faultstring>403 Forbidden: You don't have the "
                          b"permission to access the requested resource. It "
                          b"is either read-protected or not readable by the "
                          b"server."
                          b"</faultstring><debuginfo /></error>")

    # NOTE(cdent): For reasons unclear, 'r' here has no value on data
    # even though it does earlier in the stack. If works with Werkzeug
    # <0.14.0 but not after. As WSME does not have test-requirement, nor
    # pinning, so not a lot to do here.
    @unittest.expectedFailure
    def test_custom_non_http_clientside_error(self):
        r = self.app.get(
            '/models/test/custom-error',
            headers={'Accept': 'application/json'}
        )
        assert r.status_code == 412, r.status_code
        assert json.loads(r.data)['faultstring'] == 'FOO!'

        r = self.app.get(
            '/models/test/custom-error',
            headers={'Accept': 'application/xml'}
        )
        assert r.status_code == 412, r.status_code
        assert r.data == (b'<error><faultcode>Client</faultcode>'
                          b'<faultstring>FOO!</faultstring>'
                          b'<debuginfo /></error>')

    def test_serversideerror(self):
        r = self.app.get('/divide_by_zero')
        assert r.status_code == 500
        data = json.loads(r.data)
        self.assertEqual(data['debuginfo'], None)
        self.assertEqual(data['faultcode'], 'Server')
        self.assertIn('by zero', data['faultstring'])

    def test_restful_get(self):
        r = self.app.get('/restful', headers={'Accept': 'application/json'})
        self.assertEqual(r.status_code, 200)

        data = json.loads(r.data)

        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], u"Gérard")

    def test_restful_post(self):
        r = self.app.post(
            '/restful',
            data=json.dumps({'id': 5, 'name': u'Huguette'}),
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 200)

        data = json.loads(r.data)

        self.assertEqual(data, 5)

if __name__ == '__main__':
    test_app.run()

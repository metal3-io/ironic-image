import unittest
import json

import webtest

from cornice import Service
from cornice import resource
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPUnauthorized

from wsme.types import text, Base, HostRequest
from wsmeext.cornice import signature


class User(Base):
    id = int
    name = text

users = Service(name='users', path='/users')


@users.get()
@signature([User])
def users_get():
    return [User(id=1, name='first')]


@users.post()
@signature(User, body=User)
def users_create(data):
    data.id = 2
    return data


secret = Service(name='secrets', path='/secret')


@secret.get()
@signature()
def secret_get():
    raise HTTPUnauthorized()


divide = Service(name='divide', path='/divide')


@divide.get()
@signature(int, int, int)
def do_divide(a, b):
    return a / b

needrequest = Service(name='needrequest', path='/needrequest')


@needrequest.get()
@signature(bool, HostRequest)
def needrequest_get(request):
    assert request.path == '/needrequest', request.path
    return True


class Author(Base):
    authorId = int
    name = text


@resource.resource(collection_path='/author', path='/author/{authorId}')
class AuthorResource(object):
    def __init__(self, request):
        self.request = request

    @signature(Author, int)
    def get(self, authorId):
        return Author(authorId=authorId, name="Author %s" % authorId)

    @signature(Author, int, body=Author)
    def post(self, authorId, data):
        data.authorId = authorId
        return data

    @signature([Author], text)
    def collection_get(self, where=None):
        return [
            Author(authorId=1, name="Author 1"),
            Author(authorId=2, name="Author 2"),
            Author(authorId=3, name="Author 3")
        ]


def make_app():
    config = Configurator()
    config.include("cornice")
    config.include("wsmeext.cornice")
    config.scan("test_cornice")
    return config.make_wsgi_app()


class WSMECorniceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = webtest.TestApp(make_app())

    def test_get_json_list(self):
        resp = self.app.get('/users')
        self.assertEqual(
            resp.body,
            b'[{"id": 1, "name": "first"}]'
        )

    def test_get_xml_list(self):
        resp = self.app.get('/users', headers={"Accept": "text/xml"})
        self.assertEqual(
            resp.body,
           b'<result><item><id>1</id><name>first</name></item></result>'
        )

    def test_post_json_data(self):
        data = json.dumps({"name": "new"})
        resp = self.app.post(
            '/users', data,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(
            resp.body,
            b'{"id": 2, "name": "new"}'
        )

    def test_post_xml_data(self):
        data = '<data><name>new</name></data>'
        resp = self.app.post(
            '/users', data,
            headers={"Content-Type": "text/xml"}
        )
        self.assertEqual(
            resp.body,
            b'<result><id>2</id><name>new</name></result>'
        )

    def test_pass_request(self):
        resp = self.app.get('/needrequest')
        assert resp.json is True

    def test_resource_collection_get(self):
        resp = self.app.get('/author')
        assert len(resp.json) == 3
        assert resp.json[0]['name'] == 'Author 1'
        assert resp.json[1]['name'] == 'Author 2'
        assert resp.json[2]['name'] == 'Author 3'

    def test_resource_get(self):
        resp = self.app.get('/author/5')
        assert resp.json['name'] == 'Author 5'

    def test_resource_post(self):
        resp = self.app.post(
            '/author/5',
            json.dumps({"name": "Author 5"}),
            headers={"Content-Type": "application/json"}
        )
        assert resp.json['authorId'] == 5
        assert resp.json['name'] == 'Author 5'

    def test_server_error(self):
        resp = self.app.get('/divide?a=1&b=0', expect_errors=True)
        self.assertEqual(resp.json['faultcode'], 'Server')
        self.assertEqual(resp.status_code, 500)

    def test_client_error(self):
        resp = self.app.get(
            '/divide?a=1&c=0',
            headers={'Accept': 'application/json'},
            expect_errors=True
        )
        self.assertEqual(resp.json['faultcode'], 'Client')
        self.assertEqual(resp.status_code, 400)

    def test_runtime_error(self):
        resp = self.app.get(
            '/secret',
            headers={'Accept': 'application/json'},
            expect_errors=True
        )
        self.assertEqual(resp.json['faultcode'], 'Client')
        self.assertEqual(resp.status_code, 401)

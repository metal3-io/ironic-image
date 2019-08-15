import datetime

try:
    import json
except ImportError:
    import simplejson as json

from webtest import TestApp

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Unicode, Date, ForeignKey
from sqlalchemy.orm import relation

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from wsme import WSRoot
import wsme.types

from wsmeext.sqlalchemy.types import generate_types
from wsmeext.sqlalchemy.controllers import CRUDController

from six import u

engine = create_engine('sqlite:///')
DBSession = scoped_session(sessionmaker(autocommit=False, autoflush=False,
                                        bind=engine))
DBBase = declarative_base()

registry = wsme.types.Registry()


class DBPerson(DBBase):
    __tablename__ = 'person'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50))
    birthdate = Column(Date)

    addresses = relation('DBAddress')


class DBAddress(DBBase):
    __tablename__ = 'address'

    id = Column(Integer, primary_key=True)

    _person_id = Column('person_id', ForeignKey(DBPerson.id))

    street = Column(Unicode(50))
    city = Column(Unicode(50))

    person = relation(DBPerson)


globals().update(
    generate_types(DBPerson, DBAddress, makename=lambda s: s[2:],
                   registry=registry))


class PersonController(CRUDController):
    __saclass__ = DBPerson
    __dbsession__ = DBSession
    __registry__ = registry


class AddressController(CRUDController):
    __saclass__ = DBAddress
    __dbsession__ = DBSession
    __registry__ = registry


class Root(WSRoot):
    __registry__ = registry

    person = PersonController()
    address = AddressController()


class TestCRUDController():
    def setUp(self):
        DBBase.metadata.create_all(DBSession.bind)

        self.root = Root()
        self.root.getapi()
        self.root.addprotocol('restjson')

        self.app = TestApp(self.root.wsgiapp())

    def tearDown(self):
        DBBase.metadata.drop_all(DBSession.bind)

    def test_create(self):
        data = dict(data=dict(
            name=u('Pierre-Joseph'),
            birthdate=u('1809-01-15')
        ))
        r = self.app.post('/person/create', json.dumps(data),
                          headers={'Content-Type': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph')
        assert r['birthdate'] == u('1809-01-15')

    def test_PUT(self):
        data = dict(data=dict(
            name=u('Pierre-Joseph'),
            birthdate=u('1809-01-15')
        ))
        r = self.app.put('/person', json.dumps(data),
                         headers={'Content-Type': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph')
        assert r['birthdate'] == u('1809-01-15')

    def test_read(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        r = self.app.post('/person/read', '{"ref": {"id": %s}}' % pid,
                          headers={'Content-Type': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph')
        assert r['birthdate'] == u('1809-01-15')

    def test_GET(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        r = self.app.get('/person?ref.id=%s' % pid,
                         headers={'Accept': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph')
        assert r['birthdate'] == u('1809-01-15')

    def test_GET_bad_accept(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        r = self.app.get('/person?ref.id=%s' % pid,
                         headers={'Accept': 'text/plain'},
                         status=406)
        assert r.text == ("Unacceptable Accept type: text/plain not in "
                          "['application/json', 'text/javascript', "
                          "'application/javascript', 'text/xml']")

    def test_update(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        data = {
            "id": pid,
            "name": u('Pierre-Joseph Proudon')
        }
        r = self.app.post('/person/update', json.dumps(dict(data=data)),
                          headers={'Content-Type': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph Proudon')
        assert r['birthdate'] == u('1809-01-15')

    def test_POST(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        data = {
            "id": pid,
            "name": u('Pierre-Joseph Proudon')
        }
        r = self.app.post('/person', json.dumps(dict(data=data)),
                          headers={'Content-Type': 'application/json'})
        r = json.loads(r.text)
        print(r)
        assert r['name'] == u('Pierre-Joseph Proudon')
        assert r['birthdate'] == u('1809-01-15')

    def test_delete(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        r = self.app.post('/person/delete', json.dumps(
            dict(ref=dict(id=pid))),
            headers={
                'Content-Type': 'application/json'
            })
        print(r)
        assert DBSession.query(DBPerson).get(pid) is None

    def test_DELETE(self):
        p = DBPerson(
            name=u('Pierre-Joseph'),
            birthdate=datetime.date(1809, 1, 15))
        DBSession.add(p)
        DBSession.flush()
        pid = p.id
        r = self.app.delete('/person?ref.id=%s' % pid,
                            headers={'Content-Type': 'application/json'})
        print(r)
        assert DBSession.query(DBPerson).get(pid) is None

    def test_nothing(self):
        pass

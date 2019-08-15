import datetime

import wsmeext.sqlalchemy.types

from wsme.types import text, Unset, isarray

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relation

from six import u

SABase = declarative_base()


class SomeClass(SABase):
    __tablename__ = 'some_table'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))

    adate = Column(Date)


def test_complextype():
    class AType(wsmeext.sqlalchemy.types.Base):
        __saclass__ = SomeClass

    assert AType.id.datatype is int
    assert AType.name.datatype is text
    assert AType.adate.datatype is datetime.date

    a = AType()
    s = SomeClass(name=u('aname'), adate=datetime.date(2012, 6, 26))
    assert s.name == u('aname')

    a.from_instance(s)
    assert a.name == u('aname')
    assert a.adate == datetime.date(2012, 6, 26)

    a.name = u('test')
    del a.adate
    assert a.adate is Unset

    a.to_instance(s)
    assert s.name == u('test')
    assert s.adate == datetime.date(2012, 6, 26)


def test_generate():
    class A(SABase):
        __tablename__ = 'a'
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

        _b_id = Column(ForeignKey('b.id'))

        b = relation('B')

    class B(SABase):
        __tablename__ = 'b'
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

        alist = relation(A)

    newtypes = wsmeext.sqlalchemy.types.generate_types(A, B)

    assert newtypes['A'].id.datatype is int
    assert newtypes['A'].b.datatype is newtypes['B']
    assert newtypes['B'].id.datatype is int
    assert isarray(newtypes['B'].alist.datatype)
    assert newtypes['B'].alist.datatype.item_type is newtypes['A']

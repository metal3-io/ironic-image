import datetime
import decimal
import logging

import six

from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.properties import ColumnProperty, RelationProperty

import sqlalchemy.types

import wsme.types

log = logging.getLogger(__name__)


class SQLAlchemyRegistry(object):
    @classmethod
    def get(cls, registry):
        if not hasattr(registry, 'sqlalchemy'):
            registry.sqlalchemy = cls()
        return registry.sqlalchemy

    def __init__(self):
        self.types = {}
        self.satypeclasses = {
            sqlalchemy.types.Integer: int,
            sqlalchemy.types.Boolean: bool,
            sqlalchemy.types.Float: float,
            sqlalchemy.types.Numeric: decimal.Decimal,
            sqlalchemy.types.Date: datetime.date,
            sqlalchemy.types.Time: datetime.time,
            sqlalchemy.types.DateTime: datetime.datetime,
            sqlalchemy.types.String: wsme.types.text,
            sqlalchemy.types.Unicode: wsme.types.text,
        }

    def getdatatype(self, sadatatype):
        if sadatatype.__class__ in self.satypeclasses:
            return self.satypeclasses[sadatatype.__class__]
        elif sadatatype in self.types:
            return self.types[sadatatype]
        else:
            return sadatatype.__name__


def register_saclass(registry, saclass, typename=None):
    """Associate a webservice type name to a SQLAlchemy mapped class.
    The default typename if the saclass name itself.
    """
    if typename is None:
        typename = saclass.__name__

    SQLAlchemyRegistry.get(registry).types[saclass] = typename


class wsattr(wsme.types.wsattr):
    def __init__(self, datatype, saproperty=None, **kw):
        super(wsattr, self).__init__(datatype, **kw)
        self.saname = saproperty.key
        self.saproperty = saproperty
        self.isrelation = isinstance(saproperty, RelationProperty)


def make_wsattr(registry, saproperty):
    datatype = None
    if isinstance(saproperty, ColumnProperty):
        if len(saproperty.columns) > 1:
            log.warning("Cannot handle multi-column ColumnProperty")
            return None
        datatype = SQLAlchemyRegistry.get(registry).getdatatype(
            saproperty.columns[0].type)
    elif isinstance(saproperty, RelationProperty):
        other_saclass = saproperty.mapper.class_
        datatype = SQLAlchemyRegistry.get(registry).getdatatype(other_saclass)
        if saproperty.uselist:
            datatype = [datatype]
    else:
        log.warning("Don't know how to handle %s attributes" %
                    saproperty.__class__)

    if datatype:
        return wsattr(datatype, saproperty)


class BaseMeta(wsme.types.BaseMeta):
    def __new__(cls, name, bases, dct):
        if '__registry__' not in dct:
            dct['__registry__'] = wsme.types.registry
        return type.__new__(cls, name, bases, dct)

    def __init__(cls, name, bases, dct):
        saclass = getattr(cls, '__saclass__', None)
        if saclass:
            mapper = class_mapper(saclass)
            cls._pkey_attrs = []
            cls._ref_attrs = []
            for prop in mapper.iterate_properties:
                key = prop.key
                if hasattr(cls, key):
                    continue
                if key.startswith('_'):
                    continue
                attr = make_wsattr(cls.__registry__, prop)
                if attr is not None:
                    setattr(cls, key, attr)

                if attr and isinstance(prop, ColumnProperty) and \
                        prop.columns[0] in mapper.primary_key:
                    cls._pkey_attrs.append(attr)
                    cls._ref_attrs.append(attr)

            register_saclass(cls.__registry__, cls.__saclass__, cls.__name__)
        super(BaseMeta, cls).__init__(name, bases, dct)


class Base(six.with_metaclass(BaseMeta, wsme.types.Base)):
    def __init__(self, instance=None, keyonly=False, attrs=None, eagerload=[]):
        if instance:
            self.from_instance(instance, keyonly, attrs, eagerload)

    def from_instance(self, instance, keyonly=False, attrs=None, eagerload=[]):
        if keyonly:
            attrs = self._pkey_attrs + self._ref_attrs
        for attr in self._wsme_attributes:
            if not isinstance(attr, wsattr):
                continue
            if attrs and not attr.isrelation and attr.name not in attrs:
                continue
            if attr.isrelation and attr.name not in eagerload:
                continue
            value = getattr(instance, attr.saname)
            if attr.isrelation:
                attr_keyonly = attr.name not in eagerload
                attr_attrs = None
                attr_eagerload = []
                if not attr_keyonly:
                    attr_attrs = [
                        aname[len(attr.name) + 1:]
                        for aname in attrs
                        if aname.startswith(attr.name + '.')
                    ]
                    attr_eagerload = [
                        aname[len(attr.name) + 1:]
                        for aname in eagerload
                        if aname.startswith(attr.name + '.')
                    ]
                if attr.saproperty.uselist:
                    value = [
                        attr.datatype.item_type(
                            o,
                            keyonly=attr_keyonly,
                            attrs=attr_attrs,
                            eagerload=attr_eagerload
                        )
                        for o in value
                    ]
                else:
                    value = attr.datatype(
                        value,
                        keyonly=attr_keyonly,
                        attrs=attr_attrs,
                        eagerload=attr_eagerload
                    )
            attr.__set__(self, value)

    def to_instance(self, instance):
        for attr in self._wsme_attributes:
            if isinstance(attr, wsattr):
                value = attr.__get__(self, self.__class__)
                if value is not wsme.types.Unset:
                    setattr(instance, attr.saname, value)

    def get_ref_criterion(self):
        """Returns a criterion that match a database object
        having the pkey/ref attribute values of this webservice object"""
        criterions = []
        for attr in self._pkey_attrs + self._ref_attrs:
            value = attr.__get__(self, self.__class__)
            if value is not wsme.types.Unset:
                criterions.append(attr.saproperty == value)


def generate_types(*classes, **kw):
    registry = kw.pop('registry', wsme.types.registry)
    prefix = kw.pop('prefix', '')
    postfix = kw.pop('postfix', '')
    makename = kw.pop('makename', lambda s: prefix + s + postfix)

    newtypes = {}
    for c in classes:
        if isinstance(c, list):
            newtypes.update(generate_types(c))
        else:
            name = makename(c.__name__)
            newtypes[name] = BaseMeta(name, (Base, ), {
                '__saclass__': c,
                '__registry__': registry
            })
    return newtypes

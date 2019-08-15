import wsme
import wsme.types

try:
    import simplejson as json
except ImportError:
    import json


class ReadResultBase(wsme.types.Base):
    total = int
    success = bool
    message = wsme.types.text


def make_readresult(datatype):
    ReadResult = type(
        datatype.__name__ + 'ReadResult',
        (ReadResultBase,), {
            'data': [datatype]
        }
    )
    return ReadResult


class DataStoreControllerMeta(type):
    def __init__(cls, name, bases, dct):
        if cls.__datatype__ is None:
            return
        if getattr(cls, '__readresulttype__', None) is None:
            cls.__readresulttype__ = make_readresult(cls.__datatype__)

        cls.create = wsme.expose(
            cls.__readresulttype__,
            extdirect_params_notation='positional')(cls.create)
        cls.create = wsme.validate(cls.__datatype__)(cls.create)

        cls.read = wsme.expose(
            cls.__readresulttype__,
            extdirect_params_notation='named')(cls.read)
        cls.read = wsme.validate(str, str, int, int, int)(cls.read)

        cls.update = wsme.expose(
            cls.__readresulttype__,
            extdirect_params_notation='positional')(cls.update)
        cls.update = wsme.validate(cls.__datatype__)(cls.update)

        cls.destroy = wsme.expose(
            cls.__readresulttype__,
            extdirect_params_notation='positional')(cls.destroy)
        cls.destroy = wsme.validate(cls.__idtype__)(cls.destroy)


class DataStoreControllerMixin(object):
    __datatype__ = None
    __idtype__ = int

    __readresulttype__ = None

    def create(self, obj):
        pass

    def read(self, query=None, sort=None, page=None, start=None, limit=None):
        pass

    def update(self, obj):
        pass

    def destroy(self, obj_id):
        pass

    def model(self):
        tpl = """
Ext.define('%(appns)s.model.%(classname)s', {
    extend: 'Ext.data.Model',
    fields: %(fields)s,

    proxy: {
        type: 'direct',
        api: {
            create: %(appns)s.%(controllerns)s.create,
            read: %(appns)s.%(controllerns)s.read,
            update: %(appns)s.%(controllerns)s.update,
            destroy: %(appns)s.%(controllerns)s.destroy
        },
        reader: {
            root: 'data'
        }
    }
});
        """
        fields = [
            attr.name for attr in self.__datatype__._wsme_attributes
        ]
        d = {
            'appns': 'Demo',
            'controllerns': 'stores.' + self.__datatype__.__name__.lower(),
            'classname': self.__datatype__.__name__,
            'fields': json.dumps(fields)
        }
        return tpl % d

    def store(self):
        tpl = """
Ext.define('%(appns)s.store.%(classname)s', {
    extend: 'Ext.data.Store',
    model: '%(appns)s.model.%(classname)s'
});
"""
        d = {
            'appns': 'Demo',
            'classname': self.__datatype__.__name__,
        }

        return tpl % d


DataStoreController = DataStoreControllerMeta(
    'DataStoreController',
    (DataStoreControllerMixin,), {}
)

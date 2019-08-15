from wsme.rest import expose, validate
import wsme.types

from wsmeext.sqlalchemy.types import SQLAlchemyRegistry


class CRUDControllerMeta(type):
    def __init__(cls, name, bases, dct):
        if cls.__saclass__ is not None:
            if cls.__registry__ is None:
                cls.__registry__ = wsme.types.registry
            if cls.__wstype__ is None:
                cls.__wstype__ = cls.__registry__.resolve_type(
                    SQLAlchemyRegistry.get(
                        cls.__registry__).getdatatype(cls.__saclass__))

            cls.create = expose(
                cls.__wstype__,
                method='PUT',
                wrap=True
            )(cls.create)
            cls.create = validate(cls.__wstype__)(cls.create)

            cls.read = expose(
                cls.__wstype__,
                method='GET',
                wrap=True
            )(cls.read)
            cls.read = validate(cls.__wstype__)(cls.read)

            cls.update = expose(
                cls.__wstype__,
                method='POST',
                wrap=True
            )(cls.update)
            cls.update = validate(cls.__wstype__)(cls.update)

            cls.delete = expose(
                method='DELETE',
                wrap=True
            )(cls.delete)
            cls.delete = validate(cls.__wstype__)(cls.delete)

        super(CRUDControllerMeta, cls).__init__(name, bases, dct)


class CRUDControllerBase(object):
    __registry__ = None
    __saclass__ = None
    __wstype__ = None
    __dbsession__ = None

    def _create_one(self, data):
        obj = self.__saclass__()
        data.to_instance(obj)
        self.__dbsession__.add(obj)
        return obj

    def _get_one(self, ref):
        q = self.__dbsession__.query(self.__saclass__)
        q = q.filter(ref.get_ref_criterion())
        return q.one()

    def _update_one(self, data):
        obj = self._get_one(data)
        if obj is None:
            raise ValueError("No match for data=%s" % data)
        data.to_instance(obj)
        return obj

    def _delete(self, ref):
        obj = self._get_one(ref)
        self.__dbsession__.delete(obj)

    def create(self, data):
        obj = self._create_one(data)
        self.__dbsession__.flush()
        return self.__wstype__(obj)

    def read(self, ref):
        obj = self._get_one(ref)
        return self.__wstype__(obj)

    def update(self, data):
        obj = self._update_one(data)
        self.__dbsession__.flush()
        return self.__wstype__(obj)

    def delete(self, ref):
        self._delete(ref)
        self.__dbsession__.flush()
        return None


CRUDController = CRUDControllerMeta(
    'CRUDController', (CRUDControllerBase,), {}
)

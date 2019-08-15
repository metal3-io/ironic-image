from wsmeext.extdirect import datastore


class SADataStoreController(datastore.DataStoreController):
    __dbsession__ = None
    __datatype__ = None

    def read(self, query=None, sort=None, page=None, start=None, limit=None):
        q = self.__dbsession__.query(self.__datatype__.__saclass__)
        total = q.count()
        if start is not None and limit is not None:
            q = q.slice(start, limit)
        return self.__readresulttype__(
            data=[
                self.__datatype__(o) for o in q
            ],
            success=True,
            total=total
        )

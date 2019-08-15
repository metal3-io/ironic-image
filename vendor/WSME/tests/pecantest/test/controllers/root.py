from pecan import expose
from webob.exc import status_map
from .ws import AuthorsController
from wsmeext.pecan import wsexpose


class RootController(object):
    authors = AuthorsController()

    @expose('error.html')
    def error(self, status):
        try:
            status = int(status)
        except ValueError:  # pragma: no cover
            status = 500
        message = getattr(status_map.get(status), 'explanation', '')
        return dict(status=status, message=message)

    @wsexpose()
    def divide_by_zero(self):
        1 / 0

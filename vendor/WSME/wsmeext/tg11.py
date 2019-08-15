from turbogears import config
import cherrypy
from cherrypy.filters.basefilter import BaseFilter
from turbogears.startup import call_on_startup, call_on_shutdown
from wsmeext.tg1 import wsexpose, wsvalidate
import wsmeext.tg1

__all__ = ['adapt', 'wsexpose', 'wsvalidate']


class WSMECherrypyFilter(BaseFilter):
    def __init__(self, controller):
        self.controller = controller
        self.webpath = None

    def on_start_resource(self):
        path = cherrypy.request.path
        if path.startswith(self.controller._wsroot._webpath):
            cherrypy.request.processRequestBody = False


def adapt(wsroot):
    wsroot._scan_api = wsmeext.tg1.scan_api
    controller = wsmeext.tg1.Controller(wsroot)
    filter_ = WSMECherrypyFilter(controller)

    def install_filter():
        filter_.webpath = config.get('server.webpath') or ''
        controller._wsroot._webpath = \
            filter_.webpath + controller._wsroot._webpath
        cherrypy.root._cp_filters.append(filter_)

    def uninstall_filter():
        cherrypy.root._cp_filters.remove(filter_)
        controller._wsroot._webpath = \
            controller._wsroot._webpath[len(filter_.webpath):]

    call_on_startup.append(install_filter)
    call_on_shutdown.insert(0, uninstall_filter)
    return controller

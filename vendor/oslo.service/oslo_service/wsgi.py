# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2010 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Utility methods for working with WSGI servers."""

from __future__ import print_function

import copy
import os
import socket

import eventlet
import eventlet.wsgi
import greenlet
from paste import deploy
import routes.middleware
import webob.dec
import webob.exc

from oslo_log import log as logging
from oslo_service._i18n import _
from oslo_service import _options
from oslo_service import service
from oslo_service import sslutils


LOG = logging.getLogger(__name__)


def list_opts():
    """Entry point for oslo-config-generator."""
    return [(None, copy.deepcopy(_options.wsgi_opts))]


def register_opts(conf):
    """Registers WSGI config options."""
    return conf.register_opts(_options.wsgi_opts)


class InvalidInput(Exception):
    message = _("Invalid input received: "
                "Unexpected argument for periodic task creation: %(arg)s.")


class Server(service.ServiceBase):
    """Server class to manage a WSGI server, serving a WSGI application."""

    # TODO(eezhova): Consider changing the default host value to prevent
    # possible binding to all interfaces. The most appropriate value seems
    # to be 127.0.0.1, but it has to be verified that the change wouldn't
    # break any consuming project.
    def __init__(self, conf, name, app, host='0.0.0.0', port=0,  # nosec
                 pool_size=None, protocol=eventlet.wsgi.HttpProtocol,
                 backlog=128, use_ssl=False, max_url_len=None,
                 logger_name='eventlet.wsgi.server',
                 socket_family=None, socket_file=None, socket_mode=None):
        """Initialize, but do not start, a WSGI server.

        :param conf: Instance of ConfigOpts.
        :param name: Pretty name for logging.
        :param app: The WSGI application to serve.
        :param host: IP address to serve the application.
        :param port: Port number to server the application.
        :param pool_size: Maximum number of eventlets to spawn concurrently.
        :param protocol: Protocol class.
        :param backlog: Maximum number of queued connections.
        :param use_ssl: Wraps the socket in an SSL context if True.
        :param max_url_len: Maximum length of permitted URLs.
        :param logger_name: The name for the logger.
        :param socket_family: Socket family.
        :param socket_file: location of UNIX socket.
        :param socket_mode: UNIX socket mode.
        :returns: None
        :raises: InvalidInput
        :raises: EnvironmentError
        """

        self.conf = conf
        self.conf.register_opts(_options.wsgi_opts)

        self.default_pool_size = self.conf.wsgi_default_pool_size

        # Allow operators to customize http requests max header line size.
        eventlet.wsgi.MAX_HEADER_LINE = conf.max_header_line
        self.name = name
        self.app = app
        self._server = None
        self._protocol = protocol
        self.pool_size = pool_size or self.default_pool_size
        self._pool = eventlet.GreenPool(self.pool_size)
        self._logger = logging.getLogger(logger_name)
        self._use_ssl = use_ssl
        self._max_url_len = max_url_len
        self.client_socket_timeout = conf.client_socket_timeout or None

        if backlog < 1:
            raise InvalidInput(reason=_('The backlog must be more than 0'))

        if not socket_family or socket_family in [socket.AF_INET,
                                                  socket.AF_INET6]:
            self.socket = self._get_socket(host, port, backlog)
        elif hasattr(socket, "AF_UNIX") and socket_family == socket.AF_UNIX:
            self.socket = self._get_unix_socket(socket_file, socket_mode,
                                                backlog)
        else:
            raise ValueError(_("Unsupported socket family: %s"), socket_family)

        (self.host, self.port) = self.socket.getsockname()[0:2]

        if self._use_ssl:
            sslutils.is_enabled(conf)

    def _get_socket(self, host, port, backlog):
        bind_addr = (host, port)
        # TODO(dims): eventlet's green dns/socket module does not actually
        # support IPv6 in getaddrinfo(). We need to get around this in the
        # future or monitor upstream for a fix
        try:
            info = socket.getaddrinfo(bind_addr[0],
                                      bind_addr[1],
                                      socket.AF_UNSPEC,
                                      socket.SOCK_STREAM)[0]
            family = info[0]
            bind_addr = info[-1]
        except Exception:
            family = socket.AF_INET

        try:
            sock = eventlet.listen(bind_addr, family, backlog=backlog)
        except EnvironmentError:
            LOG.error("Could not bind to %(host)s:%(port)s",
                      {'host': host, 'port': port})
            raise
        sock = self._set_socket_opts(sock)
        LOG.info("%(name)s listening on %(host)s:%(port)s",
                 {'name': self.name, 'host': host, 'port': port})
        return sock

    def _get_unix_socket(self, socket_file, socket_mode, backlog):
        sock = eventlet.listen(socket_file, family=socket.AF_UNIX,
                               backlog=backlog)
        if socket_mode is not None:
            os.chmod(socket_file, socket_mode)
        LOG.info("%(name)s listening on %(socket_file)s:",
                 {'name': self.name, 'socket_file': socket_file})
        return sock

    def start(self):
        """Start serving a WSGI application.

        :returns: None
        """
        # The server socket object will be closed after server exits,
        # but the underlying file descriptor will remain open, and will
        # give bad file descriptor error. So duplicating the socket object,
        # to keep file descriptor usable.

        self.dup_socket = self.socket.dup()

        if self._use_ssl:
            self.dup_socket = sslutils.wrap(self.conf, self.dup_socket)

        wsgi_kwargs = {
            'func': eventlet.wsgi.server,
            'sock': self.dup_socket,
            'site': self.app,
            'protocol': self._protocol,
            'custom_pool': self._pool,
            'log': self._logger,
            'log_format': self.conf.wsgi_log_format,
            'debug': False,
            'keepalive': self.conf.wsgi_keep_alive,
            'socket_timeout': self.client_socket_timeout
            }

        if self._max_url_len:
            wsgi_kwargs['url_length_limit'] = self._max_url_len

        self._server = eventlet.spawn(**wsgi_kwargs)

    def _set_socket_opts(self, _socket):
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # sockets can hang around forever without keepalive
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # This option isn't available in the OS X version of eventlet
        if hasattr(socket, 'TCP_KEEPIDLE'):
            _socket.setsockopt(socket.IPPROTO_TCP,
                               socket.TCP_KEEPIDLE,
                               self.conf.tcp_keepidle)

        return _socket

    def reset(self):
        """Reset server greenpool size to default.

        :returns: None

        """
        self._pool.resize(self.pool_size)

    def stop(self):
        """Stops eventlet server. Doesn't allow accept new connecting.

        :returns: None

        """
        LOG.info("Stopping WSGI server.")

        if self._server is not None:
            # let eventlet close socket
            self._pool.resize(0)
            self._server.kill()

    def wait(self):
        """Block, until the server has stopped.

        Waits on the server's eventlet to finish, then returns.

        :returns: None

        """
        try:
            if self._server is not None:
                num = self._pool.running()
                LOG.debug("Waiting WSGI server to finish %d requests.", num)
                self._pool.waitall()
        except greenlet.GreenletExit:
            LOG.info("WSGI server has stopped.")


class Request(webob.Request):
    pass


class Router(object):
    """WSGI middleware that maps incoming requests to WSGI apps."""

    def __init__(self, mapper):
        """Create a router for the given routes.Mapper.

        Each route in `mapper` must specify a 'controller', which is a
        WSGI app to call.  You'll probably want to specify an 'action' as
        well and have your controller be an object that can route
        the request to the action-specific method.

        Examples:
          mapper = routes.Mapper()
          sc = ServerController()

          # Explicit mapping of one route to a controller+action
          mapper.connect(None, '/svrlist', controller=sc, action='list')

          # Actions are all implicitly defined
          mapper.resource('server', 'servers', controller=sc)

          # Pointing to an arbitrary WSGI app.  You can specify the
          # {path_info:.*} parameter so the target app can be handed just that
          # section of the URL.
          mapper.connect(None, '/v1.0/{path_info:.*}', controller=BlogApp())

        """
        self.map = mapper
        self._router = routes.middleware.RoutesMiddleware(self._dispatch,
                                                          self.map)

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        """Route the incoming request to a controller based on self.map.

        If no match, return a 404.

        """
        return self._router

    @staticmethod
    @webob.dec.wsgify(RequestClass=Request)
    def _dispatch(req):
        """Dispatch the request to the appropriate controller.

        Called by self._router after matching the incoming request to a route
        and putting the information into req.environ.  Either returns 404
        or the routed WSGI app's response.

        """
        match = req.environ['wsgiorg.routing_args'][1]
        if not match:
            return webob.exc.HTTPNotFound()
        app = match['controller']
        return app


class ConfigNotFound(Exception):
    def __init__(self, path):
        msg = _('Could not find config at %(path)s') % {'path': path}
        super(ConfigNotFound, self).__init__(msg)


class PasteAppNotFound(Exception):
    def __init__(self, name, path):
        msg = (_("Could not load paste app '%(name)s' from %(path)s") %
               {'name': name, 'path': path})
        super(PasteAppNotFound, self).__init__(msg)


class Loader(object):
    """Used to load WSGI applications from paste configurations."""

    def __init__(self, conf):
        """Initialize the loader, and attempt to find the config.

        :param conf: Application config
        :returns: None

        """
        conf.register_opts(_options.wsgi_opts)
        self.config_path = None

        config_path = conf.api_paste_config
        if not os.path.isabs(config_path):
            self.config_path = conf.find_file(config_path)
        elif os.path.exists(config_path):
            self.config_path = config_path

        if not self.config_path:
            raise ConfigNotFound(path=config_path)

    def load_app(self, name):
        """Return the paste URLMap wrapped WSGI application.

        :param name: Name of the application to load.
        :returns: Paste URLMap object wrapping the requested application.
        :raises: PasteAppNotFound

        """
        try:
            LOG.debug("Loading app %(name)s from %(path)s",
                      {'name': name, 'path': self.config_path})
            return deploy.loadapp("config:%s" % self.config_path, name=name)
        except LookupError:
            LOG.exception("Couldn't lookup app: %s", name)
            raise PasteAppNotFound(name=name, path=self.config_path)

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

"""Multicast DNS implementation for API discovery.

This implementation follows RFC 6763 as clarified by the API SIG guideline
https://review.opendev.org/651222.
"""

import collections
import socket
import time

from oslo_config import cfg
from oslo_config import types as cfg_types
from oslo_log import log as logging
from six.moves.urllib import parse
import zeroconf

from ironic_lib.common.i18n import _
from ironic_lib import exception


opts = [
    cfg.IntOpt('registration_attempts',
               min=1, default=5,
               help='Number of attempts to register a service. Currently '
                    'has to be larger than 1 because of race conditions '
                    'in the zeroconf library.'),
    cfg.IntOpt('lookup_attempts',
               min=1, default=3,
               help='Number of attempts to lookup a service.'),
    cfg.Opt('params',
            # This is required for values that contain commas.
            type=cfg_types.Dict(cfg_types.String(quotes=True)),
            default={},
            help='Additional parameters to pass for the registered '
                 'service.'),
    cfg.ListOpt('interfaces',
                help='List of IP addresses of interfaces to use for mDNS. '
                     'Defaults to all interfaces on the system.'),
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='mdns', title='Options for multicast DNS')
CONF.register_group(opt_group)
CONF.register_opts(opts, opt_group)

LOG = logging.getLogger(__name__)

_MDNS_DOMAIN = '_openstack._tcp.local.'
_endpoint = collections.namedtuple('Endpoint',
                                   ['ip', 'hostname', 'port', 'params'])


class Zeroconf(object):
    """Multicast DNS implementation client and server.

    Uses threading internally, so there is no start method. It starts
    automatically on creation.

    .. warning::
        The underlying library does not yet support IPv6.
    """

    def __init__(self):
        """Initialize and start the mDNS server."""
        interfaces = (CONF.mdns.interfaces if CONF.mdns.interfaces
                      else zeroconf.InterfaceChoice.All)
        self._zc = zeroconf.Zeroconf(interfaces=interfaces)
        self._registered = []

    def register_service(self, service_type, endpoint, params=None):
        """Register a service.

        This call announces the new services via multicast and instructs the
        built-in server to respond to queries about it.

        :param service_type: OpenStack service type, e.g. "baremetal".
        :param endpoint: full endpoint to reach the service.
        :param params: optional properties as a dictionary.
        :raises: :exc:`.ServiceRegistrationFailure` if the service cannot be
            registered, e.g. because of conflicts.
        """
        try:
            parsed = _parse_endpoint(endpoint)
        except socket.error as ex:
            msg = (_("Cannot resolve the host name of %(endpoint)s: "
                     "%(error)s. Hint: only IPv4 is supported for now.") %
                   {'endpoint': endpoint, 'error': ex})
            raise exception.ServiceRegistrationFailure(
                service=service_type, error=msg)

        all_params = CONF.mdns.params.copy()
        if params:
            all_params.update(params)
        all_params.update(parsed.params)

        # TODO(dtantsur): allow overriding TTL values via configuration when
        # https://github.com/jstasiak/python-zeroconf/commit/ecc021b7a3cec863eed5a3f71a1f28e3026c25b0
        # is released.
        info = zeroconf.ServiceInfo(_MDNS_DOMAIN,
                                    '%s.%s' % (service_type, _MDNS_DOMAIN),
                                    parsed.ip, parsed.port,
                                    properties=all_params,
                                    server=parsed.hostname)

        LOG.debug('Registering %s via mDNS', info)
        # Work around a potential race condition in the registration code:
        # https://github.com/jstasiak/python-zeroconf/issues/163
        delay = 0.1
        try:
            for attempt in range(CONF.mdns.registration_attempts):
                try:
                    self._zc.register_service(info)
                except zeroconf.NonUniqueNameException:
                    LOG.debug('Could not register %s - conflict', info)
                    if attempt == CONF.mdns.registration_attempts - 1:
                        raise
                    # reset the cache to purge learned records and retry
                    self._zc.cache = zeroconf.DNSCache()
                    time.sleep(delay)
                    delay *= 2
                else:
                    break
        except zeroconf.Error as exc:
            raise exception.ServiceRegistrationFailure(
                service=service_type, error=exc)

        self._registered.append(info)

    def get_endpoint(self, service_type):
        """Get an endpoint and its properties from mDNS.

        If the requested endpoint is already in the built-in server cache, and
        its TTL is not exceeded, the cached value is returned.

        :param service_type: OpenStack service type.
        :returns: tuple (endpoint URL, properties as a dict).
        :raises: :exc:`.ServiceLookupFailure` if the service cannot be found.
        """
        delay = 0.1
        for attempt in range(CONF.mdns.lookup_attempts):
            name = '%s.%s' % (service_type, _MDNS_DOMAIN)
            info = self._zc.get_service_info(name, name)
            if info is not None:
                break
            elif attempt == CONF.mdns.lookup_attempts - 1:
                raise exception.ServiceLookupFailure(service=service_type)
            else:
                time.sleep(delay)
                delay *= 2

        # TODO(dtantsur): IPv6 support
        address = socket.inet_ntoa(info.address)
        properties = {}
        for key, value in info.properties.items():
            try:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
            except UnicodeError as exc:
                raise exception.ServiceLookupFailure(
                    _('Invalid properties for service %(svc)s. Cannot decode '
                      'key %(key)r: %(exc)r') %
                    {'svc': service_type, 'key': key, 'exc': exc})

            try:
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
            except UnicodeError as exc:
                LOG.debug('Cannot convert value %(value)r for key %(key)s '
                          'to string, assuming binary: %(exc)s',
                          {'key': key, 'value': value, 'exc': exc})

            properties[key] = value

        path = properties.pop('path', '')
        protocol = properties.pop('protocol', None)
        if not protocol:
            if info.port == 80:
                protocol = 'http'
            else:
                protocol = 'https'

        if info.server.endswith('.local.'):
            # Local hostname means that the catalog lists an IP address,
            # so use it
            host = address
        else:
            # Otherwise use the provided hostname.
            host = info.server.rstrip('.')

        return ('{proto}://{host}:{port}{path}'.format(proto=protocol,
                                                       host=host,
                                                       port=info.port,
                                                       path=path),
                properties)

    def close(self):
        """Shut down mDNS and unregister services.

        .. note::
            If another server is running for the same services, it will
            re-register them immediately.
        """
        for info in self._registered:
            try:
                self._zc.unregister_service(info)
            except Exception:
                LOG.exception('Cound not unregister mDNS service %s', info)
        self._zc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def get_endpoint(service_type):
    """Get an endpoint and its properties from mDNS.

    If the requested endpoint is already in the built-in server cache, and
    its TTL is not exceeded, the cached value is returned.

    :param service_type: OpenStack service type.
    :returns: tuple (endpoint URL, properties as a dict).
    :raises: :exc:`.ServiceLookupFailure` if the service cannot be found.
    """
    with Zeroconf() as zc:
        return zc.get_endpoint(service_type)


def _parse_endpoint(endpoint):
    params = {}
    url = parse.urlparse(endpoint)
    port = url.port

    if port is None:
        if url.scheme == 'https':
            port = 443
        else:
            port = 80

    hostname = url.hostname
    # FIXME(dtantsur): the zeroconf library does not support IPv6, use IPv4
    # only resolving for now.
    ip = socket.gethostbyname(hostname)
    if ip == hostname:
        # we need a host name for the service record. if what we have in
        # the catalog is an IP address, use the local hostname instead
        hostname = None
    # zeroconf requires addresses in network format (and see above re IPv6)
    ip = socket.inet_aton(ip)

    # avoid storing information that can be derived from existing data
    if url.path not in ('', '/'):
        params['path'] = url.path

    if (not (port == 80 and url.scheme == 'http')
            and not (port == 443 and url.scheme == 'https')):
        params['protocol'] = url.scheme

    # zeroconf is pretty picky about having the trailing dot
    if hostname is not None and not hostname.endswith('.'):
        hostname += '.'

    return _endpoint(ip, hostname, port, params)


def list_opts():
    """Entry point for oslo-config-generator."""
    return [('mdns', opts)]

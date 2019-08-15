# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import socket

from ironicclient import client
from ironicclient import exceptions as ironic_exc
import netaddr
from oslo_config import cfg
import retrying

from ironic_inspector.common.i18n import _
from ironic_inspector.common import keystone
from ironic_inspector import utils

CONF = cfg.CONF
LOG = utils.getProcessingLogger(__name__)

# See https://docs.openstack.org/ironic/latest/contributor/states.html  # noqa
VALID_STATES = frozenset(['enroll', 'manageable', 'inspecting', 'inspect wait',
                          'inspect failed'])

# States where an instance is deployed and an admin may be doing something.
VALID_ACTIVE_STATES = frozenset(['active', 'rescue'])

# 1.38 is the latest API version in the Queens release series, 10.1.0.
# 1.46 is the latest API version in the Rocky release series, 11.1.0.
# 1.56 is the latest API version in the Stein release series, 12.1.0
# NOTE(mgoddard): This should be updated with each release to ensure that
# inspector is able to use the latest ironic API. In particular, this version
# is used when processing introspection rules, and is the default version used
# by processing plugins.
DEFAULT_IRONIC_API_VERSION = ['1.38', '1.46', '1.56']

IRONIC_SESSION = None


class NotFound(utils.Error):
    """Node not found in Ironic."""

    def __init__(self, node_ident, code=404, *args, **kwargs):
        msg = _('Node %s was not found in Ironic') % node_ident
        super(NotFound, self).__init__(msg, code, *args, **kwargs)


def reset_ironic_session():
    """Reset the global session variable.

    Mostly useful for unit tests.
    """
    global IRONIC_SESSION
    IRONIC_SESSION = None


def get_ipmi_address(node):
    """Get the BMC address defined in node.driver_info dictionary

    Possible names of BMC address value examined in order of list
    ['ipmi_address'] + CONF.ipmi_address_fields. The value could
    be an IP address or a hostname. DNS lookup performed for the
    first non empty value.

    The first valid BMC address value returned along with
    it's v4 and v6 IP addresses.

    :param node: Node object with defined driver_info dictionary
    :return: tuple (ipmi_address, ipv4_address, ipv6_address)
    """
    none_address = None, None, None
    ipmi_fields = ['ipmi_address'] + CONF.ipmi_address_fields
    # NOTE(sambetts): IPMI Address is useless to us if bridging is enabled so
    # just ignore it and return None
    if node.driver_info.get("ipmi_bridging", "no") != "no":
        return none_address
    for name in ipmi_fields:
        value = node.driver_info.get(name)
        if not value:
            continue

        ipv4 = None
        ipv6 = None
        try:
            addrinfo = socket.getaddrinfo(value, None, 0, 0, socket.SOL_TCP)
            for family, socket_type, proto, canon_name, sockaddr in addrinfo:
                ip = sockaddr[0]
                if netaddr.IPAddress(ip).is_loopback():
                    LOG.warning('Ignoring loopback BMC address %s', ip,
                                node_info=node)
                elif family == socket.AF_INET:
                    ipv4 = ip
                elif family == socket.AF_INET6:
                    ipv6 = ip
        except socket.gaierror:
            msg = _('Failed to resolve the hostname (%(value)s)'
                    ' for node %(uuid)s')
            raise utils.Error(msg % {'value': value,
                                     'uuid': node.uuid},
                              node_info=node)

        return (value, ipv4, ipv6) if ipv4 or ipv6 else none_address
    return none_address


def get_client(token=None,
               api_version=DEFAULT_IRONIC_API_VERSION):  # pragma: no cover
    """Get Ironic client instance."""
    global IRONIC_SESSION

    if not IRONIC_SESSION:
        IRONIC_SESSION = keystone.get_session('ironic')

    args = {
        'session': IRONIC_SESSION,
        'os_ironic_api_version': api_version,
        'max_retries': CONF.ironic.max_retries,
        'retry_interval': CONF.ironic.retry_interval
    }

    if token is not None:
        args['token'] = token

    endpoint = keystone.get_adapter('ironic',
                                    session=IRONIC_SESSION).get_endpoint()
    if not endpoint:
        raise utils.Error(
            _('Cannot find the bare metal endpoint either in Keystone or '
              'in the configuration'), code=500)
    return client.get_client(1, endpoint=endpoint, **args)


def check_provision_state(node):
    """Sanity checks the provision state of the node.

    :param node: An API client returned node object describing
                 the baremetal node according to ironic's node
                 data model.
    :returns: None if no action is to be taken, True if the
              power node state should not be modified.
    :raises: Error on an invalid state being detected.
    """
    state = node.provision_state.lower()
    if state not in VALID_STATES:
        if (CONF.processing.permit_active_introspection
                and state in VALID_ACTIVE_STATES):
            # Hey, we can leave the power on! Lets return
            # True to let the caller know.
            return True

        msg = _('Invalid provision state for introspection: '
                '"%(state)s", valid states are "%(valid)s"')
        raise utils.Error(msg % {'state': state,
                                 'valid': list(VALID_STATES)},
                          node_info=node)


def capabilities_to_dict(caps):
    """Convert the Node's capabilities into a dictionary."""
    if not caps:
        return {}
    return dict([key.split(':', 1) for key in caps.split(',')])


def dict_to_capabilities(caps_dict):
    """Convert a dictionary into a string with the capabilities syntax."""
    return ','.join(["%s:%s" % (key, value)
                     for key, value in caps_dict.items()
                     if value is not None])


def get_node(node_id, ironic=None, **kwargs):
    """Get a node from Ironic.

    :param node_id: node UUID or name.
    :param ironic: ironic client instance.
    :param kwargs: arguments to pass to Ironic client.
    :raises: Error on failure
    """
    ironic = ironic if ironic is not None else get_client()

    try:
        return ironic.node.get(node_id, **kwargs)
    except ironic_exc.NotFound:
        raise NotFound(node_id)
    except ironic_exc.HttpError as exc:
        raise utils.Error(_("Cannot get node %(node)s: %(exc)s") %
                          {'node': node_id, 'exc': exc})


@retrying.retry(
    retry_on_exception=lambda exc: isinstance(exc, ironic_exc.ClientException),
    stop_max_attempt_number=5, wait_fixed=1000)
def call_with_retries(func, *args, **kwargs):
    """Call an ironic client function retrying all errors.

    If an ironic client exception is raised, try calling the func again,
    at most 5 times, waiting 1 sec between each call. If on the 5th attempt
    the func raises again, the exception is propagated to the caller.
    """
    return func(*args, **kwargs)


def lookup_node_by_macs(macs, introspection_data=None,
                        ironic=None, fail=False):
    """Find a node by its MACs."""
    if ironic is None:
        ironic = get_client()

    nodes = set()
    for mac in macs:
        ports = ironic.port.list(address=mac)
        if not ports:
            continue
        elif fail:
            raise utils.Error(
                _('Port %(mac)s already exists, uuid: %(uuid)s') %
                {'mac': mac, 'uuid': ports[0].uuid}, data=introspection_data)
        else:
            nodes.update(p.node_uuid for p in ports)

    if len(nodes) > 1:
        raise utils.Error(_('MAC addresses %(macs)s correspond to more than '
                            'one node: %(nodes)s') %
                          {'macs': ', '.join(macs),
                           'nodes': ', '.join(nodes)},
                          data=introspection_data)
    elif nodes:
        return nodes.pop()


def lookup_node_by_bmc_addresses(addresses, introspection_data=None,
                                 ironic=None, fail=False):
    """Find a node by its BMC address."""
    if ironic is None:
        ironic = get_client()

    # FIXME(aarefiev): it's not effective to fetch all nodes, and may
    #                  impact on performance on big clusters
    nodes = ironic.node.list(fields=('uuid', 'driver_info'), limit=0)
    found = set()
    for node in nodes:
        bmc_address, bmc_ipv4, bmc_ipv6 = get_ipmi_address(node)
        for addr in addresses:
            if addr not in (bmc_ipv4, bmc_ipv6):
                continue
            elif fail:
                raise utils.Error(
                    _('Node %(uuid)s already has BMC address %(addr)s') %
                    {'addr': addr, 'uuid': node.uuid},
                    data=introspection_data)
            else:
                found.add(node.uuid)

    if len(found) > 1:
        raise utils.Error(_('BMC addresses %(addr)s correspond to more than '
                            'one node: %(nodes)s') %
                          {'addr': ', '.join(addresses),
                           'nodes': ', '.join(found)},
                          data=introspection_data)
    elif found:
        return found.pop()


def lookup_node(macs=None, bmc_addresses=None, introspection_data=None,
                ironic=None):
    """Lookup a node in the ironic database."""
    node = node2 = None

    if macs:
        node = lookup_node_by_macs(macs, ironic=ironic)
    if bmc_addresses:
        node2 = lookup_node_by_bmc_addresses(bmc_addresses, ironic=ironic)

    if node and node2 and node != node2:
        raise utils.Error(_('MAC addresses %(mac)s and BMC addresses %(addr)s '
                            'correspond to different nodes: %(node1)s and '
                            '%(node2)s') %
                          {'mac': ', '.join(macs),
                           'addr': ', '.join(bmc_addresses),
                           'node1': node, 'node2': node2})

    return node or node2

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

import datetime
import logging as pylog

import futurist
from ironicclient.v1 import node
from keystonemiddleware import auth_token
from oslo_config import cfg
from oslo_log import log
from oslo_middleware import cors as cors_middleware
import pytz
from tooz import coordination

from ironic_inspector.common.i18n import _
from ironic_inspector import policy

CONF = cfg.CONF

_EXECUTOR = None


def get_ipmi_address_from_data(introspection_data):
    try:
        result = introspection_data['inventory']['bmc_address']
    except KeyError:
        result = introspection_data.get('ipmi_address')

    if result in ('', '0.0.0.0'):
        # ipmitool can return these values, if it does not know the address
        return None
    else:
        return result


def get_ipmi_v6address_from_data(introspection_data):
    try:
        result = introspection_data['inventory']['bmc_v6address']
    except KeyError:
        result = introspection_data.get('ipmi_v6address')

    if result in ('', '::/0'):
        # ipmitool can return these values, if it does not know the address
        return None
    else:
        return result


def get_pxe_mac(introspection_data):
    pxe_mac = introspection_data.get('boot_interface')
    if pxe_mac and '-' in pxe_mac:
        # pxelinux format: 01-aa-bb-cc-dd-ee-ff
        pxe_mac = pxe_mac.split('-', 1)[1]
        pxe_mac = pxe_mac.replace('-', ':').lower()
    return pxe_mac


def processing_logger_prefix(data=None, node_info=None):
    """Calculate prefix for logging.

    Tries to use:
    * node UUID, node._state
    * node PXE MAC,
    * node BMC address

    :param data: introspection data
    :param node_info: NodeInfo or ironic node object
    :return: logging prefix as a string
    """
    # TODO(dtantsur): try to get MAC and BMC address for node_info as well
    parts = []
    data = data or {}

    if node_info is not None:
        if isinstance(node_info, node.Node):
            parts.append(str(node_info.uuid))
        else:
            parts.append(str(node_info))

    pxe_mac = get_pxe_mac(data)
    if pxe_mac:
        parts.append('MAC %s' % pxe_mac)

    bmc_address = get_ipmi_address_from_data(data) if data else None
    if bmc_address:
        parts.append('BMC %s' % bmc_address)

    if parts:
        return _('[node: %s]') % ' '.join(parts)
    else:
        return _('[unidentified node]')


class ProcessingLoggerAdapter(log.KeywordArgumentAdapter):
    def process(self, msg, kwargs):
        if 'data' not in kwargs and 'node_info' not in kwargs:
            return super(ProcessingLoggerAdapter, self).process(msg, kwargs)

        data = kwargs.get('data', {})
        node_info = kwargs.get('node_info')
        prefix = processing_logger_prefix(data, node_info)

        msg, kwargs = super(ProcessingLoggerAdapter, self).process(msg, kwargs)
        return ('%s %s' % (prefix, msg)), kwargs


def getProcessingLogger(name):
    # We can't use getLogger from oslo_log, as it's an adapter itself
    logger = pylog.getLogger(name)
    return ProcessingLoggerAdapter(logger, {})


LOG = getProcessingLogger(__name__)


class Error(Exception):
    """Inspector exception."""

    def __init__(self, msg, code=400, log_level='error', **kwargs):
        super(Error, self).__init__(msg)
        getattr(LOG, log_level)(msg, **kwargs)
        self.http_code = code


class NotFoundInCacheError(Error):
    """Exception when node was not found in cache during processing."""

    def __init__(self, msg, code=404, **kwargs):
        super(NotFoundInCacheError, self).__init__(msg, code,
                                                   log_level='info', **kwargs)


class NodeStateRaceCondition(Error):
    """State mismatch between the DB and a node_info."""
    def __init__(self, *args, **kwargs):
        message = _('Node state mismatch detected between the DB and the '
                    'cached node_info object')
        kwargs.setdefault('code', 500)
        super(NodeStateRaceCondition, self).__init__(message, *args, **kwargs)


class NodeStateInvalidEvent(Error):
    """Invalid event attempted."""


class IntrospectionDataStoreDisabled(Error):
    """Introspection data store is disabled."""


class IntrospectionDataNotFound(NotFoundInCacheError):
    """Introspection data not found."""


def executor():
    """Return the current futures executor."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = futurist.GreenThreadPoolExecutor(
            max_workers=CONF.max_concurrency)
    return _EXECUTOR


def add_auth_middleware(app):
    """Add authentication middleware to Flask application.

    :param app: application.
    """
    auth_conf = dict(CONF.keystone_authtoken)
    auth_conf['delay_auth_decision'] = True
    app.wsgi_app = auth_token.AuthProtocol(app.wsgi_app, auth_conf)


def add_cors_middleware(app):
    """Create a CORS wrapper

    Attach ironic-inspector-specific defaults that must be included
    in all CORS responses.

    :param app: application
    """
    app.wsgi_app = cors_middleware.CORS(app.wsgi_app, CONF)


def check_auth(request, rule=None, target=None):
    """Check authentication on request.

    :param request: Flask request
    :param rule: policy rule to check the request against
    :raises: utils.Error if access is denied
    """
    if CONF.auth_strategy == 'noauth':
        return
    if not request.context.is_public_api:
        if request.headers.get('X-Identity-Status', '').lower() == 'invalid':
            raise Error(_('Authentication required'), code=401)
    target = {} if target is None else target
    if not policy.authorize(rule, target, request.context.to_policy_values()):
        raise Error(_("Access denied by policy"), code=403)


def get_valid_macs(data):
    """Get a list of valid MAC's from the introspection data."""
    return [m['mac']
            for m in data.get('all_interfaces', {}).values()
            if m.get('mac')]


def get_inventory(data, node_info=None):
    """Get and validate the hardware inventory from introspection data."""
    inventory = data.get('inventory')
    # TODO(dtantsur): validate inventory using JSON schema
    if not inventory:
        raise Error(_('Hardware inventory is empty or missing'),
                    data=data, node_info=node_info)

    if not inventory.get('interfaces'):
        raise Error(_('No network interfaces provided in the inventory'),
                    data=data, node_info=node_info)

    if not inventory.get('disks'):
        LOG.info('No disks were detected in the inventory, assuming this '
                 'is a disk-less node', data=data, node_info=node_info)
        # Make sure the code iterating over it does not fail with a TypeError
        inventory['disks'] = []

    return inventory


def iso_timestamp(timestamp=None, tz=pytz.timezone('utc')):
    """Return an ISO8601-formatted timestamp (tz: UTC) or None.

    :param timestamp: such as time.time() or None
    :param tz: timezone
    :returns: an ISO8601-formatted timestamp, or None
    """
    if timestamp is None:
        return None
    date = datetime.datetime.fromtimestamp(timestamp, tz=tz)
    return date.isoformat()


_COORDINATOR = None


def get_coordinator():
    global _COORDINATOR
    if _COORDINATOR is None:
        _COORDINATOR = coordination.get_coordinator(
            CONF.coordination.backend_url, str.encode(CONF.host))
    return _COORDINATOR

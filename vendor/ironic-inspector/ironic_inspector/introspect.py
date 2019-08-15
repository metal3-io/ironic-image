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

"""Handling introspection request."""

import time

from eventlet import semaphore
from oslo_config import cfg

from ironic_inspector.common.i18n import _
from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import introspection_state as istate
from ironic_inspector import node_cache
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector import utils

CONF = cfg.CONF


LOG = utils.getProcessingLogger(__name__)

_LAST_INTROSPECTION_TIME = 0
_LAST_INTROSPECTION_LOCK = semaphore.BoundedSemaphore()


def introspect(node_id, manage_boot=True, token=None):
    """Initiate hardware properties introspection for a given node.

    :param node_id: node UUID or name
    :param manage_boot: whether to manage boot for this node
    :param token: authentication token
    :raises: Error
    """
    ironic = ir_utils.get_client(token)
    node = ir_utils.get_node(node_id, ironic=ironic)

    ir_utils.check_provision_state(node)
    if manage_boot:
        validation = ironic.node.validate(node.uuid)
        if not validation.power['result']:
            msg = _('Failed validation of power interface, reason: %s')
            raise utils.Error(msg % validation.power['reason'],
                              node_info=node)

    bmc_address, bmc_ipv4, bmc_ipv6 = ir_utils.get_ipmi_address(node)
    lookup_attrs = list(filter(None, [bmc_ipv4, bmc_ipv6]))
    node_info = node_cache.start_introspection(node.uuid,
                                               bmc_address=lookup_attrs,
                                               manage_boot=manage_boot,
                                               ironic=ironic)

    utils.executor().submit(_background_introspect, node_info, ironic)


@node_cache.release_lock
@node_cache.fsm_transition(istate.Events.wait)
def _background_introspect(node_info, ironic):
    global _LAST_INTROSPECTION_TIME

    LOG.debug('Attempting to acquire lock on last introspection time')
    with _LAST_INTROSPECTION_LOCK:
        delay = (_LAST_INTROSPECTION_TIME - time.time()
                 + CONF.introspection_delay)
        if delay > 0:
            LOG.debug('Waiting %d seconds before sending the next '
                      'node on introspection', delay)
            time.sleep(delay)
        _LAST_INTROSPECTION_TIME = time.time()

    node_info.acquire_lock()
    _background_introspect_locked(node_info, ironic)


def _background_introspect_locked(node_info, ironic):
    # TODO(dtantsur): pagination
    macs = list(node_info.ports())
    if macs:
        node_info.add_attribute(node_cache.MACS_ATTRIBUTE, macs)
        LOG.info('Whitelisting MAC\'s %s for a PXE boot', macs,
                 node_info=node_info)
        pxe_filter.driver().sync(ironic)

    attrs = node_info.attributes
    if CONF.processing.node_not_found_hook is None and not attrs:
        raise utils.Error(
            _('No lookup attributes were found, inspector won\'t '
              'be able to find it after introspection, consider creating '
              'ironic ports or providing an IPMI address'),
            node_info=node_info)

    LOG.info('The following attributes will be used for look up: %s',
             attrs, node_info=node_info)

    if node_info.manage_boot:
        try:
            ironic.node.set_boot_device(node_info.uuid, 'pxe',
                                        persistent=False)
        except Exception as exc:
            raise utils.Error(_('Failed to set boot device to PXE: %s') % exc,
                              node_info=node_info)

        try:
            ironic.node.set_power_state(node_info.uuid, 'reboot')
        except Exception as exc:
            raise utils.Error(_('Failed to power on the node, check it\'s '
                                'power management configuration: %s') % exc,
                              node_info=node_info)
        LOG.info('Introspection started successfully',
                 node_info=node_info)
    else:
        LOG.info('Introspection environment is ready, external power on '
                 'is required within %d seconds', CONF.timeout,
                 node_info=node_info)


def abort(node_id, token=None):
    """Abort running introspection.

    :param node_id: node UUID or name
    :param token: authentication token
    :raises: Error
    """
    LOG.debug('Aborting introspection for node %s', node_id)
    ironic = ir_utils.get_client(token)
    node_info = node_cache.get_node(node_id, ironic=ironic)

    # check pending operations
    locked = node_info.acquire_lock(blocking=False)
    if not locked:
        # Node busy --- cannot abort atm
        raise utils.Error(_('Node is locked, please, retry later'),
                          node_info=node_info, code=409)

    utils.executor().submit(_abort, node_info, ironic)


@node_cache.release_lock
@node_cache.fsm_event_before(istate.Events.abort)
def _abort(node_info, ironic):
    # runs in background

    LOG.debug('Forcing power-off', node_info=node_info)
    if node_info.manage_boot:
        try:
            ironic.node.set_power_state(node_info.uuid, 'off')
        except Exception as exc:
            LOG.warning('Failed to power off node: %s', exc,
                        node_info=node_info)

    node_info.finished(istate.Events.abort_end,
                       error=_('Canceled by operator'))

    # block this node from PXE Booting the introspection image
    try:
        pxe_filter.driver().sync(ironic)
    except Exception as exc:
        # Note(mkovacik): this will be retried in the PXE filter sync
        # periodic task; we continue aborting
        LOG.warning('Failed to sync the PXE filter: %s', exc,
                    node_info=node_info)
    LOG.info('Introspection aborted', node_info=node_info)

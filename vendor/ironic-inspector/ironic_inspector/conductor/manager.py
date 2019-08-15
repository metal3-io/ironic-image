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

import sys
import traceback as traceback_mod

import eventlet
from eventlet import semaphore
from futurist import periodics
from ironic_lib import mdns
from oslo_config import cfg
from oslo_log import log
import oslo_messaging as messaging
from oslo_utils import excutils
from oslo_utils import reflection

from ironic_inspector.common.i18n import _
from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import keystone
from ironic_inspector import db
from ironic_inspector import introspect
from ironic_inspector import node_cache
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector import process
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector import utils

LOG = log.getLogger(__name__)
CONF = cfg.CONF
MANAGER_TOPIC = 'ironic-inspector-conductor'


class ConductorManager(object):
    """ironic inspector conductor manager"""
    RPC_API_VERSION = '1.2'

    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self):
        self._periodics_worker = None
        self._zeroconf = None
        self._shutting_down = semaphore.Semaphore()

    def init_host(self):
        """Initialize Worker host

        Init db connection, load and validate processing
        hooks, runs periodic tasks.

        :returns None
        """
        if CONF.processing.store_data == 'none':
            LOG.warning('Introspection data will not be stored. Change '
                        '"[processing] store_data" option if this is not '
                        'the desired behavior')
        else:
            LOG.info('Introspection data will be stored in the %s backend',
                     CONF.processing.store_data)

        db.init()

        try:
            hooks = plugins_base.validate_processing_hooks()
        except Exception as exc:
            LOG.critical(str(exc))
            sys.exit(1)
        LOG.info('Enabled processing hooks: %s', [h.name for h in hooks])

        driver = pxe_filter.driver()
        driver.init_filter()

        periodic_clean_up_ = periodics.periodic(
            spacing=CONF.clean_up_period
        )(periodic_clean_up)

        self._periodics_worker = periodics.PeriodicWorker(
            callables=[(driver.get_periodic_sync_task(), None, None),
                       (periodic_clean_up_, None, None)],
            executor_factory=periodics.ExistingExecutor(utils.executor()),
            on_failure=self._periodics_watchdog)
        utils.executor().submit(self._periodics_worker.start)

        if CONF.enable_mdns:
            endpoint = keystone.get_endpoint('service_catalog')
            self._zeroconf = mdns.Zeroconf()
            self._zeroconf.register_service('baremetal-introspection',
                                            endpoint)

        if not CONF.standalone:
            try:
                coordinator = utils.get_coordinator()
                coordinator.start()
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.critical('Failed when connecting to coordination '
                                 'backend.')
                    self.del_host()
            else:
                LOG.info('Successfully connected to coordination backend.')

    def del_host(self):

        if not self._shutting_down.acquire(blocking=False):
            LOG.warning('Attempted to shut down while already shutting down')
            return

        pxe_filter.driver().tear_down_filter()
        if self._periodics_worker is not None:
            try:
                self._periodics_worker.stop()
                self._periodics_worker.wait()
            except Exception as e:
                LOG.exception('Service error occurred when stopping '
                              'periodic workers. Error: %s', e)
            self._periodics_worker = None

        if utils.executor().alive:
            utils.executor().shutdown(wait=True)

        if self._zeroconf is not None:
            self._zeroconf.close()
            self._zeroconf = None

        self._shutting_down.release()

        if not CONF.standalone:
            try:
                coordinator = utils.get_coordinator()
                if coordinator and coordinator.is_started:
                    coordinator.stop()
            except Exception:
                LOG.exception('Failed to stop coordinator')

        LOG.info('Shut down successfully')

    def _periodics_watchdog(self, callable_, activity, spacing, exc_info,
                            traceback=None):
        LOG.exception("The periodic %(callable)s failed with: %(exception)s", {
            'exception': ''.join(traceback_mod.format_exception(*exc_info)),
            'callable': reflection.get_callable_name(callable_)})
        # NOTE(milan): spawn new thread otherwise waiting would block
        eventlet.spawn(self.del_host)

    @messaging.expected_exceptions(utils.Error)
    def do_introspection(self, context, node_id, token=None,
                         manage_boot=True):
        introspect.introspect(node_id, token=token, manage_boot=manage_boot)

    @messaging.expected_exceptions(utils.Error)
    def do_abort(self, context, node_id, token=None):
        introspect.abort(node_id, token=token)

    @messaging.expected_exceptions(utils.Error)
    def do_reapply(self, context, node_uuid, token=None, data=None):
        if not data:
            try:
                data = process.get_introspection_data(node_uuid,
                                                      processed=False,
                                                      get_json=True)
            except utils.IntrospectionDataStoreDisabled:
                raise utils.Error(_('Inspector is not configured to store '
                                    'introspection data. Set the '
                                    '[processing]store_data configuration '
                                    'option to change this.'))
        else:
            process.store_introspection_data(node_uuid, data, processed=False)

        process.reapply(node_uuid, data=data)


def periodic_clean_up():  # pragma: no cover
    try:
        if node_cache.clean_up():
            pxe_filter.driver().sync(ir_utils.get_client())
    except Exception:
        LOG.exception('Periodic clean up of node cache failed')

    try:
        sync_with_ironic()
    except Exception:
        LOG.exception('Periodic sync of node list with ironic failed')


def sync_with_ironic():
    ironic = ir_utils.get_client()
    # TODO(yuikotakada): pagination
    ironic_nodes = ironic.node.list(limit=0)
    ironic_node_uuids = {node.uuid for node in ironic_nodes}
    node_cache.delete_nodes_not_in_list(ironic_node_uuids)

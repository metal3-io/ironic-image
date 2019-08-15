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

"""Standard set of plugins."""

from ironic_lib import utils as il_utils
import netaddr
from oslo_config import cfg
from oslo_utils import netutils
from oslo_utils import units
import six

from ironic_inspector.common.i18n import _
from ironic_inspector.plugins import base
from ironic_inspector import utils

CONF = cfg.CONF

LOG = utils.getProcessingLogger('ironic_inspector.plugins.standard')


class RootDiskSelectionHook(base.ProcessingHook):
    """Smarter root disk selection using Ironic root device hints.

    This hook must always go before SchedulerHook, otherwise root_disk field
    might not be updated.
    """

    def _process_root_device_hints(self, introspection_data, node_info,
                                   inventory):
        """Detect root disk from root device hints and IPA inventory."""
        hints = node_info.node().properties.get('root_device')
        if not hints:
            LOG.debug('Root device hints are not provided',
                      node_info=node_info, data=introspection_data)
            return

        try:
            device = il_utils.match_root_device_hints(inventory['disks'],
                                                      hints)
        except (TypeError, ValueError) as e:
            raise utils.Error(
                _('No disks could be found using the root device hints '
                  '%(hints)s because they failed to validate. '
                  'Error: %(error)s') % {'hints': hints, 'error': e},
                node_info=node_info, data=introspection_data)

        if not device:
            raise utils.Error(_('No disks satisfied root device hints'),
                              node_info=node_info, data=introspection_data)

        LOG.debug('Disk %(disk)s of size %(size)s satisfies '
                  'root device hints',
                  {'disk': device.get('name'), 'size': device['size']},
                  node_info=node_info, data=introspection_data)
        introspection_data['root_disk'] = device

    def before_update(self, introspection_data, node_info, **kwargs):
        """Process root disk information."""
        inventory = utils.get_inventory(introspection_data,
                                        node_info=node_info)
        self._process_root_device_hints(introspection_data, node_info,
                                        inventory)

        root_disk = introspection_data.get('root_disk')
        if root_disk:
            local_gb = root_disk['size'] // units.Gi
            if CONF.processing.disk_partitioning_spacing:
                local_gb -= 1
            LOG.info('Root disk %(disk)s, local_gb %(local_gb)s GiB',
                     {'disk': root_disk, 'local_gb': local_gb},
                     node_info=node_info, data=introspection_data)
        else:
            local_gb = 0
            LOG.info('No root device found, assuming a diskless node',
                     node_info=node_info, data=introspection_data)

        introspection_data['local_gb'] = local_gb
        if (CONF.processing.overwrite_existing or not
                node_info.node().properties.get('local_gb')):
            node_info.update_properties(local_gb=str(local_gb))


class SchedulerHook(base.ProcessingHook):
    """Nova scheduler required properties."""

    KEYS = ('cpus', 'cpu_arch', 'memory_mb')

    def before_update(self, introspection_data, node_info, **kwargs):
        """Update node with scheduler properties."""
        inventory = utils.get_inventory(introspection_data,
                                        node_info=node_info)
        try:
            introspection_data['cpus'] = int(inventory['cpu']['count'])
            introspection_data['cpu_arch'] = six.text_type(
                inventory['cpu']['architecture'])
        except (KeyError, ValueError, TypeError):
            LOG.warning('malformed or missing CPU information: %s',
                        inventory.get('cpu'))

        try:
            introspection_data['memory_mb'] = int(
                inventory['memory']['physical_mb'])
        except (KeyError, ValueError, TypeError):
            LOG.warning('malformed or missing memory information: %s; '
                        'introspection requires physical memory size '
                        'from dmidecode', inventory.get('memory'))

        LOG.info('Discovered data: CPUs: count %(cpus)s, architecture '
                 '%(cpu_arch)s, memory %(memory_mb)s MiB',
                 {key: introspection_data.get(key) for key in self.KEYS},
                 node_info=node_info, data=introspection_data)

        overwrite = CONF.processing.overwrite_existing
        properties = {key: str(introspection_data[key])
                      for key in self.KEYS if introspection_data.get(key) and
                      (overwrite or not node_info.node().properties.get(key))}
        if properties:
            node_info.update_properties(**properties)


class ValidateInterfacesHook(base.ProcessingHook):
    """Hook to validate network interfaces."""

    def __init__(self):
        # Some configuration checks
        if (CONF.processing.add_ports == 'disabled' and
                CONF.processing.keep_ports == 'added'):
            msg = _("Configuration error: add_ports set to disabled "
                    "and keep_ports set to added. Please change keep_ports "
                    "to all.")
            raise utils.Error(msg)

    def _get_interfaces(self, data=None):
        """Convert inventory to a dict with interfaces.

        :return: dict interface name -> dict with keys 'mac' and 'ip'
        """
        result = {}
        inventory = utils.get_inventory(data)

        pxe_mac = utils.get_pxe_mac(data)

        for iface in inventory['interfaces']:
            name = iface.get('name')
            mac = iface.get('mac_address')
            ipv4_address = iface.get('ipv4_address')
            ipv6_address = iface.get('ipv6_address')
            # NOTE(kaifeng) ipv6 address may in the form of fd00::1%enp2s0,
            # which is not supported by netaddr, remove the suffix if exists.
            if ipv6_address and '%' in ipv6_address:
                ipv6_address = ipv6_address.split('%')[0]
            ip = ipv4_address or ipv6_address
            client_id = iface.get('client_id')

            if not name:
                LOG.error('Malformed interface record: %s',
                          iface, data=data)
                continue

            if not mac:
                LOG.debug('Skipping interface %s without link information',
                          name, data=data)
                continue

            if not netutils.is_valid_mac(mac):
                LOG.warning('MAC %(mac)s for interface %(name)s is '
                            'not valid, skipping',
                            {'mac': mac, 'name': name},
                            data=data)
                continue

            mac = mac.lower()

            LOG.debug('Found interface %(name)s with MAC "%(mac)s", '
                      'IP address "%(ip)s" and client_id "%(client_id)s"',
                      {'name': name, 'mac': mac, 'ip': ip,
                       'client_id': client_id}, data=data)
            result[name] = {'ip': ip, 'mac': mac, 'client_id': client_id,
                            'pxe': (mac == pxe_mac)}

        return result

    def _validate_interfaces(self, interfaces, data=None):
        """Validate interfaces on correctness and suitability.

        :return: dict interface name -> dict with keys 'mac' and 'ip'
        """
        if not interfaces:
            raise utils.Error(_('No interfaces supplied by the ramdisk'),
                              data=data)

        pxe_mac = utils.get_pxe_mac(data)
        if not pxe_mac and CONF.processing.add_ports == 'pxe':
            LOG.warning('No boot interface provided in the introspection '
                        'data, will add all ports with IP addresses')

        result = {}

        for name, iface in interfaces.items():
            ip = iface.get('ip')
            pxe = iface.get('pxe', True)

            if name == 'lo' or (ip and netaddr.IPAddress(ip).is_loopback()):
                LOG.debug('Skipping local interface %s', name, data=data)
                continue

            if CONF.processing.add_ports == 'pxe' and pxe_mac and not pxe:
                LOG.debug('Skipping interface %s as it was not PXE booting',
                          name, data=data)
                continue
            elif CONF.processing.add_ports != 'all' and (
                        not ip or netaddr.IPAddress(ip).is_link_local()):
                LOG.debug('Skipping interface %s as it did not have '
                          'an IP address assigned during the ramdisk run',
                          name, data=data)
                continue

            result[name] = iface

        if not result:
            raise utils.Error(_('No suitable interfaces found in %s') %
                              interfaces, data=data)
        return result

    def before_processing(self, introspection_data, **kwargs):
        """Validate information about network interfaces."""

        bmc_address = utils.get_ipmi_address_from_data(introspection_data)
        bmc_v6address = utils.get_ipmi_v6address_from_data(introspection_data)
        # Overwrite the old ipmi_address field to avoid inconsistency
        introspection_data['ipmi_address'] = bmc_address
        introspection_data['ipmi_v6address'] = bmc_v6address
        if not (bmc_address or bmc_v6address):
            LOG.debug('No BMC address provided in introspection data, '
                      'assuming virtual environment', data=introspection_data)

        all_interfaces = self._get_interfaces(introspection_data)

        interfaces = self._validate_interfaces(all_interfaces,
                                               introspection_data)

        LOG.info('Using network interface(s): %s',
                 ', '.join('%s %s' % (name, items)
                           for (name, items) in interfaces.items()),
                 data=introspection_data)

        introspection_data['all_interfaces'] = all_interfaces
        introspection_data['interfaces'] = interfaces
        valid_macs = [iface['mac'] for iface in interfaces.values()]
        introspection_data['macs'] = valid_macs

    def before_update(self, introspection_data, node_info, **kwargs):
        """Create new ports and drop ports that are not present in the data."""
        interfaces = introspection_data.get('interfaces')
        if CONF.processing.add_ports != 'disabled':
            node_info.create_ports(list(interfaces.values()))

        if CONF.processing.keep_ports == 'present':
            expected_macs = {
                iface['mac']
                for iface in introspection_data['all_interfaces'].values()
            }
        elif CONF.processing.keep_ports == 'added':
            expected_macs = set(introspection_data['macs'])

        if CONF.processing.keep_ports != 'all':
            # list is required as we modify underlying dict
            for port in list(node_info.ports().values()):
                if port.address not in expected_macs:
                    LOG.info("Deleting port %(port)s as its MAC %(mac)s is "
                             "not in expected MAC list %(expected)s",
                             {'port': port.uuid,
                              'mac': port.address,
                              'expected': list(sorted(expected_macs))},
                             node_info=node_info, data=introspection_data)
                    node_info.delete_port(port)

        if CONF.processing.overwrite_existing:
            # Make sure pxe_enabled is up-to-date
            ports = node_info.ports()
            for iface in introspection_data['interfaces'].values():
                try:
                    port = ports[iface['mac']]
                except KeyError:
                    continue

                real_pxe = iface.get('pxe', True)
                if port.pxe_enabled != real_pxe:
                    LOG.info('Fixing pxe_enabled=%(val)s on port %(port)s '
                             'to match introspected data',
                             {'port': port.address, 'val': real_pxe},
                             node_info=node_info, data=introspection_data)
                    node_info.patch_port(port, [{'op': 'replace',
                                                 'path': '/pxe_enabled',
                                                 'value': real_pxe}])


class RamdiskErrorHook(base.ProcessingHook):
    """Hook to process error send from the ramdisk."""

    def before_processing(self, introspection_data, **kwargs):
        error = introspection_data.get('error')
        if error:
            raise utils.Error(_('Ramdisk reported error: %s') % error,
                              data=introspection_data)

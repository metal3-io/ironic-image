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

from oslo_config import cfg

from ironic_inspector.common.i18n import _


VALID_ADD_PORTS_VALUES = ('all', 'active', 'pxe', 'disabled')
VALID_KEEP_PORTS_VALUES = ('all', 'present', 'added')


_OPTS = [
    cfg.StrOpt('add_ports',
               default='pxe',
               help=_('Which MAC addresses to add as ports during '
                      'introspection. Possible values: all '
                      '(all MAC addresses), active (MAC addresses of NIC with '
                      'IP addresses), pxe (only MAC address of NIC node PXE '
                      'booted from, falls back to "active" if PXE MAC is not '
                      'supplied by the ramdisk).'),
               choices=VALID_ADD_PORTS_VALUES),
    cfg.StrOpt('keep_ports',
               default='all',
               help=_('Which ports (already present on a node) to keep after '
                      'introspection. Possible values: all (do not delete '
                      'anything), present (keep ports which MACs were present '
                      'in introspection data), added (keep only MACs that we '
                      'added during introspection).'),
               choices=VALID_KEEP_PORTS_VALUES),
    cfg.BoolOpt('overwrite_existing',
                default=True,
                help=_('Whether to overwrite existing values in node '
                       'database. Disable this option to make '
                       'introspection a non-destructive operation.')),
    cfg.StrOpt('default_processing_hooks',
               default='ramdisk_error,root_disk_selection,scheduler,'
                       'validate_interfaces,capabilities,pci_devices',
               help=_('Comma-separated list of default hooks for processing '
                      'pipeline. Hook \'scheduler\' updates the node with the '
                      'minimum properties required by the Nova scheduler. '
                      'Hook \'validate_interfaces\' ensures that valid NIC '
                      'data was provided by the ramdisk. '
                      'Do not exclude these two unless you really know what '
                      'you\'re doing.')),
    cfg.StrOpt('processing_hooks',
               default='$default_processing_hooks',
               help=_('Comma-separated list of enabled hooks for processing '
                      'pipeline. The default for this is '
                      '$default_processing_hooks, hooks can be added before '
                      'or after the defaults like this: '
                      '"prehook,$default_processing_hooks,posthook".')),
    cfg.StrOpt('ramdisk_logs_dir',
               help=_('If set, logs from ramdisk will be stored in this '
                      'directory.')),
    cfg.BoolOpt('always_store_ramdisk_logs',
                default=False,
                help=_('Whether to store ramdisk logs even if it did not '
                       'return an error message (dependent upon '
                       '"ramdisk_logs_dir" option being set).')),
    cfg.StrOpt('node_not_found_hook',
               help=_('The name of the hook to run when inspector receives '
                      'inspection information from a node it isn\'t already '
                      'aware of. This hook is ignored by default.')),
    cfg.StrOpt('store_data',
               default='none',
               help=_('The storage backend for storing introspection data. '
                      'Possible values are: \'none\', \'database\' and '
                      '\'swift\'. If set to \'none\', introspection data will '
                      'not be stored.')),
    cfg.BoolOpt('disk_partitioning_spacing',
                default=True,
                help=_('Whether to leave 1 GiB of disk size untouched for '
                       'partitioning. Only has effect when used with the IPA '
                       'as a ramdisk, for older ramdisk local_gb is '
                       'calculated on the ramdisk side.')),
    cfg.StrOpt('ramdisk_logs_filename_format',
               default='{uuid}_{dt:%Y%m%d-%H%M%S.%f}.tar.gz',
               help=_('File name template for storing ramdisk logs. The '
                      'following replacements can be used: '
                      '{uuid} - node UUID or "unknown", '
                      '{bmc} - node BMC address or "unknown", '
                      '{dt} - current UTC date and time, '
                      '{mac} - PXE booting MAC or "unknown".')),
    cfg.BoolOpt('power_off',
                default=True,
                help=_('Whether to power off a node after introspection.'
                       'Nodes in active or rescue states which submit '
                       'introspection data will be left on if the feature '
                       'is enabled via the \'permit_active_introspection\' '
                       'configuration option.')),
    cfg.BoolOpt('permit_active_introspection',
                default=False,
                help=_('Whether to process nodes that are in running '
                       'states.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'processing')


def list_opts():
    return _OPTS

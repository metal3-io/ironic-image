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
from oslo_log import log
from oslo_middleware import cors

import ironic_inspector.conf
from ironic_inspector import version


MIN_VERSION_HEADER = 'X-OpenStack-Ironic-Inspector-API-Minimum-Version'
MAX_VERSION_HEADER = 'X-OpenStack-Ironic-Inspector-API-Maximum-Version'
VERSION_HEADER = 'X-OpenStack-Ironic-Inspector-API-Version'


def set_config_defaults():
    """Return a list of oslo.config options available in Inspector code."""
    log.set_defaults(default_log_levels=['sqlalchemy=WARNING',
                                         'iso8601=WARNING',
                                         'requests=WARNING',
                                         'urllib3.connectionpool=WARNING',
                                         'keystonemiddleware=WARNING',
                                         'keystoneauth=WARNING',
                                         'ironicclient=WARNING'])
    set_cors_middleware_defaults()


def set_cors_middleware_defaults():
    """Update default configuration options for oslo.middleware."""
    cors.set_defaults(
        allow_headers=['X-Auth-Token',
                       MIN_VERSION_HEADER,
                       MAX_VERSION_HEADER,
                       VERSION_HEADER],
        allow_methods=['GET', 'POST', 'PUT', 'HEAD',
                       'PATCH', 'DELETE', 'OPTIONS']
    )


def parse_args(args, default_config_files=None):
    cfg.CONF(args,
             project='ironic-inspector',
             version=version.version_info.release_string(),
             default_config_files=default_config_files)


def list_opts():
    return [
        ('capabilities', ironic_inspector.conf.capabilities.list_opts()),
        ('coordination', ironic_inspector.conf.coordination.list_opts()),
        ('DEFAULT', ironic_inspector.conf.default.list_opts()),
        ('discovery', ironic_inspector.conf.discovery.list_opts()),
        ('dnsmasq_pxe_filter',
         ironic_inspector.conf.dnsmasq_pxe_filter.list_opts()),
        ('swift', ironic_inspector.conf.swift.list_opts()),
        ('ironic', ironic_inspector.conf.ironic.list_opts()),
        ('iptables', ironic_inspector.conf.iptables.list_opts()),
        ('processing', ironic_inspector.conf.processing.list_opts()),
        ('pci_devices', ironic_inspector.conf.pci_devices.list_opts()),
        ('pxe_filter', ironic_inspector.conf.pxe_filter.list_opts()),
        ('service_catalog', ironic_inspector.conf.service_catalog.list_opts()),
    ]

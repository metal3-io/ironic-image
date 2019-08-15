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

import copy

from keystoneauth1 import loading
from oslo_config import cfg


CONF = cfg.CONF
DEFAULT_VALID_INTERFACES = ['internal', 'public']


# TODO(pas-ha) set default values in conf.opts.set_defaults()
def register_auth_opts(group, service_type):
    loading.register_session_conf_options(CONF, group)
    loading.register_auth_conf_options(CONF, group)
    CONF.set_default('auth_type', default='password', group=group)
    loading.register_adapter_conf_options(CONF, group)
    CONF.set_default('valid_interfaces', DEFAULT_VALID_INTERFACES,
                     group=group)
    CONF.set_default('service_type', service_type, group=group)


def get_session(group):
    auth = loading.load_auth_from_conf_options(CONF, group)
    session = loading.load_session_from_conf_options(
        CONF, group, auth=auth)
    return session


def get_adapter(group, **adapter_kwargs):
    return loading.load_adapter_from_conf_options(CONF, group,
                                                  **adapter_kwargs)


# TODO(pas-ha) set default values in conf.opts.set_defaults()
def add_auth_options(options, service_type):
    def add_options(opts, opts_to_add):
        for new_opt in opts_to_add:
            for opt in opts:
                if opt.name == new_opt.name:
                    break
            else:
                opts.append(new_opt)

    opts = copy.deepcopy(options)
    opts.insert(0, loading.get_auth_common_conf_options()[0])
    # NOTE(dims): There are a lot of auth plugins, we just generate
    # the config options for a few common ones
    plugins = ['password', 'v2password', 'v3password']
    for name in plugins:
        plugin = loading.get_plugin_loader(name)
        add_options(opts, loading.get_auth_plugin_conf_options(plugin))
    add_options(opts, loading.get_session_conf_options())
    adapter_opts = loading.get_adapter_conf_options(
        include_deprecated=False)
    cfg.set_defaults(adapter_opts, service_type=service_type,
                     valid_interfaces=DEFAULT_VALID_INTERFACES)
    add_options(opts, adapter_opts)
    opts.sort(key=lambda x: x.name)
    return opts


def get_endpoint(group, **kwargs):
    return get_adapter(group, session=get_session(group)).get_endpoint(
        **kwargs)

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy

from keystoneauth1 import loading
from oslo_config import cfg

from keystonemiddleware.auth_token import _base


# NOTE(jamielennox): A number of options below are deprecated however are left
# in the list and only mentioned as deprecated in the help string. This is
# because we have to provide the same deprecation functionality for arguments
# passed in via the conf in __init__ (from paste) and there is no way to test
# that the default value was set or not in CONF.
# Also if we were to remove the options from the CONF list (as typical CONF
# deprecation works) then other projects will not be able to override the
# options via CONF.

_OPTS = [
    cfg.StrOpt('www_authenticate_uri',
               # FIXME(dolph): should be default='http://127.0.0.1:5000/v2.0/',
               # or (depending on client support) an unversioned, publicly
               # accessible identity endpoint (see bug 1207517). Further, we
               # can eliminate this configuration option in favor of pulling
               # the endpoint from the service catalog that the service user
               # receives (there should be an identity endpoint listed there).
               # This wasn't an option originally when many auth_token
               # deployments were configured with the "ADMIN" token and
               # endpoint combination.
               deprecated_name='auth_uri',
               help='Complete "public" Identity API endpoint. This endpoint'
               ' should not be an "admin" endpoint, as it should be accessible'
               ' by all end users. Unauthenticated clients are redirected to'
               ' this endpoint to authenticate. Although this endpoint should'
               ' ideally be unversioned, client support in the wild varies.'
               ' If you\'re using a versioned v2 endpoint here, then this'
               ' should *not* be the same endpoint the service user utilizes'
               ' for validating tokens, because normal end users may not be'
               ' able to reach that endpoint.'),
    cfg.StrOpt('auth_uri',
               deprecated_for_removal=True,
               deprecated_reason='The auth_uri option is deprecated in favor'
               ' of www_authenticate_uri and will be removed in the S '
               ' release.',
               deprecated_since='Queens',
               help='Complete "public" Identity API endpoint. This endpoint'
               ' should not be an "admin" endpoint, as it should be accessible'
               ' by all end users. Unauthenticated clients are redirected to'
               ' this endpoint to authenticate. Although this endpoint should'
               ' ideally be unversioned, client support in the wild varies.'
               ' If you\'re using a versioned v2 endpoint here, then this'
               ' should *not* be the same endpoint the service user utilizes'
               ' for validating tokens, because normal end users may not be'
               ' able to reach that endpoint. This option is deprecated in'
               ' favor of www_authenticate_uri and will be removed in the S'
               ' release.'),
    cfg.StrOpt('auth_version',
               help='API version of the Identity API endpoint.'),
    cfg.StrOpt('interface',
               default='admin',
               help='Interface to use for the Identity API endpoint. Valid'
               ' values are "public", "internal" or "admin"(default).'),
    cfg.BoolOpt('delay_auth_decision',
                default=False,
                help='Do not handle authorization requests within the'
                ' middleware, but delegate the authorization decision to'
                ' downstream WSGI components.'),
    cfg.IntOpt('http_connect_timeout',
               help='Request timeout value for communicating with Identity'
               ' API server.'),
    cfg.IntOpt('http_request_max_retries',
               default=3,
               help='How many times are we trying to reconnect when'
               ' communicating with Identity API Server.'),
    cfg.StrOpt('cache',
               help='Request environment key where the Swift cache object is'
               ' stored. When auth_token middleware is deployed with a Swift'
               ' cache, use this option to have the middleware share a caching'
               ' backend with swift. Otherwise, use the ``memcached_servers``'
               ' option instead.'),
    cfg.StrOpt('certfile',
               help='Required if identity server requires client certificate'),
    cfg.StrOpt('keyfile',
               help='Required if identity server requires client certificate'),
    cfg.StrOpt('cafile',
               help='A PEM encoded Certificate Authority to use when '
                    'verifying HTTPs connections. Defaults to system CAs.'),
    cfg.BoolOpt('insecure', default=False, help='Verify HTTPS connections.'),
    cfg.StrOpt('region_name',
               help='The region in which the identity server can be found.'),
    cfg.ListOpt('memcached_servers',
                deprecated_name='memcache_servers',
                help='Optionally specify a list of memcached server(s) to'
                ' use for caching. If left undefined, tokens will instead be'
                ' cached in-process.'),
    cfg.IntOpt('token_cache_time',
               default=300,
               help='In order to prevent excessive effort spent validating'
               ' tokens, the middleware caches previously-seen tokens for a'
               ' configurable duration (in seconds). Set to -1 to disable'
               ' caching completely.'),
    cfg.StrOpt('memcache_security_strategy',
               default='None',
               choices=('None', 'MAC', 'ENCRYPT'),
               ignore_case=True,
               help='(Optional) If defined, indicate whether token data'
               ' should be authenticated or authenticated and encrypted.'
               ' If MAC, token data is authenticated (with HMAC) in the cache.'
               ' If ENCRYPT, token data is encrypted and authenticated in the'
               ' cache. If the value is not one of these options or empty,'
               ' auth_token will raise an exception on initialization.'),
    cfg.StrOpt('memcache_secret_key',
               secret=True,
               help='(Optional, mandatory if memcache_security_strategy is'
               ' defined) This string is used for key derivation.'),
    cfg.IntOpt('memcache_pool_dead_retry',
               default=5 * 60,
               help='(Optional) Number of seconds memcached server is'
               ' considered dead before it is tried again.'),
    cfg.IntOpt('memcache_pool_maxsize',
               default=10,
               help='(Optional) Maximum total number of open connections to'
               ' every memcached server.'),
    cfg.IntOpt('memcache_pool_socket_timeout',
               default=3,
               help='(Optional) Socket timeout in seconds for communicating '
                    'with a memcached server.'),
    cfg.IntOpt('memcache_pool_unused_timeout',
               default=60,
               help='(Optional) Number of seconds a connection to memcached'
               ' is held unused in the pool before it is closed.'),
    cfg.IntOpt('memcache_pool_conn_get_timeout',
               default=10,
               help='(Optional) Number of seconds that an operation will wait '
                    'to get a memcached client connection from the pool.'),
    cfg.BoolOpt('memcache_use_advanced_pool',
                default=False,
                help='(Optional) Use the advanced (eventlet safe) memcached '
                     'client pool. The advanced pool will only work under '
                     'python 2.x.'),
    cfg.BoolOpt('include_service_catalog',
                default=True,
                help='(Optional) Indicate whether to set the X-Service-Catalog'
                ' header. If False, middleware will not ask for service'
                ' catalog on token validation and will not set the'
                ' X-Service-Catalog header.'),
    cfg.StrOpt('enforce_token_bind',
               default='permissive',
               help='Used to control the use and type of token binding. Can'
               ' be set to: "disabled" to not check token binding.'
               ' "permissive" (default) to validate binding information if the'
               ' bind type is of a form known to the server and ignore it if'
               ' not. "strict" like "permissive" but if the bind type is'
               ' unknown the token will be rejected. "required" any form of'
               ' token binding is needed to be allowed. Finally the name of a'
               ' binding method that must be present in tokens.'),
    cfg.ListOpt('service_token_roles', default=['service'],
                help='A choice of roles that must be present in a service'
                ' token. Service tokens are allowed to request that an expired'
                ' token can be used and so this check should tightly control'
                ' that only actual services should be sending this token.'
                ' Roles here are applied as an ANY check so any role in this'
                ' list must be present. For backwards compatibility reasons'
                ' this currently only affects the allow_expired check.'),
    cfg.BoolOpt('service_token_roles_required', default=False,
                help='For backwards compatibility reasons we must let valid'
                ' service tokens pass that don\'t pass the service_token_roles'
                ' check as valid. Setting this true will become the default'
                ' in a future release and should be enabled if possible.'),
    cfg.StrOpt('service_type',
               help='The name or type of the service as it appears in the'
               ' service catalog. This is used to validate tokens that have'
               ' restricted access rules.'),
]


CONF = cfg.CONF
CONF.register_opts(_OPTS, group=_base.AUTHTOKEN_GROUP)
loading.register_auth_conf_options(cfg.CONF, _base.AUTHTOKEN_GROUP)


auth_token_opts = [
    (_base.AUTHTOKEN_GROUP, _OPTS + loading.get_auth_common_conf_options()),
]

__all__ = (
    'list_opts',
)


def list_opts():
    """Return a list of oslo_config options available in auth_token middleware.

    The returned list includes the non-deprecated oslo_config options which may
    be registered at runtime by the project. The purpose of this is to allow
    tools like the Oslo sample config file generator to discover the options
    exposed to users by this middleware.

    Deprecated Options should not show up here so as to not be included in
    sample configuration.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is discoverable via the entry point
    'keystonemiddleware.auth_token' under the 'oslo.config.opts' namespace.

    :returns: a list of (group_name, opts) tuples
    """
    auth_token_opts = (_OPTS + loading.get_auth_common_conf_options())

    return [(_base.AUTHTOKEN_GROUP, copy.deepcopy(auth_token_opts))]

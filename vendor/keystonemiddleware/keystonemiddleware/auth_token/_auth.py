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

from keystoneauth1 import discover
from keystoneauth1.identity import v2
from keystoneauth1 import plugin
from keystoneauth1 import token_endpoint
from oslo_config import cfg

from keystonemiddleware.auth_token import _base
from keystonemiddleware.i18n import _


class AuthTokenPlugin(plugin.BaseAuthPlugin):

    def __init__(self, auth_host, auth_port, auth_protocol, auth_admin_prefix,
                 admin_user, admin_password, admin_tenant_name, admin_token,
                 identity_uri, log):

        log.warning(
            "Use of the auth_admin_prefix, auth_host, auth_port, "
            "auth_protocol, identity_uri, admin_token, admin_user, "
            "admin_password, and admin_tenant_name configuration options was "
            "deprecated in the Mitaka release in favor of an auth_plugin and "
            "its related options. This class may be removed in a future "
            "release.")

        # NOTE(jamielennox): it does appear here that our default arguments
        # are backwards. We need to do it this way so that we can handle the
        # same deprecation strategy for CONF and the conf variable.
        if not identity_uri:
            log.warning('Configuring admin URI using auth fragments was '
                        'deprecated in the Kilo release, and will be '
                        'removed in the Newton release, '
                        "use 'identity_uri' instead.")

            if ':' in auth_host:
                # Note(dzyu) it is an IPv6 address, so it needs to be wrapped
                # with '[]' to generate a valid IPv6 URL, based on
                # http://www.ietf.org/rfc/rfc2732.txt
                auth_host = '[%s]' % auth_host

            identity_uri = '%s://%s:%s' % (auth_protocol,
                                           auth_host,
                                           auth_port)

            if auth_admin_prefix:
                identity_uri = '%s/%s' % (identity_uri,
                                          auth_admin_prefix.strip('/'))

        self._identity_uri = identity_uri.rstrip('/')

        # FIXME(jamielennox): Yes. This is wrong. We should be determining the
        # plugin to use based on a combination of discovery and inputs. Much
        # of this can be changed when we get keystoneclient 0.10. For now this
        # hardcoded path is EXACTLY the same as the original auth_token did.
        auth_url = '%s/v2.0' % self._identity_uri

        if admin_token:
            log.warning(
                "The admin_token option in auth_token middleware was "
                "deprecated in the Kilo release, and will be removed in the "
                "Newton release, use admin_user and admin_password instead.")
            self._plugin = token_endpoint.Token(auth_url, admin_token)
        else:
            self._plugin = v2.Password(auth_url,
                                       username=admin_user,
                                       password=admin_password,
                                       tenant_name=admin_tenant_name)

        self._LOG = log
        self._discover = None

    def get_token(self, *args, **kwargs):
        return self._plugin.get_token(*args, **kwargs)

    def get_endpoint(self, session, interface=None, version=None, **kwargs):
        """Return an endpoint for the client.

        There are no required keyword arguments to ``get_endpoint`` as a plugin
        implementation should use best effort with the information available to
        determine the endpoint.

        :param session: The session object that the auth_plugin belongs to.
        :type session: keystoneauth1.session.Session
        :param version: The version number required for this endpoint.
        :type version: tuple or str
        :param str interface: what visibility the endpoint should have.

        :returns: The base URL that will be used to talk to the required
                  service or None if not available.
        :rtype: string
        """
        if interface == plugin.AUTH_INTERFACE:
            return self._identity_uri

        if not version:
            # NOTE(jamielennox): This plugin can only be used within auth_token
            # and auth_token will always provide version= with requests.
            return None

        if not self._discover:
            self._discover = discover.Discover(session,
                                               url=self._identity_uri,
                                               authenticated=False)

        if not self._discover.url_for(version):
            # NOTE(jamielennox): The requested version is not supported by the
            # identity server.
            return None

        # NOTE(jamielennox): for backwards compatibility here we don't
        # actually use the URL from discovery we hack it up instead. :(
        # NOTE(blk-u): Normalizing the version is a workaround for bug 1450272.
        # This can be removed once that's fixed. Also fix the docstring for the
        # version parameter to be just "tuple".
        version = discover.normalize_version_number(version)
        if discover.version_match((2, 0), version):
            return '%s/v2.0' % self._identity_uri
        elif discover.version_match((3, 0), version):
            return '%s/v3' % self._identity_uri

        # NOTE(jamielennox): This plugin will only get called from auth_token
        # middleware. The middleware should never request a version that the
        # plugin doesn't know how to handle.
        msg = _('Invalid version asked for in auth_token plugin')
        raise NotImplementedError(msg)

    def invalidate(self):
        return self._plugin.invalidate()


OPTS = [
    cfg.StrOpt('auth_admin_prefix',
               default='',
               help='Prefix to prepend at the beginning of the path. '
                    'Deprecated, use identity_uri.'),
    cfg.StrOpt('auth_host',
               default='127.0.0.1',
               help='Host providing the admin Identity API endpoint. '
                    'Deprecated, use identity_uri.'),
    cfg.IntOpt('auth_port',
               default=35357,
               help='Port of the admin Identity API endpoint. '
                    'Deprecated, use identity_uri.'),
    cfg.StrOpt('auth_protocol',
               default='https',
               choices=('http', 'https'),
               help='Protocol of the admin Identity API endpoint. '
                    'Deprecated, use identity_uri.'),
    cfg.StrOpt('identity_uri',
               help='Complete admin Identity API endpoint. This '
                    'should specify the unversioned root endpoint '
                    'e.g. https://localhost:35357/'),
    cfg.StrOpt('admin_token',
               secret=True,
               help='This option is deprecated and may be removed in '
                    'a future release. Single shared secret with the '
                    'Keystone configuration used for bootstrapping a '
                    'Keystone installation, or otherwise bypassing '
                    'the normal authentication process. This option '
                    'should not be used, use `admin_user` and '
                    '`admin_password` instead.'),
    cfg.StrOpt('admin_user',
               help='Service username.'),
    cfg.StrOpt('admin_password',
               secret=True,
               help='Service user password.'),
    cfg.StrOpt('admin_tenant_name',
               default='admin',
               help='Service tenant name.'),
]


cfg.CONF.register_opts(OPTS, group=_base.AUTHTOKEN_GROUP)

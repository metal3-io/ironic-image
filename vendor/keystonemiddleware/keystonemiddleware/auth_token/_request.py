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

import itertools

from oslo_serialization import jsonutils
import webob


def _v3_to_v2_catalog(catalog):
    """Convert a catalog to v2 format.

    X_SERVICE_CATALOG must be specified in v2 format. If you get a token
    that is in v3 convert it.
    """
    v2_services = []
    for v3_service in catalog:
        # first copy over the entries we allow for the service
        v2_service = {'type': v3_service['type']}
        try:
            v2_service['name'] = v3_service['name']
        except KeyError:  # nosec
            # v3 service doesn't have a name, so v2_service doesn't either.
            pass

        # now convert the endpoints. Because in v3 we specify region per
        # URL not per group we have to collect all the entries of the same
        # region together before adding it to the new service.
        regions = {}
        for v3_endpoint in v3_service.get('endpoints', []):
            region_name = v3_endpoint.get('region')
            try:
                region = regions[region_name]
            except KeyError:
                region = {'region': region_name} if region_name else {}
                regions[region_name] = region

            interface_name = v3_endpoint['interface'].lower() + 'URL'
            region[interface_name] = v3_endpoint['url']

        v2_service['endpoints'] = list(regions.values())
        v2_services.append(v2_service)

    return v2_services


def _is_admin_project(auth_ref):
    """Return an appropriate header value for X-Is-Admin-Project.

    Headers must be strings so we can't simply pass a boolean value through so
    return a True or False string to signal the admin project.
    """
    return 'True' if auth_ref.is_admin_project else 'False'


def _get_system_scope(auth_ref):
    """Return the scope information of a system scoped token."""
    if auth_ref.system_scoped:
        if auth_ref.system.get('all'):
            return 'all'


# NOTE(jamielennox): this should probably be moved into its own file, but at
# the moment there's no real logic here so just keep it locally.
class _AuthTokenResponse(webob.Response):

    default_content_type = None  # prevents webob assigning a content type


class _AuthTokenRequest(webob.Request):

    ResponseClass = _AuthTokenResponse

    _HEADER_TEMPLATE = {
        'X%s-Domain-Id': 'domain_id',
        'X%s-Domain-Name': 'domain_name',
        'X%s-Project-Id': 'project_id',
        'X%s-Project-Name': 'project_name',
        'X%s-Project-Domain-Id': 'project_domain_id',
        'X%s-Project-Domain-Name': 'project_domain_name',
        'X%s-User-Id': 'user_id',
        'X%s-User-Name': 'username',
        'X%s-User-Domain-Id': 'user_domain_id',
        'X%s-User-Domain-Name': 'user_domain_name',
    }

    _ROLES_TEMPLATE = 'X%s-Roles'

    _USER_HEADER_PREFIX = ''
    _SERVICE_HEADER_PREFIX = '-Service'

    _USER_STATUS_HEADER = 'X-Identity-Status'
    _SERVICE_STATUS_HEADER = 'X-Service-Identity-Status'

    _ADMIN_PROJECT_HEADER = 'X-Is-Admin-Project'
    _SYSTEM_SCOPE_HEADER = 'OpenStack-System-Scope'

    _SERVICE_CATALOG_HEADER = 'X-Service-Catalog'
    _TOKEN_AUTH = 'keystone.token_auth'  # nosec
    _TOKEN_INFO = 'keystone.token_info'  # nosec

    _CONFIRMED = 'Confirmed'
    _INVALID = 'Invalid'

    # header names that have been deprecated in favour of something else.
    _DEPRECATED_HEADER_MAP = {
        'X-Role': 'X-Roles',
        'X-User': 'X-User-Name',
        'X-Tenant-Id': 'X-Project-Id',
        'X-Tenant-Name': 'X-Project-Name',
        'X-Tenant': 'X-Project-Name',
    }

    def _confirmed(cls, value):
        return cls._CONFIRMED if value else cls._INVALID

    @property
    def user_token_valid(self):
        """User token is marked as valid.

        :returns: True if the X-Identity-Status header is set to Confirmed.
        :rtype: bool
        """
        return self.headers[self._USER_STATUS_HEADER] == self._CONFIRMED

    @user_token_valid.setter
    def user_token_valid(self, value):
        self.headers[self._USER_STATUS_HEADER] = self._confirmed(value)

    @property
    def user_token(self):
        return self.headers.get('X-Auth-Token',
                                self.headers.get('X-Storage-Token'))

    @property
    def service_token_valid(self):
        """Service token is marked as valid.

        :returns: True if the X-Service-Identity-Status header
                  is set to Confirmed.
        :rtype: bool
        """
        return self.headers[self._SERVICE_STATUS_HEADER] == self._CONFIRMED

    @service_token_valid.setter
    def service_token_valid(self, value):
        self.headers[self._SERVICE_STATUS_HEADER] = self._confirmed(value)

    @property
    def service_token(self):
        return self.headers.get('X-Service-Token')

    def _set_auth_headers(self, auth_ref, prefix):
        names = ','.join(auth_ref.role_names)
        self.headers[self._ROLES_TEMPLATE % prefix] = names
        self.headers[self._SYSTEM_SCOPE_HEADER] = _get_system_scope(auth_ref)

        for header_tmplt, attr in self._HEADER_TEMPLATE.items():
            self.headers[header_tmplt % prefix] = getattr(auth_ref, attr)

    def set_user_headers(self, auth_ref):
        """Convert token object into headers.

        Build headers that represent authenticated user - see main
        doc info at start of __init__ file for details of headers to be defined
        """
        self._set_auth_headers(auth_ref, self._USER_HEADER_PREFIX)
        self.headers[self._ADMIN_PROJECT_HEADER] = _is_admin_project(auth_ref)

        for k, v in self._DEPRECATED_HEADER_MAP.items():
            self.headers[k] = self.headers[v]

    def set_service_catalog_headers(self, auth_ref):
        """Convert service catalog from token object into headers.

        Build headers that represent the catalog - see main
        doc info at start of __init__ file for details of headers to be defined

        :param auth_ref: The token data
        :type auth_ref: keystoneauth.access.AccessInfo
        """
        if not auth_ref.has_service_catalog():
            self.headers.pop(self._SERVICE_CATALOG_HEADER, None)
            return

        catalog = auth_ref.service_catalog.catalog
        if auth_ref.version == 'v3':
            catalog = _v3_to_v2_catalog(catalog)

        c = jsonutils.dumps(catalog)
        self.headers[self._SERVICE_CATALOG_HEADER] = c

    def set_service_headers(self, auth_ref):
        """Convert token object into service headers.

        Build headers that represent authenticated user - see main
        doc info at start of __init__ file for details of headers to be defined
        """
        self._set_auth_headers(auth_ref, self._SERVICE_HEADER_PREFIX)

    def _all_auth_headers(self):
        """All the authentication headers that can be set on the request."""
        yield self._SERVICE_CATALOG_HEADER
        yield self._USER_STATUS_HEADER
        yield self._SERVICE_STATUS_HEADER
        yield self._ADMIN_PROJECT_HEADER

        for header in self._DEPRECATED_HEADER_MAP:
            yield header

        prefixes = (self._USER_HEADER_PREFIX, self._SERVICE_HEADER_PREFIX)

        for tmpl, prefix in itertools.product(self._HEADER_TEMPLATE, prefixes):
            yield tmpl % prefix

        for prefix in prefixes:
            yield self._ROLES_TEMPLATE % prefix

    def remove_auth_headers(self):
        """Remove headers so a user can't fake authentication."""
        for header in self._all_auth_headers():
            self.headers.pop(header, None)

    @property
    def auth_type(self):
        """The authentication type that was performed by the web server.

        The returned string value is always lower case.

        :returns: The AUTH_TYPE environ string or None if not present.
        :rtype: str or None
        """
        try:
            auth_type = self.environ['AUTH_TYPE']
        except KeyError:
            return None
        else:
            return auth_type.lower()

    @property
    def token_auth(self):
        """The auth plugin that will be associated with this request."""
        return self.environ.get(self._TOKEN_AUTH)

    @token_auth.setter
    def token_auth(self, v):
        self.environ[self._TOKEN_AUTH] = v

    @property
    def token_info(self):
        """The raw token dictionary retrieved by the middleware."""
        return self.environ.get(self._TOKEN_INFO)

    @token_info.setter
    def token_info(self, v):
        self.environ[self._TOKEN_INFO] = v

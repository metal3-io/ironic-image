# Copyright 2010-2012 OpenStack Foundation
#
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

r"""
Token-based Authentication Middleware.

This WSGI component:

* Verifies that incoming client requests have valid tokens by validating
  tokens with the auth service.
* Rejects unauthenticated requests unless the auth_token middleware is in
  ``delay_auth_decision`` mode, which means the final decision is delegated to
  the downstream WSGI component (usually the OpenStack service).
* Collects and forwards identity information based on a valid token
  such as user name, domain, project, etc.

Refer to: https://docs.openstack.org/keystonemiddleware/latest/\
middlewarearchitecture.html


Headers
-------

The auth_token middleware uses headers sent in by the client on the request
and sets headers and environment variables for the downstream WSGI component.

Coming in from initial call from client or customer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

HTTP_X_AUTH_TOKEN
    The client token being passed in.

HTTP_X_SERVICE_TOKEN
    A service token being passed in.

Used for communication between components
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

WWW-Authenticate
    HTTP header returned to a user indicating which endpoint to use
    to retrieve a new token.

What auth_token adds to the request for use by the OpenStack service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When using composite authentication (a user and service token are
present) additional service headers relating to the service user
will be added. They take the same form as the standard headers but add
``_SERVICE_``. These headers will not exist in the environment if no
service token is present.

HTTP_X_IDENTITY_STATUS, HTTP_X_SERVICE_IDENTITY_STATUS
    Will be set to either ``Confirmed`` or ``Invalid``.

    The underlying service will only see a value of 'Invalid' if the middleware
    is configured to run in ``delay_auth_decision`` mode. As with all such
    headers, ``HTTP_X_SERVICE_IDENTITY_STATUS`` will only exist in the
    environment if a service token is presented. This is different than
    ``HTTP_X_IDENTITY_STATUS`` which is always set even if no user token is
    presented. This allows the underlying service to determine if a
    denial should use ``401 Unauthenticated`` or ``403 Forbidden``.

HTTP_OPENSTACK_SYSTEM_SCOPE
    A string relaying system information about the token's scope. This
    attribute is only present if the token is system-scoped. The string ``all``
    means the token is scoped to the entire deployment system.

HTTP_X_DOMAIN_ID, HTTP_X_SERVICE_DOMAIN_ID
    Identity service managed unique identifier, string. Only present if
    this is a domain-scoped token.

HTTP_X_DOMAIN_NAME, HTTP_X_SERVICE_DOMAIN_NAME
    Unique domain name, string. Only present if this is a domain-scoped
    token.

HTTP_X_PROJECT_ID, HTTP_X_SERVICE_PROJECT_ID
    Identity service managed unique identifier, string. Only present if
    this is a project-scoped token.

HTTP_X_PROJECT_NAME, HTTP_X_SERVICE_PROJECT_NAME
    Project name, unique within owning domain, string. Only present if
    this is a project-scoped token.

HTTP_X_PROJECT_DOMAIN_ID, HTTP_X_SERVICE_PROJECT_DOMAIN_ID
    Identity service managed unique identifier of owning domain of
    project, string.  Only present if this is a project-scoped v3 token. If
    this variable is set, this indicates that the PROJECT_NAME can only
    be assumed to be unique within this domain.

HTTP_X_PROJECT_DOMAIN_NAME, HTTP_X_SERVICE_PROJECT_DOMAIN_NAME
    Name of owning domain of project, string. Only present if this is a
    project-scoped v3 token. If this variable is set, this indicates that
    the PROJECT_NAME can only be assumed to be unique within this domain.

HTTP_X_USER_ID, HTTP_X_SERVICE_USER_ID
    Identity-service managed unique identifier, string.

HTTP_X_USER_NAME, HTTP_X_SERVICE_USER_NAME
    User identifier, unique within owning domain, string.

HTTP_X_USER_DOMAIN_ID, HTTP_X_SERVICE_USER_DOMAIN_ID
    Identity service managed unique identifier of owning domain of
    user, string. If this variable is set, this indicates that the USER_NAME
    can only be assumed to be unique within this domain.

HTTP_X_USER_DOMAIN_NAME, HTTP_X_SERVICE_USER_DOMAIN_NAME
    Name of owning domain of user, string. If this variable is set, this
    indicates that the USER_NAME can only be assumed to be unique within
    this domain.

HTTP_X_ROLES, HTTP_X_SERVICE_ROLES
    Comma delimited list of case-sensitive role names.

HTTP_X_IS_ADMIN_PROJECT
    The string value 'True' or 'False' representing whether the user's token is
    scoped to the admin project. As historically there was no admin project
    this will default to True for tokens without this information to be
    backwards with existing policy files.

HTTP_X_SERVICE_CATALOG
    service catalog (optional, JSON string).

    For compatibility reasons this catalog will always be in the V2 catalog
    format even if it is a v3 token.

    .. note:: This is an exception in that it contains 'SERVICE' but relates to
        a user token, not a service token. The existing user's catalog can be
        very large; it was decided not to present a catalog relating to the
        service token to avoid using more HTTP header space.

HTTP_X_TENANT_ID
    *Deprecated* in favor of HTTP_X_PROJECT_ID.

    Identity service managed unique identifier, string. For v3 tokens, this
    will be set to the same value as HTTP_X_PROJECT_ID.

HTTP_X_TENANT_NAME
    *Deprecated* in favor of HTTP_X_PROJECT_NAME.

    Project identifier, unique within owning domain, string. For v3 tokens,
    this will be set to the same value as HTTP_X_PROJECT_NAME.

HTTP_X_TENANT
    *Deprecated* in favor of HTTP_X_TENANT_ID and HTTP_X_TENANT_NAME.

    Identity server-assigned unique identifier, string. For v3 tokens, this
    will be set to the same value as HTTP_X_PROJECT_ID.

HTTP_X_USER
    *Deprecated* in favor of HTTP_X_USER_ID and HTTP_X_USER_NAME.

    User name, unique within owning domain, string.

HTTP_X_ROLE
    *Deprecated* in favor of HTTP_X_ROLES.

    Will contain the same values as HTTP_X_ROLES.

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

These variables are set in the request environment for use by the downstream
WSGI component.

keystone.token_info
    Information about the token discovered in the process of validation.  This
    may include extended information returned by the token validation call, as
    well as basic information about the project and user.

keystone.token_auth
    A keystoneauth1 auth plugin that may be used with a
    :py:class:`keystoneauth1.session.Session`. This plugin will load the
    authentication data provided to auth_token middleware.


Configuration
-------------

auth_token middleware configuration can be in the main application's
configuration file, e.g. in ``nova.conf``:

.. code-block:: ini

  [keystone_authtoken]
  auth_plugin = password
  auth_url = http://keystone:5000/
  username = nova
  user_domain_id = default
  password = whyarewestillusingpasswords
  project_name = service
  project_domain_id = default

Configuration can also be in the ``api-paste.ini`` file with the same options,
but this is discouraged.

Swift
-----

When deploy auth_token middleware with Swift, user may elect to use Swift
memcache instead of the local auth_token memcache. Swift memcache is passed in
from the request environment and it's identified by the ``swift.cache`` key.
However it could be different, depending on deployment. To use Swift memcache,
you must set the ``cache`` option to the environment key where the Swift cache
object is stored.

"""

import copy
import re

from keystoneauth1 import access
from keystoneauth1 import adapter
from keystoneauth1 import discover
from keystoneauth1 import exceptions as ksa_exceptions
from keystoneauth1 import loading
from keystoneauth1.loading import session as session_loading
import oslo_cache
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
import webob.dec

from keystonemiddleware._common import config
from keystonemiddleware.auth_token import _auth
from keystonemiddleware.auth_token import _base
from keystonemiddleware.auth_token import _cache
from keystonemiddleware.auth_token import _exceptions as ksm_exceptions
from keystonemiddleware.auth_token import _identity
from keystonemiddleware.auth_token import _opts
from keystonemiddleware.auth_token import _request
from keystonemiddleware.auth_token import _user_plugin
from keystonemiddleware.i18n import _


_LOG = logging.getLogger(__name__)
_CACHE_INVALID_INDICATOR = 'invalid'
oslo_cache.configure(cfg.CONF)

AUTH_TOKEN_OPTS = [
    (_base.AUTHTOKEN_GROUP,
     _opts._OPTS + _auth.OPTS + loading.get_auth_common_conf_options())
]


def list_opts():
    """Return a list of oslo_config options available in auth_token middleware.

    The returned list includes all oslo_config options which may be registered
    at runtime by the project.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    NOTE: This function is no longer used for oslo_config sample generation.
    Some services rely on this function for listing ALL (including deprecated)
    options and registering them into their own config objects which we do not
    want for sample config files.

    See: :py:func:`keystonemiddleware.auth_token._opts.list_opts` for sample
    config files.

    :returns: a list of (group_name, opts) tuples
    """
    return [(g, copy.deepcopy(o)) for g, o in AUTH_TOKEN_OPTS]


def _path_matches(request_path, path_pattern):
    # The fnmatch module doesn't provide the ability to match * versus **,
    # so convert to regex.
    token_regex = (r'(?P<tag>{[^}]*})|'  # {tag} # nosec
                   '(?P<wild>\*(?=$|[^\*]))|'  # *
                   '(?P<rec_wild>\*\*)|'  # **
                   '(?P<literal>[^{}\*])')  # anything else
    path_regex = ''
    for match in re.finditer(token_regex, path_pattern):
        token = match.groupdict()
        if token['tag'] or token['wild']:
            path_regex += '[^\/]+'
        if token['rec_wild']:
            path_regex += '.*'
        if token['literal']:
            path_regex += token['literal']
    path_regex = r'^%s$' % path_regex
    return re.match(path_regex, request_path)


class _BIND_MODE(object):
    DISABLED = 'disabled'
    PERMISSIVE = 'permissive'
    STRICT = 'strict'
    REQUIRED = 'required'
    KERBEROS = 'kerberos'


class BaseAuthProtocol(object):
    """A base class for AuthProtocol token checking implementations.

    :param Callable app: The next application to call after middleware.
    :param logging.Logger log: The logging object to use for output. By default
                               it will use a logger in the
                               keystonemiddleware.auth_token namespace.
    :param str enforce_token_bind: The style of token binding enforcement to
                                   perform.
    """

    def __init__(self,
                 app,
                 log=_LOG,
                 enforce_token_bind=_BIND_MODE.PERMISSIVE,
                 service_token_roles=None,
                 service_token_roles_required=False,
                 service_type=None):
        self.log = log
        self._app = app
        self._enforce_token_bind = enforce_token_bind
        self._service_token_roles = set(service_token_roles or [])
        self._service_token_roles_required = service_token_roles_required
        self._service_token_warning_emitted = False
        self._service_type = service_type

    @webob.dec.wsgify(RequestClass=_request._AuthTokenRequest)
    def __call__(self, req):
        """Handle incoming request."""
        response = self.process_request(req)
        if response:
            return response
        response = req.get_response(self._app)
        return self.process_response(response)

    def process_request(self, request):
        """Process request.

        If this method returns a value then that value will be used as the
        response. The next application down the stack will not be executed and
        process_response will not be called.

        Otherwise, the next application down the stack will be executed and
        process_response will be called with the generated response.

        By default this method does not return a value.

        :param request: Incoming request
        :type request: _request.AuthTokenRequest

        """
        user_auth_ref = None
        serv_auth_ref = None
        allow_expired = False

        if request.service_token:
            self.log.debug('Authenticating service token')
            try:
                _, serv_auth_ref = self._do_fetch_token(request.service_token)
                self._validate_token(serv_auth_ref)
                self._confirm_token_bind(serv_auth_ref, request)
            except ksm_exceptions.InvalidToken:
                self.log.info('Invalid service token')
                request.service_token_valid = False
            else:
                # FIXME(jamielennox): The new behaviour for service tokens is
                # that they have to pass the policy check to be allowed.
                # Previously any token was accepted here. For now we will
                # continue to mark service tokens as valid if they are valid
                # but we will only allow service role tokens to do
                # allow_expired. In future we should reject any token that
                # isn't a service token here.
                role_names = set(serv_auth_ref.role_names)
                check = self._service_token_roles.intersection(role_names)
                role_check_passed = bool(check)

                # if service_token_roles_required then the service token is
                # only valid if the roles check out. Otherwise at this point it
                # is true because keystone has already validated it.
                if self._service_token_roles_required:
                    request.service_token_valid = role_check_passed
                else:
                    if not self._service_token_warning_emitted:
                        self.log.warning('A valid token was submitted as '
                                         'a service token, but it was not '
                                         'a valid service token. This is '
                                         'incorrect but backwards '
                                         'compatible behaviour. This will '
                                         'be removed in future releases.')
                        # prevent log spam on every single request
                        self._service_token_warning_emitted = True

                    request.service_token_valid = True

                # allow_expired always requires passing the role check.
                allow_expired = role_check_passed

        if request.user_token:
            self.log.debug('Authenticating user token')
            try:
                data, user_auth_ref = self._do_fetch_token(
                    request.user_token,
                    allow_expired=allow_expired)
                self._validate_token(user_auth_ref,
                                     allow_expired=allow_expired)
                if user_auth_ref.version != 'v2.0':
                    self.validate_allowed_request(request, data['token'])
                if not request.service_token:
                    self._confirm_token_bind(user_auth_ref, request)
            except ksm_exceptions.InvalidToken:
                self.log.info('Invalid user token')
                request.user_token_valid = False
            else:
                request.user_token_valid = True
                request.token_info = data

        request.token_auth = _user_plugin.UserAuthPlugin(user_auth_ref,
                                                         serv_auth_ref)

    def _validate_token(self, auth_ref, allow_expired=False):
        """Perform the validation steps on the token.

        :param auth_ref: The token data
        :type auth_ref: keystoneauth1.access.AccessInfo

        :raises exc.InvalidToken: if token is rejected
        """
        # 0 seconds of validity means it is invalid right now
        if (not allow_expired) and auth_ref.will_expire_soon(stale_duration=0):
            raise ksm_exceptions.InvalidToken(_('Token authorization failed'))

    def _do_fetch_token(self, token, **kwargs):
        """Helper method to fetch a token and convert it into an AccessInfo."""
        # NOTE(edmondsw): strip the token to remove any whitespace that may
        # have been passed along in the header per bug 1689468
        token = token.strip()
        data = self.fetch_token(token, **kwargs)

        try:
            return data, access.create(body=data, auth_token=token)
        except Exception:
            self.log.warning('Invalid token contents.', exc_info=True)
            raise ksm_exceptions.InvalidToken(_('Token authorization failed'))

    def fetch_token(self, token, **kwargs):
        """Fetch the token data based on the value in the header.

        Retrieve the data associated with the token value that was in the
        header. This can be from PKI, contacting the identity server or
        whatever is required.

        :param str token: The token present in the request header.
        :param dict kwargs: Additional keyword arguments may be passed through
                            here to support new features. If an implementation
                            is not aware of how to use these arguments it
                            should ignore them.

        :raises exc.InvalidToken: if token is invalid.

        :returns: The token data
        :rtype: dict
        """
        raise NotImplementedError()

    def process_response(self, response):
        """Do whatever you'd like to the response.

        By default the response is returned unmodified.

        :param response: Response object
        :type response: ._request._AuthTokenResponse
        """
        return response

    def _invalid_user_token(self, msg=False):
        # NOTE(jamielennox): use False as the default so that None is valid
        if msg is False:
            msg = _('Token authorization failed')

        raise ksm_exceptions.InvalidToken(msg)

    def _confirm_token_bind(self, auth_ref, req):
        if self._enforce_token_bind == _BIND_MODE.DISABLED:
            return

        # permissive and strict modes don't require there to be a bind
        permissive = self._enforce_token_bind in (_BIND_MODE.PERMISSIVE,
                                                  _BIND_MODE.STRICT)

        if not auth_ref.bind:
            if permissive:
                # no bind provided and none required
                return
            else:
                self.log.info('No bind information present in token.')
                self._invalid_user_token()

        # get the named mode if bind_mode is not one of the predefined
        if permissive or self._enforce_token_bind == _BIND_MODE.REQUIRED:
            name = None
        else:
            name = self._enforce_token_bind

        if name and name not in auth_ref.bind:
            self.log.info('Named bind mode %s not in bind information',
                          name)
            self._invalid_user_token()

        for bind_type, identifier in auth_ref.bind.items():
            if bind_type == _BIND_MODE.KERBEROS:
                if req.auth_type != 'negotiate':
                    self.log.info('Kerberos credentials required and '
                                  'not present.')
                    self._invalid_user_token()

                if req.remote_user != identifier:
                    self.log.info('Kerberos credentials do not match '
                                  'those in bind.')
                    self._invalid_user_token()

                self.log.debug('Kerberos bind authentication successful.')

            elif self._enforce_token_bind == _BIND_MODE.PERMISSIVE:
                self.log.debug('Ignoring Unknown bind for permissive mode: '
                               '%(bind_type)s: %(identifier)s.',
                               {'bind_type': bind_type,
                                'identifier': identifier})

            else:
                self.log.info(
                    'Couldn`t verify unknown bind: %(bind_type)s: '
                    '%(identifier)s.',
                    {'bind_type': bind_type, 'identifier': identifier})
                self._invalid_user_token()

    def validate_allowed_request(self, request, token):
        self.log.debug("Validating token access rules against request")
        app_cred = token.get('application_credential')
        if not app_cred:
            return
        access_rules = app_cred.get('access_rules')
        if access_rules is None:
            return
        if hasattr(self, '_conf'):
            my_service_type = self._conf.get('service_type')
        else:
            my_service_type = self._service_type
        if not my_service_type:
            self.log.warning('Cannot validate request with restricted'
                             ' access rules. Set service_type in'
                             ' [keystone_authtoken] to allow access rule'
                             ' validation.')
            raise ksm_exceptions.InvalidToken(_('Token authorization failed'))
        # token can always be validated regardless of access rules
        if (my_service_type == 'identity' and
                request.method == 'GET' and
                request.path.endswith('/v3/auth/tokens')):
            return
        catalog = token['catalog']
        # validate service type is in catalog
        catalog_svcs = [s for s in catalog if s['type'] == my_service_type]
        if len(catalog_svcs) == 0:
            self.log.warning('Cannot validate request with restricted'
                             ' access rules. service_type in'
                             ' [keystone_authtoken] is not a valid service'
                             ' type in the catalog.')
            raise ksm_exceptions.InvalidToken(_('Token authorization failed'))
        if request.service_token:
            # The request may not match an allowed request, but the presence
            # of the service token indicates this is a chain of requests and
            # hence this request was not user-facing
            return
        for access_rule in access_rules:
            method = access_rule['method']
            path = access_rule['path']
            service = access_rule['service']
            if request.method == method and \
                    service == my_service_type and \
                    _path_matches(request.path, path):
                return
        raise ksm_exceptions.InvalidToken(_('Token authorization failed'))


class AuthProtocol(BaseAuthProtocol):
    """Middleware that handles authenticating client calls."""

    def __init__(self, app, conf):
        log = logging.getLogger(conf.get('log_name', __name__))
        log.info('Starting Keystone auth_token middleware')

        self._conf = config.Config('auth_token',
                                   _base.AUTHTOKEN_GROUP,
                                   list_opts(),
                                   conf)
        if self._conf.oslo_conf_obj is not cfg.CONF:
            oslo_cache.configure(self._conf.oslo_conf_obj)

        token_roles_required = self._conf.get('service_token_roles_required')

        if not token_roles_required:
            log.warning('AuthToken middleware is set with '
                        'keystone_authtoken.service_token_roles_required '
                        'set to False. This is backwards compatible but '
                        'deprecated behaviour. Please set this to True.')

        super(AuthProtocol, self).__init__(
            app,
            log=log,
            enforce_token_bind=self._conf.get('enforce_token_bind'),
            service_token_roles=self._conf.get('service_token_roles'),
            service_token_roles_required=token_roles_required)

        # delay_auth_decision means we still allow unauthenticated requests
        # through and we let the downstream service make the final decision
        self._delay_auth_decision = self._conf.get('delay_auth_decision')
        self._include_service_catalog = self._conf.get(
            'include_service_catalog')
        self._interface = self._conf.get('interface')
        self._auth = self._create_auth_plugin()
        self._session = self._create_session()
        self._identity_server = self._create_identity_server()

        self._www_authenticate_uri = self._conf.get('www_authenticate_uri')
        if not self._www_authenticate_uri:
            self._www_authenticate_uri = self._conf.get('auth_uri')
        if not self._www_authenticate_uri:
            self.log.warning(
                'Configuring www_authenticate_uri to point to the public '
                'identity endpoint is required; clients may not be able to '
                'authenticate against an admin endpoint')

            # FIXME(dolph): drop support for this fallback behavior as
            # documented in bug 1207517.

            self._www_authenticate_uri = \
                self._identity_server.www_authenticate_uri

        self._token_cache = self._token_cache_factory()

    def process_request(self, request):
        """Process request.

        Evaluate the headers in a request and attempt to authenticate the
        request. If authenticated then additional headers are added to the
        request for use by applications. If not authenticated the request will
        be rejected or marked unauthenticated depending on configuration.
        """
        request.remove_auth_headers()
        self._token_cache.initialize(request.environ)

        resp = super(AuthProtocol, self).process_request(request)
        if resp:
            return resp

        if not request.user_token:
            # if no user token is present then that's an invalid request
            request.user_token_valid = False

        # NOTE(jamielennox): The service status is allowed to be missing if a
        # service token is not passed. If the service status is missing that's
        # a valid request. We should find a better way to expose this from the
        # request object.
        user_status = request.user_token and request.user_token_valid
        service_status = request.headers.get('X-Service-Identity-Status',
                                             'Confirmed')

        if not (user_status and service_status == 'Confirmed'):
            if self._delay_auth_decision:
                self.log.debug('Deferring reject downstream')
            else:
                self.log.info('Rejecting request')
                message = _('The request you have made requires '
                            'authentication.')
                body = {'error': {
                    'code': 401,
                    'title': 'Unauthorized',
                    'message': message,
                }}
                raise webob.exc.HTTPUnauthorized(
                    body=jsonutils.dumps(body),
                    headers=self._reject_auth_headers,
                    charset='UTF-8',
                    content_type='application/json')

        if request.user_token_valid:
            request.set_user_headers(request.token_auth.user)

            if self._include_service_catalog:
                request.set_service_catalog_headers(request.token_auth.user)

        if request.token_auth:
            request.token_auth._auth = self._auth
            request.token_auth._session = self._session

        if request.service_token and request.service_token_valid:
            request.set_service_headers(request.token_auth.service)

        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug('Received request from %s',
                           request.token_auth._log_format)

    def process_response(self, response):
        """Process Response.

        Add ``WWW-Authenticate`` headers to requests that failed with
        ``401 Unauthenticated`` so users know where to authenticate for future
        requests.
        """
        if response.status_int == 401:
            response.headers.extend(self._reject_auth_headers)

        return response

    @property
    def _reject_auth_headers(self):
        header_val = 'Keystone uri="%s"' % self._www_authenticate_uri
        return [('WWW-Authenticate', header_val)]

    def fetch_token(self, token, allow_expired=False):
        """Retrieve a token from either a PKI bundle or the identity server.

        :param str token: token id

        :raises exc.InvalidToken: if token is rejected
        """
        data = None
        try:
            cached = self._token_cache.get(token)

            if cached:
                if cached == _CACHE_INVALID_INDICATOR:
                    self.log.debug('Cached token is marked unauthorized')
                    raise ksm_exceptions.InvalidToken()

                # NOTE(jamielennox): Cached values used to be stored as a tuple
                # of data and expiry time. They no longer are but we have to
                # allow some time to transition the old format so if it's a
                # tuple just use the data.
                if len(cached) == 2:
                    cached = cached[0]

                data = cached
            else:
                data = self._identity_server.verify_token(
                    token,
                    allow_expired=allow_expired)

                self._token_cache.set(token, data)

        except (ksa_exceptions.ConnectFailure,
                ksa_exceptions.DiscoveryFailure,
                ksa_exceptions.RequestTimeout,
                ksm_exceptions.ServiceError) as e:
            self.log.critical('Unable to validate token: %s', e)
            if self._delay_auth_decision:
                self.log.debug('Keystone unavailable; marking token as '
                               'invalid and deferring auth decision.')
                raise ksm_exceptions.InvalidToken(
                    'Keystone unavailable: %s' % e)
            raise webob.exc.HTTPServiceUnavailable(
                'The Keystone service is temporarily unavailable.')
        except ksm_exceptions.InvalidToken:
            self.log.debug('Token validation failure.', exc_info=True)
            self._token_cache.set(token, _CACHE_INVALID_INDICATOR)
            self.log.warning('Authorization failed for token')
            raise
        except ksa_exceptions.EndpointNotFound:
            # Invalidate auth in adapter for identity endpoint update
            self._identity_server.invalidate()
            raise

        return data

    def _validate_token(self, auth_ref, **kwargs):
        super(AuthProtocol, self)._validate_token(auth_ref, **kwargs)

        if auth_ref.version == 'v2.0' and not auth_ref.project_id:
            msg = _('Unable to determine service tenancy.')
            raise ksm_exceptions.InvalidToken(msg)

    def _create_auth_plugin(self):
        # NOTE(jamielennox): Ideally this would use load_from_conf_options
        # however that is not possible because we have to support the override
        # pattern we use in _conf.get. This function therefore does a manual
        # version of load_from_conf_options with the fallback plugin inline.

        group = self._conf.get('auth_section') or _base.AUTHTOKEN_GROUP

        # NOTE(jamielennox): auth_plugin was deprecated to auth_type. _conf.get
        # doesn't handle that deprecation in the case of conf dict options so
        # we have to manually check the value
        plugin_name = (self._conf.get('auth_type', group=group)
                       or self._conf.paste_overrides.get('auth_plugin'))

        if not plugin_name:
            return _auth.AuthTokenPlugin(
                log=self.log,
                auth_admin_prefix=self._conf.get('auth_admin_prefix',
                                                 group=group),
                auth_host=self._conf.get('auth_host', group=group),
                auth_port=self._conf.get('auth_port', group=group),
                auth_protocol=self._conf.get('auth_protocol', group=group),
                identity_uri=self._conf.get('identity_uri', group=group),
                admin_token=self._conf.get('admin_token', group=group),
                admin_user=self._conf.get('admin_user', group=group),
                admin_password=self._conf.get('admin_password', group=group),
                admin_tenant_name=self._conf.get('admin_tenant_name',
                                                 group=group)
            )

        # Plugin option registration is normally done as part of the load_from
        # function rather than the register function so copy here.
        plugin_loader = loading.get_plugin_loader(plugin_name)
        plugin_opts = loading.get_auth_plugin_conf_options(plugin_loader)

        self._conf.oslo_conf_obj.register_opts(plugin_opts, group=group)
        getter = lambda opt: self._conf.get(opt.dest, group=group)
        return plugin_loader.load_from_options_getter(getter)

    def _create_session(self, **kwargs):
        # NOTE(jamielennox): Loading Session here should be exactly the
        # same as calling Session.load_from_conf_options(CONF, GROUP)
        # however we can't do that because we have to use _conf.get to
        # support the paste.ini options.
        kwargs.setdefault('cert', self._conf.get('certfile'))
        kwargs.setdefault('key', self._conf.get('keyfile'))
        kwargs.setdefault('cacert', self._conf.get('cafile'))
        kwargs.setdefault('insecure', self._conf.get('insecure'))
        kwargs.setdefault('timeout', self._conf.get('http_connect_timeout'))
        kwargs.setdefault('user_agent', self._conf.user_agent)

        return session_loading.Session().load_from_options(**kwargs)

    def _create_identity_server(self):
        adap = adapter.Adapter(
            self._session,
            auth=self._auth,
            service_type='identity',
            interface=self._interface,
            region_name=self._conf.get('region_name'),
            connect_retries=self._conf.get('http_request_max_retries'))

        auth_version = self._conf.get('auth_version')
        if auth_version is not None:
            auth_version = discover.normalize_version_number(auth_version)
        return _identity.IdentityServer(
            self.log,
            adap,
            include_service_catalog=self._include_service_catalog,
            requested_auth_version=auth_version,
            requested_auth_interface=self._interface)

    def _create_oslo_cache(self):
        # having this as a function makes test mocking easier
        region = oslo_cache.create_region()
        oslo_cache.configure_cache_region(self._conf.oslo_conf_obj, region)
        return region

    def _token_cache_factory(self):

        security_strategy = self._conf.get('memcache_security_strategy')

        cache_kwargs = dict(
            cache_time=int(self._conf.get('token_cache_time')),
            env_cache_name=self._conf.get('cache'),
            memcached_servers=self._conf.get('memcached_servers'),
            use_advanced_pool=self._conf.get('memcache_use_advanced_pool'),
            dead_retry=self._conf.get('memcache_pool_dead_retry'),
            maxsize=self._conf.get('memcache_pool_maxsize'),
            unused_timeout=self._conf.get('memcache_pool_unused_timeout'),
            conn_get_timeout=self._conf.get('memcache_pool_conn_get_timeout'),
            socket_timeout=self._conf.get('memcache_pool_socket_timeout'),
        )

        if security_strategy.lower() != 'none':
            secret_key = self._conf.get('memcache_secret_key')
            return _cache.SecureTokenCache(self.log,
                                           security_strategy,
                                           secret_key,
                                           **cache_kwargs)
        else:
            return _cache.TokenCache(self.log, **cache_kwargs)


def filter_factory(global_conf, **local_conf):
    """Return a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)

    def auth_filter(app):
        return AuthProtocol(app, conf)
    return auth_filter


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return AuthProtocol(None, conf)


# NOTE(jamielennox): Maintained here for public API compatibility.
InvalidToken = ksm_exceptions.InvalidToken
ServiceError = ksm_exceptions.ServiceError
ConfigurationError = ksm_exceptions.ConfigurationError

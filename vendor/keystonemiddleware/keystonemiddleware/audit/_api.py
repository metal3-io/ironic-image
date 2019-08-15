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

import collections
import re

from oslo_log import log as logging
from oslo_serialization import jsonutils
from pycadf import cadftaxonomy as taxonomy
from pycadf import cadftype
from pycadf import credential
from pycadf import endpoint
from pycadf import eventfactory as factory
from pycadf import host
from pycadf import identifier
from pycadf import resource
from pycadf import tag
import six
from six.moves import configparser
from six.moves.urllib import parse as urlparse

# NOTE(blk-u): Compatibility for Python 2. SafeConfigParser and
# SafeConfigParser.readfp are deprecated in Python 3. Remove this when we drop
# support for Python 2.
if six.PY2:
    class _ConfigParser(configparser.SafeConfigParser):
        read_file = configparser.SafeConfigParser.readfp
else:
    _ConfigParser = configparser.ConfigParser


Service = collections.namedtuple('Service',
                                 ['id', 'name', 'type', 'admin_endp',
                                  'public_endp', 'private_endp'])


AuditMap = collections.namedtuple('AuditMap',
                                  ['path_kw',
                                   'custom_actions',
                                   'service_endpoints',
                                   'default_target_endpoint_type'])


class PycadfAuditApiConfigError(Exception):
    """Error raised when pyCADF fails to configure correctly."""

    pass


class ClientResource(resource.Resource):
    def __init__(self, project_id=None, request_id=None,
                 global_request_id=None, **kwargs):
        super(ClientResource, self).__init__(**kwargs)
        if project_id is not None:
            self.project_id = project_id
        if request_id is not None:
            self.request_id = request_id
        if global_request_id is not None:
            self.global_request_id = global_request_id


class KeystoneCredential(credential.Credential):
    def __init__(self, identity_status=None, **kwargs):
        super(KeystoneCredential, self).__init__(**kwargs)
        if identity_status is not None:
            self.identity_status = identity_status


class OpenStackAuditApi(object):

    def __init__(self, cfg_file, log=logging.getLogger(__name__)):
        """Configure to recognize and map known api paths."""
        path_kw = {}
        custom_actions = {}
        endpoints = {}
        default_target_endpoint_type = None

        if cfg_file:
            try:
                map_conf = _ConfigParser()
                map_conf.read_file(open(cfg_file))

                try:
                    default_target_endpoint_type = map_conf.get(
                        'DEFAULT', 'target_endpoint_type')
                except configparser.NoOptionError:  # nosec
                    # Ignore the undefined config option,
                    # default_target_endpoint_type remains None which is valid.
                    pass

                try:
                    custom_actions = dict(map_conf.items('custom_actions'))
                except configparser.Error:  # nosec
                    # custom_actions remains {} which is valid.
                    pass

                try:
                    path_kw = dict(map_conf.items('path_keywords'))
                except configparser.Error:  # nosec
                    # path_kw remains {} which is valid.
                    pass

                try:
                    endpoints = dict(map_conf.items('service_endpoints'))
                except configparser.Error:  # nosec
                    # endpoints remains {} which is valid.
                    pass
            except configparser.ParsingError as err:
                raise PycadfAuditApiConfigError(
                    'Error parsing audit map file: %s' % err)

        self._log = log
        self._MAP = AuditMap(
            path_kw=path_kw, custom_actions=custom_actions,
            service_endpoints=endpoints,
            default_target_endpoint_type=default_target_endpoint_type)

    @staticmethod
    def _clean_path(value):
        """Clean path if path has json suffix."""
        return value[:-5] if value.endswith('.json') else value

    def get_action(self, req):
        """Take a given Request, parse url path to calculate action type.

        Depending on req.method:

        if POST:

        - path ends with 'action', read the body and use as action;
        - path ends with known custom_action, take action from config;
        - request ends with known path, assume is create action;
        - request ends with unknown path, assume is update action.

        if GET:

        - request ends with known path, assume is list action;
        - request ends with unknown path, assume is read action.

        if PUT, assume update action.
        if DELETE, assume delete action.
        if HEAD, assume read action.

        """
        path = req.path[:-1] if req.path.endswith('/') else req.path
        url_ending = self._clean_path(path[path.rfind('/') + 1:])
        method = req.method

        if url_ending + '/' + method.lower() in self._MAP.custom_actions:
            action = self._MAP.custom_actions[url_ending + '/' +
                                              method.lower()]
        elif url_ending in self._MAP.custom_actions:
            action = self._MAP.custom_actions[url_ending]
        elif method == 'POST':
            if url_ending == 'action':
                try:
                    if req.json:
                        body_action = list(req.json.keys())[0]
                        action = taxonomy.ACTION_UPDATE + '/' + body_action
                    else:
                        action = taxonomy.ACTION_CREATE
                except ValueError:
                    action = taxonomy.ACTION_CREATE
            elif url_ending not in self._MAP.path_kw:
                action = taxonomy.ACTION_UPDATE
            else:
                action = taxonomy.ACTION_CREATE
        elif method == 'GET':
            if url_ending in self._MAP.path_kw:
                action = taxonomy.ACTION_LIST
            else:
                action = taxonomy.ACTION_READ
        elif method == 'PUT' or method == 'PATCH':
            action = taxonomy.ACTION_UPDATE
        elif method == 'DELETE':
            action = taxonomy.ACTION_DELETE
        elif method == 'HEAD':
            action = taxonomy.ACTION_READ
        else:
            action = taxonomy.UNKNOWN

        return action

    def _get_service_info(self, endp):
        service = Service(
            type=self._MAP.service_endpoints.get(
                endp['type'],
                taxonomy.UNKNOWN),
            name=endp['name'],
            id=endp['endpoints'][0].get('id', endp['name']),
            admin_endp=endpoint.Endpoint(
                name='admin',
                url=endp['endpoints'][0].get('adminURL', taxonomy.UNKNOWN)),
            private_endp=endpoint.Endpoint(
                name='private',
                url=endp['endpoints'][0].get('internalURL', taxonomy.UNKNOWN)),
            public_endp=endpoint.Endpoint(
                name='public',
                url=endp['endpoints'][0].get('publicURL', taxonomy.UNKNOWN)))

        return service

    def _build_typeURI(self, req, service_type):
        """Build typeURI of target.

        Combines service type and corresponding path for greater detail.
        """
        type_uri = ''
        prev_key = None
        for key in re.split('/', req.path):
            key = self._clean_path(key)
            if key in self._MAP.path_kw:
                type_uri += '/' + key
            elif prev_key in self._MAP.path_kw:
                type_uri += '/' + self._MAP.path_kw[prev_key]
            prev_key = key
        return service_type + type_uri

    def _build_target(self, req, service):
        """Build target resource."""
        target_typeURI = (
            self._build_typeURI(req, service.type)
            if service.type != taxonomy.UNKNOWN else service.type)
        target = resource.Resource(typeURI=target_typeURI,
                                   id=service.id, name=service.name)
        if service.admin_endp:
            target.add_address(service.admin_endp)
        if service.private_endp:
            target.add_address(service.private_endp)
        if service.public_endp:
            target.add_address(service.public_endp)
        return target

    def get_target_resource(self, req):
        """Retrieve target information.

        If discovery is enabled, target will attempt to retrieve information
        from service catalog. If not, the information will be taken from
        given config file.
        """
        service_info = Service(type=taxonomy.UNKNOWN, name=taxonomy.UNKNOWN,
                               id=taxonomy.UNKNOWN, admin_endp=None,
                               private_endp=None, public_endp=None)

        catalog = {}
        try:
            catalog = jsonutils.loads(req.environ['HTTP_X_SERVICE_CATALOG'])
        except KeyError:
            self._log.warning(
                'Unable to discover target information because '
                'service catalog is missing. Either the incoming '
                'request does not contain an auth token or auth '
                'token does not contain a service catalog. For '
                'the latter, please make sure the '
                '"include_service_catalog" property in '
                'auth_token middleware is set to "True"')

        default_endpoint = None
        for endp in catalog:
            if not endp['endpoints']:
                self._log.warning(
                    'Skipping service %s as it have no endpoints.',
                    endp['name'])
                continue
            endpoint_urls = endp['endpoints'][0]
            admin_urlparse = urlparse.urlparse(
                endpoint_urls.get('adminURL', ''))
            public_urlparse = urlparse.urlparse(
                endpoint_urls.get('publicURL', ''))
            req_url = urlparse.urlparse(req.host_url)
            if req_url.port and (req_url.netloc == admin_urlparse.netloc
                                 or req_url.netloc == public_urlparse.netloc):
                service_info = self._get_service_info(endp)
                break
            elif (self._MAP.default_target_endpoint_type and
                  endp['type'] == self._MAP.default_target_endpoint_type):
                default_endpoint = endp
        else:
            if default_endpoint:
                service_info = self._get_service_info(default_endpoint)
        return self._build_target(req, service_info)

    def _create_event(self, req):
        correlation_id = identifier.generate_uuid()
        action = self.get_action(req)

        initiator = ClientResource(
            typeURI=taxonomy.ACCOUNT_USER,
            id=req.environ.get('HTTP_X_USER_ID', taxonomy.UNKNOWN),
            name=req.environ.get('HTTP_X_USER_NAME', taxonomy.UNKNOWN),
            host=host.Host(address=req.client_addr, agent=req.user_agent),
            credential=KeystoneCredential(
                token=req.environ.get('HTTP_X_AUTH_TOKEN', ''),
                identity_status=req.environ.get('HTTP_X_IDENTITY_STATUS',
                                                taxonomy.UNKNOWN)),
            project_id=req.environ.get('HTTP_X_PROJECT_ID', taxonomy.UNKNOWN),
            request_id=req.environ.get('openstack.request_id'),
            global_request_id=req.environ.get('openstack.global_request_id'))

        target = self.get_target_resource(req)

        event = factory.EventFactory().new_event(
            eventType=cadftype.EVENTTYPE_ACTIVITY,
            outcome=taxonomy.OUTCOME_PENDING,
            action=action,
            initiator=initiator,
            target=target,
            observer=resource.Resource(id='target'))
        event.requestPath = req.path_qs
        event.add_tag(tag.generate_name_value_tag('correlation_id',
                                                  correlation_id))
        return event

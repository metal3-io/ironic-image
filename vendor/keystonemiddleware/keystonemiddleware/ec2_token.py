# Copyright 2012 OpenStack Foundation
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
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

"""Starting point for routing EC2 requests."""

import hashlib

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
import requests
import six
import webob.dec

from keystonemiddleware.i18n import _


keystone_ec2_opts = [
    cfg.StrOpt('url',
               default='http://localhost:5000/v2.0/ec2tokens',
               help='URL to get token from ec2 request.'),
    cfg.StrOpt('keyfile',
               help='Required if EC2 server requires client certificate.'),
    cfg.StrOpt('certfile',
               help='Client certificate key filename. Required if EC2 server '
                    'requires client certificate.'),
    cfg.StrOpt('cafile',
               help='A PEM encoded certificate authority to use when '
                    'verifying HTTPS connections. Defaults to the system '
                    'CAs.'),
    cfg.BoolOpt('insecure', default=False,
                help='Disable SSL certificate verification.'),
]

CONF = cfg.CONF
CONF.register_opts(keystone_ec2_opts, group='keystone_ec2_token')


PROTOCOL_NAME = 'EC2 Token Authentication'


class EC2Token(object):
    """Authenticate an EC2 request with keystone and convert to token."""

    def __init__(self, application, conf):
        super(EC2Token, self).__init__()
        self._application = application
        self._logger = logging.getLogger(conf.get('log_name', __name__))
        self._logger.debug('Starting the %s component', PROTOCOL_NAME)

    def _ec2_error_response(self, code, message):
        """Helper to construct an EC2 compatible error message."""
        self._logger.debug('EC2 error response: %(code)s: %(message)s',
                           {'code': code, 'message': message})
        resp = webob.Response()
        resp.status = 400
        resp.headers['Content-Type'] = 'text/xml'
        error_msg = str('<?xml version="1.0"?>\n'
                        '<Response><Errors><Error><Code>%s</Code>'
                        '<Message>%s</Message></Error></Errors></Response>' %
                        (code, message))
        if six.PY3:
            error_msg = error_msg.encode()
        resp.body = error_msg
        return resp

    def _get_signature(self, req):
        """Extract the signature from the request.

        This can be a get/post variable or for version 4 also in a header
        called 'Authorization'.
        - params['Signature'] == version 0,1,2,3
        - params['X-Amz-Signature'] == version 4
        - header 'Authorization' == version 4
        """
        sig = req.params.get('Signature') or req.params.get('X-Amz-Signature')
        if sig is None and 'Authorization' in req.headers:
            auth_str = req.headers['Authorization']
            sig = auth_str.partition("Signature=")[2].split(',')[0]

        return sig

    def _get_access(self, req):
        """Extract the access key identifier.

        For version 0/1/2/3 this is passed as the AccessKeyId parameter, for
        version 4 it is either an X-Amz-Credential parameter or a Credential=
        field in the 'Authorization' header string.
        """
        access = req.params.get('AWSAccessKeyId')
        if access is None:
            cred_param = req.params.get('X-Amz-Credential')
            if cred_param:
                access = cred_param.split("/")[0]

        if access is None and 'Authorization' in req.headers:
            auth_str = req.headers['Authorization']
            cred_str = auth_str.partition("Credential=")[2].split(',')[0]
            access = cred_str.split("/")[0]

        return access

    @webob.dec.wsgify()
    def __call__(self, req):
        # NOTE(alevine): We need to calculate the hash here because
        # subsequent access to request modifies the req.body so the hash
        # calculation will yield invalid results.
        body_hash = hashlib.sha256(req.body).hexdigest()

        signature = self._get_signature(req)
        if not signature:
            msg = _("Signature not provided")
            return self._ec2_error_response("AuthFailure", msg)
        access = self._get_access(req)
        if not access:
            msg = _("Access key not provided")
            return self._ec2_error_response("AuthFailure", msg)

        if 'X-Amz-Signature' in req.params or 'Authorization' in req.headers:
            auth_params = {}
        else:
            # Make a copy of args for authentication and signature verification
            auth_params = dict(req.params)
            # Not part of authentication args
            auth_params.pop('Signature', None)

        headers = req.headers
        if six.PY3:
            # NOTE(andrey-mp): jsonutils dumps it as list of keys without
            # conversion instead real dict
            headers = {k: headers[k] for k in headers}
        cred_dict = {
            'access': access,
            'signature': signature,
            'host': req.host,
            'verb': req.method,
            'path': req.path,
            'params': auth_params,
            'headers': headers,
            'body_hash': body_hash
        }
        if "ec2" in CONF.keystone_ec2_token.url:
            creds = {'ec2Credentials': cred_dict}
        else:
            creds = {'auth': {'OS-KSEC2:ec2Credentials': cred_dict}}
        creds_json = jsonutils.dumps(creds)
        headers = {'Content-Type': 'application/json'}

        verify = not CONF.keystone_ec2_token.insecure
        if verify and CONF.keystone_ec2_token.cafile:
            verify = CONF.keystone_ec2_token.cafile

        cert = None
        if (CONF.keystone_ec2_token.certfile and
                CONF.keystone_ec2_token.keyfile):
            cert = (CONF.keystone_ec2_certfile,
                    CONF.keystone_ec2_token.keyfile)
        elif CONF.keystone_ec2_token.certfile:
            cert = CONF.keystone_ec2_token.certfile

        response = requests.request('POST', CONF.keystone_ec2_token.url,
                                    data=creds_json, headers=headers,
                                    verify=verify, cert=cert)

        # NOTE(vish): We could save a call to keystone by
        #             having keystone return token, tenant,
        #             user, and roles from this call.

        status_code = response.status_code
        if status_code != 200:
            msg = _('Error response from keystone: %s') % response.reason
            self._logger.debug(msg)
            return self._ec2_error_response("AuthFailure", msg)
        result = response.json()
        try:
            if 'token' in result:
                # NOTE(andrey-mp): response from keystone v3
                token_id = response.headers['x-subject-token']
            else:
                token_id = result['access']['token']['id']
        except (AttributeError, KeyError):
            msg = _("Failure parsing response from keystone")
            self._logger.exception(msg)
            return self._ec2_error_response("AuthFailure", msg)

        # Authenticated!
        req.headers['X-Auth-Token'] = token_id
        return self._application


def filter_factory(global_conf, **local_conf):
    """Return a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)

    def auth_filter(app):
        return EC2Token(app, conf)
    return auth_filter


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return EC2Token(None, conf)

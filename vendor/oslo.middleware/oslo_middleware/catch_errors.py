# Copyright (c) 2013 NEC Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import re

import webob.dec
import webob.exc

from oslo_middleware import base


LOG = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'^(X-\w+-Token):.*$', flags=re.MULTILINE)


class CatchErrors(base.ConfigurableMiddleware):
    """Middleware that provides high-level error handling.

    It catches all exceptions from subsequent applications in WSGI pipeline
    to hide internal errors from API response.
    """

    @webob.dec.wsgify
    def __call__(self, req):
        try:
            response = req.get_response(self.application)
        except Exception:
            req_str = _TOKEN_RE.sub(r'\1: *****', req.as_text())
            LOG.exception('An error occurred during '
                          'processing the request: %s', req_str)
            response = webob.exc.HTTPInternalServerError()
        return response

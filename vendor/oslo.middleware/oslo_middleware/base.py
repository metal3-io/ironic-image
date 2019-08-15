# Copyright 2011 OpenStack Foundation.
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

"""Base class(es) for WSGI Middleware."""

import six

from oslo_config import cfg
import webob.dec
import webob.request
import webob.response

if six.PY2:
    from inspect import getargspec as getfullargspec
else:
    from inspect import getfullargspec


class NoContentTypeResponse(webob.response.Response):

    default_content_type = None  # prevents webob assigning content type


class NoContentTypeRequest(webob.request.Request):

    ResponseClass = NoContentTypeResponse


class ConfigurableMiddleware(object):
    """Base WSGI middleware wrapper.

    These classes require an application to be initialized that will be called
    next.  By default the middleware will simply call its wrapped app, or you
    can override __call__ to customize its behavior.
    """

    @classmethod
    def factory(cls, global_conf, **local_conf):
        """Factory method for paste.deploy.

        :param global_conf: dict of options for all middlewares
                            (usually the [DEFAULT] section of the paste deploy
                            configuration file)
        :param local_conf: options dedicated to this middleware
                           (usually the option defined in the middleware
                           section of the paste deploy configuration file)
        """
        conf = global_conf.copy() if global_conf else {}
        conf.update(local_conf)

        def middleware_filter(app):
            return cls(app, conf)

        return middleware_filter

    def __init__(self, application, conf=None):
        """Base middleware constructor

        :param  conf: a dict of options or a cfg.ConfigOpts object
        """
        self.application = application

        # NOTE(sileht): If the configuration come from oslo.config
        # just use it.
        if isinstance(conf, cfg.ConfigOpts):
            self.conf = {}
            self.oslo_conf = conf
        else:
            self.conf = conf or {}
            if "oslo_config_project" in self.conf:
                if 'oslo_config_file' in self.conf:
                    default_config_files = [self.conf['oslo_config_file']]
                else:
                    default_config_files = None

                if 'oslo_config_program' in self.conf:
                    program = self.conf['oslo_config_program']
                else:
                    program = None

                self.oslo_conf = cfg.ConfigOpts()
                self.oslo_conf([],
                               project=self.conf['oslo_config_project'],
                               prog=program,
                               default_config_files=default_config_files,
                               validate_default_values=True)

            else:
                # Fallback to global object
                self.oslo_conf = cfg.CONF

    def _conf_get(self, key, group="oslo_middleware"):
        if key in self.conf:
            # Validate value type
            self.oslo_conf.set_override(key, self.conf[key], group=group)
        return getattr(getattr(self.oslo_conf, group), key)

    @staticmethod
    def process_request(req):
        """Called on each request.

        If this returns None, the next application down the stack will be
        executed. If it returns a response then that response will be returned
        and execution will stop here.
        """
        return None

    @staticmethod
    def process_response(response, request=None):
        """Do whatever you'd like to the response."""
        return response

    @webob.dec.wsgify(RequestClass=NoContentTypeRequest)
    def __call__(self, req):
        response = self.process_request(req)
        if response:
            return response
        response = req.get_response(self.application)

        args = getfullargspec(self.process_response)[0]
        if 'request' in args:
            return self.process_response(response, request=req)
        return self.process_response(response)


class Middleware(ConfigurableMiddleware):
    """Legacy base WSGI middleware wrapper.

    Legacy interface that doesn't pass configuration options
    to the middleware when it's loaded via paste.deploy.
    """

    @classmethod
    def factory(cls, global_conf, **local_conf):
        """Factory method for paste.deploy."""
        return cls

# Copyright 2014 IBM Corp.
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

import copy
import itertools

from oslo_middleware import cors
from oslo_middleware.healthcheck import opts as healthcheck_opts
from oslo_middleware import http_proxy_to_wsgi
from oslo_middleware import sizelimit
from oslo_middleware import ssl

__all__ = [
    'list_opts',
    'list_opts_sizelimit',
    'list_opts_ssl',
    'list_opts_cors',
    'list_opts_http_proxy_to_wsgi',
    'list_opts_healthcheck',
]


def list_opts():
    """Return a list of oslo.config options for ALL of the middleware classes.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return list(
        itertools.chain(
            list_opts_sizelimit(),
            list_opts_ssl(),
            list_opts_cors(),
            list_opts_http_proxy_to_wsgi(),
            list_opts_healthcheck(),
        )
    )


def list_opts_sizelimit():
    """Return a list of oslo.config options for the sizelimit middleware.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return [
        ('oslo_middleware', copy.deepcopy(sizelimit._opts)),
    ]


def list_opts_ssl():
    """Return a list of oslo.config options for the SSL middleware.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return [
        ('oslo_middleware', copy.deepcopy(ssl.OPTS)),
    ]


def list_opts_cors():
    """Return a list of oslo.config options for the cors middleware.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return [
        ('cors', copy.deepcopy(cors.CORS_OPTS)),
    ]


def list_opts_http_proxy_to_wsgi():
    """Return a list of oslo.config options for http_proxy_to_wsgi.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    return [
        ('oslo_middleware', copy.deepcopy(http_proxy_to_wsgi.OPTS)),
    ]


def list_opts_healthcheck():
    """Return a list of oslo.config options for healthcheck.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'oslo.middleware' entry point
    under the 'oslo.config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """
    # standard opts and the most common plugin to turn up in sample config.
    # can figure out a better way of exposing plugin opts later if required.
    return [
        ('healthcheck', copy.deepcopy(healthcheck_opts.HEALTHCHECK_OPTS +
                                      healthcheck_opts.DISABLE_BY_FILE_OPTS +
                                      healthcheck_opts.DISABLE_BY_FILES_OPTS))
    ]

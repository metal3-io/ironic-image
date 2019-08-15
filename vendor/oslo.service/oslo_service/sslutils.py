# Copyright 2013 IBM Corp.
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
import os
import ssl

from oslo_service._i18n import _
from oslo_service import _options


config_section = 'ssl'

_SSL_PROTOCOLS = {
    "tlsv1": ssl.PROTOCOL_TLSv1,
    "sslv23": ssl.PROTOCOL_SSLv23
}

_OPTIONAL_PROTOCOLS = {
    'sslv2': 'PROTOCOL_SSLv2',
    'sslv3': 'PROTOCOL_SSLv3',
    'tlsv1_1': 'PROTOCOL_TLSv1_1',
    'tlsv1_2': 'PROTOCOL_TLSv1_2',
}
for protocol in _OPTIONAL_PROTOCOLS:
    try:
        _SSL_PROTOCOLS[protocol] = getattr(ssl,
                                           _OPTIONAL_PROTOCOLS[protocol])
    except AttributeError:  # nosec
        pass


def list_opts():
    """Entry point for oslo-config-generator."""
    return [(config_section, copy.deepcopy(_options.ssl_opts))]


def register_opts(conf):
    """Registers sslutils config options."""
    return conf.register_opts(_options.ssl_opts, config_section)


def is_enabled(conf):
    conf.register_opts(_options.ssl_opts, config_section)
    cert_file = conf.ssl.cert_file
    key_file = conf.ssl.key_file
    ca_file = conf.ssl.ca_file
    use_ssl = cert_file or key_file

    if cert_file and not os.path.exists(cert_file):
        raise RuntimeError(_("Unable to find cert_file : %s") % cert_file)

    if ca_file and not os.path.exists(ca_file):
        raise RuntimeError(_("Unable to find ca_file : %s") % ca_file)

    if key_file and not os.path.exists(key_file):
        raise RuntimeError(_("Unable to find key_file : %s") % key_file)

    if use_ssl and (not cert_file or not key_file):
        raise RuntimeError(_("When running server in SSL mode, you must "
                             "specify both a cert_file and key_file "
                             "option value in your configuration file"))

    return use_ssl


def wrap(conf, sock):
    conf.register_opts(_options.ssl_opts, config_section)
    ssl_kwargs = {
        'server_side': True,
        'certfile': conf.ssl.cert_file,
        'keyfile': conf.ssl.key_file,
        'cert_reqs': ssl.CERT_NONE,
    }

    if conf.ssl.ca_file:
        ssl_kwargs['ca_certs'] = conf.ssl.ca_file
        ssl_kwargs['cert_reqs'] = ssl.CERT_REQUIRED

        if conf.ssl.version:
            key = conf.ssl.version.lower()
            try:
                ssl_kwargs['ssl_version'] = _SSL_PROTOCOLS[key]
            except KeyError:
                raise RuntimeError(
                    _("Invalid SSL version : %s") % conf.ssl.version)

        if conf.ssl.ciphers:
            ssl_kwargs['ciphers'] = conf.ssl.ciphers

    # NOTE(eezhova): SSL/TLS protocol version is injected in ssl_kwargs above,
    # so skipping bandit check
    return ssl.wrap_socket(sock, **ssl_kwargs)  # nosec

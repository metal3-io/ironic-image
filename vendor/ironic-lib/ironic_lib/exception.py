# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Ironic base exception handling.

Includes decorator for re-raising Ironic-type exceptions.

SHOULD include dedicated exception logging.

"""

import collections

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import excutils
import six

from ironic_lib.common.i18n import _


LOG = logging.getLogger(__name__)

exc_log_opts = [
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False,
                help=_('Used if there is a formatting error when generating '
                       'an exception message (a programming error). If True, '
                       'raise an exception; if False, use the unformatted '
                       'message.'),
                deprecated_group='DEFAULT'),
]

CONF = cfg.CONF
CONF.register_opts(exc_log_opts, group='ironic_lib')


def list_opts():
    """Entry point for oslo-config-generator."""
    return [('ironic_lib', exc_log_opts)]


def _ensure_exception_kwargs_serializable(exc_class_name, kwargs):
    """Ensure that kwargs are serializable

    Ensure that all kwargs passed to exception constructor can be passed over
    RPC, by trying to convert them to JSON, or, as a last resort, to string.
    If it is not possible, unserializable kwargs will be removed, letting the
    receiver to handle the exception string as it is configured to.

    :param exc_class_name: a IronicException class name.
    :param kwargs: a dictionary of keyword arguments passed to the exception
        constructor.
    :returns: a dictionary of serializable keyword arguments.
    """
    serializers = [(jsonutils.dumps, _('when converting to JSON')),
                   (six.text_type, _('when converting to string'))]
    exceptions = collections.defaultdict(list)
    serializable_kwargs = {}
    for k, v in kwargs.items():
        for serializer, msg in serializers:
            try:
                serializable_kwargs[k] = serializer(v)
                exceptions.pop(k, None)
                break
            except Exception as e:
                exceptions[k].append(
                    '(%(serializer_type)s) %(e_type)s: %(e_contents)s' %
                    {'serializer_type': msg, 'e_contents': e,
                     'e_type': e.__class__.__name__})
    if exceptions:
        LOG.error("One or more arguments passed to the %(exc_class)s "
                  "constructor as kwargs can not be serialized. The "
                  "serialized arguments: %(serialized)s. These "
                  "unserialized kwargs were dropped because of the "
                  "exceptions encountered during their "
                  "serialization:\n%(errors)s",
                  dict(errors=';\n'.join("%s: %s" % (k, '; '.join(v))
                                         for k, v in exceptions.items()),
                       exc_class=exc_class_name,
                       serialized=serializable_kwargs))
        # We might be able to actually put the following keys' values into
        # format string, but there is no guarantee, drop it just in case.
        for k in exceptions:
            del kwargs[k]
    return serializable_kwargs


class IronicException(Exception):
    """Base Ironic Exception

    To correctly use this class, inherit from it and define
    a '_msg_fmt' property. That _msg_fmt will get printf'd
    with the keyword arguments provided to the constructor.

    If you need to access the message from an exception you should use
    six.text_type(exc)

    """

    _msg_fmt = _("An unknown exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = _ensure_exception_kwargs_serializable(
            self.__class__.__name__, kwargs)

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass
        else:
            self.code = int(kwargs['code'])

        if not message:
            try:
                message = self._msg_fmt % kwargs

            except Exception:
                with excutils.save_and_reraise_exception() as ctxt:
                    # kwargs doesn't match a variable in the message
                    # log the issue and the kwargs
                    prs = ', '.join('%s=%s' % pair for pair in kwargs.items())
                    LOG.exception('Exception in string format operation '
                                  '(arguments %s)', prs)
                    if not CONF.ironic_lib.fatal_exception_format_errors:
                        # at least get the core message out if something
                        # happened
                        message = self._msg_fmt
                        ctxt.reraise = False

        super(IronicException, self).__init__(message)

    def __str__(self):
        """Encode to utf-8 then wsme api can consume it as well."""
        value = self.__unicode__()
        if six.PY3:
            # On Python 3 unicode is the same as str
            return value
        else:
            return value.encode('utf-8')

    def __unicode__(self):
        """Return a unicode representation of the exception message."""
        return six.text_type(self.args[0])

    def format_message(self):
        if self.__class__.__name__.endswith('_Remote'):
            return self.args[0]
        else:
            return six.text_type(self)


class InstanceDeployFailure(IronicException):
    _msg_fmt = _("Failed to deploy instance: %(reason)s")


class FileSystemNotSupported(IronicException):
    _msg_fmt = _("Failed to create a file system. "
                 "File system %(fs)s is not supported.")


class InvalidMetricConfig(IronicException):
    _msg_fmt = _("Invalid value for metrics config option: %(reason)s")


class ServiceLookupFailure(IronicException):
    _msg_fmt = _("Cannot find %(service)s service through multicast")


class ServiceRegistrationFailure(IronicException):
    _msg_fmt = _("Cannot register %(service)s service: %(error)s")

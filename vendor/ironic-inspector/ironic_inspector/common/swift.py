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

# Mostly copied from ironic/common/swift.py

import json

import openstack
from openstack import exceptions as os_exc
from oslo_config import cfg

from ironic_inspector.common.i18n import _
from ironic_inspector.common import keystone
from ironic_inspector import utils

CONF = cfg.CONF


OBJECT_NAME_PREFIX = 'inspector_data'
SWIFT_SESSION = None


def reset_swift_session():
    """Reset the global session variable.

    Mostly useful for unit tests.
    """
    global SWIFT_SESSION
    SWIFT_SESSION = None


class SwiftAPI(object):
    """API for communicating with Swift."""

    def __init__(self):
        """Constructor for creating a SwiftAPI object.

        Authentification is loaded from config file.
        """
        global SWIFT_SESSION

        try:
            if not SWIFT_SESSION:
                SWIFT_SESSION = keystone.get_session('swift')

            self.connection = openstack.connection.Connection(
                session=SWIFT_SESSION,
                oslo_conf=CONF).object_store
        except Exception as exc:
            raise utils.Error(_("Could not connect to the object storage "
                                "service: %s") % exc)

    def create_object(self, object, data, container=CONF.swift.container,
                      headers=None):
        """Uploads a given string to Swift.

        :param object: The name of the object in Swift
        :param data: string data to put in the object
        :param container: The name of the container for the object.
        :param headers: the headers for the object to pass to Swift
        :returns: The Swift UUID of the object
        :raises: utils.Error, if any operation with Swift fails.
        """
        try:
            self.connection.create_container(container)
        except os_exc.SDKException as e:
            err_msg = (_('Swift failed to create container %(container)s. '
                         'Error was: %(error)s') %
                       {'container': container, 'error': e})
            raise utils.Error(err_msg)

        if CONF.swift.delete_after > 0:
            headers = headers or {}
            headers['X-Delete-After'] = CONF.swift.delete_after

        try:
            obj_uuid = self.connection.create_object(
                container, object, data=data, headers=headers)
        except os_exc.SDKException as e:
            err_msg = (_('Swift failed to create object %(object)s in '
                         'container %(container)s. Error was: %(error)s') %
                       {'object': object, 'container': container, 'error': e})
            raise utils.Error(err_msg)

        return obj_uuid

    def get_object(self, object, container=CONF.swift.container):
        """Downloads a given object from Swift.

        :param object: The name of the object in Swift
        :param container: The name of the container for the object.
        :returns: Swift object
        :raises: utils.Error, if the Swift operation fails.
        """
        try:
            obj = self.connection.download_object(object, container=container)
        except os_exc.SDKException as e:
            err_msg = (_('Swift failed to get object %(object)s in '
                         'container %(container)s. Error was: %(error)s') %
                       {'object': object, 'container': container, 'error': e})
            raise utils.Error(err_msg)

        return obj


def store_introspection_data(data, uuid, suffix=None):
    """Uploads introspection data to Swift.

    :param data: data to store in Swift
    :param uuid: UUID of the Ironic node that the data came from
    :param suffix: optional suffix to add to the underlying swift
                   object name
    :returns: name of the Swift object that the data is stored in
    """
    swift_api = SwiftAPI()
    swift_object_name = '%s-%s' % (OBJECT_NAME_PREFIX, uuid)
    if suffix is not None:
        swift_object_name = '%s-%s' % (swift_object_name, suffix)
    swift_api.create_object(swift_object_name, json.dumps(data))
    return swift_object_name


def get_introspection_data(uuid, suffix=None):
    """Downloads introspection data from Swift.

    :param uuid: UUID of the Ironic node that the data came from
    :param suffix: optional suffix to add to the underlying swift
                   object name
    :returns: Swift object with the introspection data
    """
    swift_api = SwiftAPI()
    swift_object_name = '%s-%s' % (OBJECT_NAME_PREFIX, uuid)
    if suffix is not None:
        swift_object_name = '%s-%s' % (swift_object_name, suffix)
    return swift_api.get_object(swift_object_name)

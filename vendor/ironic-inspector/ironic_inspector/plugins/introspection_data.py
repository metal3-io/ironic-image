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

"""Backends for storing introspection data."""

import abc
import json

from oslo_config import cfg
from oslo_utils import excutils
import six

from ironic_inspector.common import swift
from ironic_inspector import node_cache
from ironic_inspector import utils


CONF = cfg.CONF

LOG = utils.getProcessingLogger(__name__)

_STORAGE_EXCLUDED_KEYS = {'logs'}
_UNPROCESSED_DATA_STORE_SUFFIX = 'UNPROCESSED'


def _filter_data_excluded_keys(data):
    return {k: v for k, v in data.items()
            if k not in _STORAGE_EXCLUDED_KEYS}


@six.add_metaclass(abc.ABCMeta)
class BaseStorageBackend(object):

    @abc.abstractmethod
    def get(self, node_uuid, processed=True, get_json=False):
        """Get introspected data from storage backend.

        :param node_uuid: node UUID.
        :param processed: Specify whether the data to be retrieved is
                          processed or not.
        :param get_json: Specify whether return the introspection data in json
                         format, string value is returned if False.
        :returns: the introspection data.
        :raises: IntrospectionDataStoreDisabled if storage backend is disabled.
        """

    @abc.abstractmethod
    def save(self, node_uuid, data, processed=True):
        """Save introspected data to storage backend.

        :param node_uuid: node UUID.
        :param data: the introspected data to be saved, in dict format.
        :param processed: Specify whether the data to be saved is processed or
                          not.
        :raises: IntrospectionDataStoreDisabled if storage backend is disabled.
        """


class NoStore(BaseStorageBackend):
    def get(self, node_uuid, processed=True, get_json=False):
        raise utils.IntrospectionDataStoreDisabled(
            'Introspection data storage is disabled')

    def save(self, node_uuid, data, processed=True):
        LOG.debug('Introspection data storage is disabled, the data will not '
                  'be saved for node %(node)s', {'node': node_uuid})


class SwiftStore(object):
    def get(self, node_uuid, processed=True, get_json=False):
        suffix = None if processed else _UNPROCESSED_DATA_STORE_SUFFIX
        LOG.debug('Fetching introspection data from Swift for %s', node_uuid)
        data = swift.get_introspection_data(node_uuid, suffix=suffix)
        if get_json:
            return json.loads(data)
        return data

    def save(self, node_uuid, data, processed=True):
        suffix = None if processed else _UNPROCESSED_DATA_STORE_SUFFIX
        swift_object_name = swift.store_introspection_data(
            _filter_data_excluded_keys(data),
            node_uuid,
            suffix=suffix
        )
        LOG.info('Introspection data was stored for node %(node)s in Swift '
                 'object %(obj_name)s', {'node': node_uuid,
                                         'obj_name': swift_object_name})


class DatabaseStore(object):
    def get(self, node_uuid, processed=True, get_json=False):
        LOG.debug('Fetching introspection data from database for %(node)s',
                  {'node': node_uuid})
        data = node_cache.get_introspection_data(node_uuid, processed)
        if get_json:
            return data
        return json.dumps(data)

    def save(self, node_uuid, data, processed=True):
        introspection_data = _filter_data_excluded_keys(data)
        try:
            node_cache.store_introspection_data(node_uuid,
                                                introspection_data, processed)
        except Exception as e:
            with excutils.save_and_reraise_exception():
                LOG.exception('Failed to store introspection data in '
                              'database: %(exc)s', {'exc': e})
        else:
            LOG.info('Introspection data was stored in database for node '
                     '%(node)s', {'node': node_uuid})

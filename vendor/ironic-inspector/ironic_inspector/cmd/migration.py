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

"""Migrate introspected data between Swift and database."""

from __future__ import print_function

import sys

from oslo_config import cfg
from oslo_log import log
from oslo_utils import encodeutils
import six

from ironic_inspector.common.i18n import _
from ironic_inspector.conf import opts
from ironic_inspector import node_cache
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector import utils

LOG = log.getLogger(__name__)
CONF = cfg.CONF

_AVAILABLE_STORAGES = [('database', _('The database storage backend')),
                       ('swift', _('The Swift storage backend'))]
_OPTS = [
    cfg.StrOpt('from',
               dest='source_storage',
               required=True,
               choices=_AVAILABLE_STORAGES,
               help=_('The source storage where the introspected data will be '
                      'read from.')),
    cfg.StrOpt('to',
               dest='target_storage',
               required=True,
               choices=_AVAILABLE_STORAGES,
               help=_('The target storage where the introspected data will be '
                      'saved to.'))
]

# Migration result
RESULT_NOCONTENT = 'no content'
RESULT_FAILED = 'failed'
RESULT_SUCCESS = 'success'


def _setup_logger(args=None):
    args = [] if args is None else args
    log.register_options(CONF)
    opts.set_config_defaults()
    opts.parse_args(args)
    log.setup(CONF, 'ironic_inspector')


class MigrationTool(object):

    def _migrate_one(self, node, processed):
        LOG.debug('Starting to migrate introspection data for node '
                  '%(node)s (processed %(processed)s)',
                  {'node': node.uuid, 'processed': processed})
        try:
            data = self.ext_src.get(node.uuid, processed=processed,
                                    get_json=True)
            if not data:
                return RESULT_NOCONTENT
            self.ext_tgt.save(node.uuid, data, processed=processed)
        except Exception as e:
            LOG.error('Migrate introspection data failed for node '
                      '%(node)s (processed %(processed)s), error: '
                      '%(error)s', {'node': node.uuid, 'processed': processed,
                                    'error': e})
            return RESULT_FAILED

        return RESULT_SUCCESS

    def main(self):
        CONF.register_cli_opts(_OPTS)
        _setup_logger(sys.argv[1:])

        if CONF.source_storage == CONF.target_storage:
            raise utils.Error(_('Source and destination can not be the same.'))

        introspection_data_manager = plugins_base.introspection_data_manager()
        self.ext_src = introspection_data_manager[CONF.source_storage].obj
        self.ext_tgt = introspection_data_manager[CONF.target_storage].obj

        nodes = node_cache.get_node_list()
        migration_list = [(n, p) for n in nodes for p in [True, False]]
        failed_records = []
        for node, processed in migration_list:
            result = self._migrate_one(node, processed)
            if result == RESULT_FAILED:
                failed_records.append((node.uuid, processed))

        msg = ('Finished introspection data migration, total records: %d. '
               % len(migration_list))
        if failed_records:
            msg += 'Failed to migrate:\n' + '\n'.join([
                '%s(processed=%s)' % (record[0], record[1])
                for record in failed_records])
        elif len(migration_list) > 0:
            msg += 'all records are migrated successfully.'
        print(msg)


def main():

    try:
        MigrationTool().main()
    except KeyboardInterrupt:
        print(_("... terminating migration tool"), file=sys.stderr)
        return 130
    except Exception as e:
        print(encodeutils.safe_encode(six.text_type(e)), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

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


"""
Tests for database migrations. There are "opportunistic" tests here, supported
backends are: sqlite (used in test environment by default), mysql and
postgresql, which are required properly configured unit test environment.

For the opportunistic testing you need to set up a db named 'openstack_citest'
with user 'openstack_citest' and password 'openstack_citest' on localhost.
The test will then use that db and u/p combo to run the tests.

"""


import contextlib
import datetime

import alembic
from alembic import script
import mock
from oslo_config import cfg
from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy.migration_cli import ext_alembic
from oslo_db.sqlalchemy import orm
from oslo_db.sqlalchemy import test_fixtures
from oslo_db.sqlalchemy import test_migrations
from oslo_db.sqlalchemy import utils as db_utils
from oslo_log import log as logging
from oslo_utils import uuidutils
from oslotest import base as test_base
import sqlalchemy

from ironic_inspector.cmd import dbsync
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector.test import base

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


@contextlib.contextmanager
def patch_with_engine(engine):
    with mock.patch.object(db, 'get_writer_session') as patch_w_sess, \
            mock.patch.object(db, 'get_reader_session') as patch_r_sess:
        patch_w_sess.return_value = patch_r_sess.return_value = (
            orm.get_maker(engine)())
        yield


class WalkVersionsMixin(object):
    def _walk_versions(self, engine=None, alembic_cfg=None):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        with patch_with_engine(engine):
            script_directory = script.ScriptDirectory.from_config(alembic_cfg)

            self.assertIsNone(self.migration_ext.version())

            versions = [ver for ver in script_directory.walk_revisions()]

            for version in reversed(versions):
                self._migrate_up(engine, alembic_cfg,
                                 version.revision, with_data=True)

    def _migrate_up(self, engine, config, version, with_data=False):
        """migrate up to a new version of the db.

        We allow for data insertion and post checks at every
        migration version with special _pre_upgrade_### and
        _check_### functions in the main test.
        """
        # NOTE(sdague): try block is here because it's impossible to debug
        # where a failed data migration happens otherwise
        try:
            if with_data:
                data = None
                pre_upgrade = getattr(
                    self, "_pre_upgrade_%s" % version, None)
                if pre_upgrade:
                    data = pre_upgrade(engine)

            self.migration_ext.upgrade(version)
            self.assertEqual(version, self.migration_ext.version())
            if with_data:
                check = getattr(self, "_check_%s" % version, None)
                if check:
                    check(engine, data)
        except Exception:
            LOG.error("Failed to migrate to version %(version)s on engine "
                      "%(engine)s",
                      {'version': version, 'engine': engine})
            raise


class TestWalkVersions(base.BaseTest, WalkVersionsMixin):
    def setUp(self):
        super(TestWalkVersions, self).setUp()
        self.engine = mock.MagicMock()
        self.migration_ext = mock.MagicMock()
        self.config = mock.MagicMock()
        self.versions = [mock.Mock(revision='2b2'), mock.Mock(revision='1a1')]

    def test_migrate_up(self):
        self.migration_ext.version.return_value = 'dsa123'

        self._migrate_up(self.engine, self.config, 'dsa123')

        self.migration_ext.version.assert_called_with()

    def test_migrate_up_with_data(self):
        test_value = {"a": 1, "b": 2}
        self.migration_ext.version.return_value = '141'
        self._pre_upgrade_141 = mock.MagicMock()
        self._pre_upgrade_141.return_value = test_value
        self._check_141 = mock.MagicMock()

        self._migrate_up(self.engine, self.config, '141', True)

        self._pre_upgrade_141.assert_called_with(self.engine)
        self._check_141.assert_called_with(self.engine, test_value)

    @mock.patch.object(script, 'ScriptDirectory')
    @mock.patch.object(WalkVersionsMixin, '_migrate_up')
    def test_walk_versions_all_default(self, _migrate_up, script_directory):
        fc = script_directory.from_config()
        fc.walk_revisions.return_value = self.versions
        self.migration_ext.version.return_value = None

        self._walk_versions(self.engine, self.config)

        self.migration_ext.version.assert_called_with()

        upgraded = [mock.call(self.engine, self.config, v.revision,
                    with_data=True) for v in reversed(self.versions)]
        self.assertEqual(self._migrate_up.call_args_list, upgraded)

    @mock.patch.object(script, 'ScriptDirectory')
    @mock.patch.object(WalkVersionsMixin, '_migrate_up')
    def test_walk_versions_all_false(self, _migrate_up, script_directory):
        fc = script_directory.from_config()
        fc.walk_revisions.return_value = self.versions
        self.migration_ext.version.return_value = None

        self._walk_versions(self.engine, self.config)

        upgraded = [mock.call(self.engine, self.config, v.revision,
                    with_data=True) for v in reversed(self.versions)]
        self.assertEqual(upgraded, self._migrate_up.call_args_list)


class MigrationCheckersMixin(object):
    def setUp(self):
        super(MigrationCheckersMixin, self).setUp()
        self.engine = enginefacade.writer.get_engine()
        self.config = dbsync._get_alembic_config()
        self.config.ironic_inspector_config = CONF
        # create AlembicExtension with fake config and replace
        # with real one.
        self.migration_ext = ext_alembic.AlembicExtension(
            self.engine, {'alembic_ini_path': ''})
        self.migration_ext.config = self.config

    def test_walk_versions(self):
        self._walk_versions(self.engine, self.config)

    def _check_578f84f38d(self, engine, data):
        nodes = db_utils.get_table(engine, 'nodes')
        col_names = [column.name for column in nodes.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(nodes.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('started_at', col_names)
        self.assertIsInstance(nodes.c.started_at.type, sqlalchemy.types.Float)
        self.assertIn('finished_at', col_names)
        self.assertIsInstance(nodes.c.started_at.type, sqlalchemy.types.Float)
        self.assertIn('error', col_names)
        self.assertIsInstance(nodes.c.error.type, sqlalchemy.types.Text)

        attributes = db_utils.get_table(engine, 'attributes')
        col_names = [column.name for column in attributes.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(attributes.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('name', col_names)
        self.assertIsInstance(attributes.c.name.type, sqlalchemy.types.String)
        self.assertIn('value', col_names)
        self.assertIsInstance(attributes.c.value.type, sqlalchemy.types.String)

        options = db_utils.get_table(engine, 'options')
        col_names = [column.name for column in options.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(options.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('name', col_names)
        self.assertIsInstance(options.c.name.type, sqlalchemy.types.String)
        self.assertIn('value', col_names)
        self.assertIsInstance(options.c.value.type, sqlalchemy.types.Text)

    def _check_d588418040d(self, engine, data):
        rules = db_utils.get_table(engine, 'rules')
        col_names = [column.name for column in rules.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(rules.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('created_at', col_names)
        self.assertIsInstance(rules.c.created_at.type,
                              sqlalchemy.types.DateTime)
        self.assertIn('description', col_names)
        self.assertIsInstance(rules.c.description.type, sqlalchemy.types.Text)
        self.assertIn('disabled', col_names)
        # in some backends bool type is integer
        self.assertIsInstance(rules.c.disabled.type,
                              (sqlalchemy.types.Boolean,
                               sqlalchemy.types.Integer))

        conditions = db_utils.get_table(engine, 'rule_conditions')
        col_names = [column.name for column in conditions.c]
        self.assertIn('id', col_names)
        self.assertIsInstance(conditions.c.id.type, sqlalchemy.types.Integer)
        self.assertIn('rule', col_names)
        self.assertIsInstance(conditions.c.rule.type, sqlalchemy.types.String)
        self.assertIn('op', col_names)
        self.assertIsInstance(conditions.c.op.type, sqlalchemy.types.String)
        self.assertIn('multiple', col_names)
        self.assertIsInstance(conditions.c.multiple.type,
                              sqlalchemy.types.String)
        self.assertIn('field', col_names)
        self.assertIsInstance(conditions.c.field.type, sqlalchemy.types.Text)
        self.assertIn('params', col_names)
        self.assertIsInstance(conditions.c.params.type, sqlalchemy.types.Text)

        actions = db_utils.get_table(engine, 'rule_actions')
        col_names = [column.name for column in actions.c]
        self.assertIn('id', col_names)
        self.assertIsInstance(actions.c.id.type, sqlalchemy.types.Integer)
        self.assertIn('rule', col_names)
        self.assertIsInstance(actions.c.rule.type, sqlalchemy.types.String)
        self.assertIn('action', col_names)
        self.assertIsInstance(actions.c.action.type, sqlalchemy.types.String)
        self.assertIn('params', col_names)
        self.assertIsInstance(actions.c.params.type, sqlalchemy.types.Text)

    def _check_e169a4a81d88(self, engine, data):
        rule_conditions = db_utils.get_table(engine, 'rule_conditions')
        # set invert with default value - False
        data = {'id': 1, 'op': 'eq', 'multiple': 'all'}
        rule_conditions.insert().execute(data)

        conds = rule_conditions.select(
            rule_conditions.c.id == 1).execute().first()
        self.assertFalse(conds['invert'])

        # set invert with - True
        data = {'id': 2, 'op': 'eq', 'multiple': 'all', 'invert': True}
        rule_conditions.insert().execute(data)

        conds = rule_conditions.select(
            rule_conditions.c.id == 2).execute().first()
        self.assertTrue(conds['invert'])

    def _pre_upgrade_d2e48801c8ef(self, engine):
        ok_node_id = uuidutils.generate_uuid()
        err_node_id = uuidutils.generate_uuid()
        data = [
            {
                'uuid': ok_node_id,
                'error': None,
                'finished_at': 0.0,
                'started_at': 0.0
            },
            {
                'uuid': err_node_id,
                'error': 'Oops!',
                'finished_at': 0.0,
                'started_at': 0.0
            }
        ]
        nodes = db_utils.get_table(engine, 'nodes')
        for node in data:
            nodes.insert().execute(node)
        return {'err_node_id': err_node_id, 'ok_node_id': ok_node_id}

    def _check_d2e48801c8ef(self, engine, data):
        nodes = db_utils.get_table(engine, 'nodes')
        col_names = [column.name for column in nodes.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(nodes.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('version_id', col_names)
        self.assertIsInstance(nodes.c.version_id.type, sqlalchemy.types.String)
        self.assertIn('state', col_names)
        self.assertIsInstance(nodes.c.state.type, sqlalchemy.types.String)
        self.assertIn('started_at', col_names)
        self.assertIsInstance(nodes.c.started_at.type, sqlalchemy.types.Float)
        self.assertIn('finished_at', col_names)
        self.assertIsInstance(nodes.c.started_at.type, sqlalchemy.types.Float)
        self.assertIn('error', col_names)
        self.assertIsInstance(nodes.c.error.type, sqlalchemy.types.Text)

        ok_node_id = data['ok_node_id']
        err_node_id = data['err_node_id']
        # assert the ok node is in the (default) finished state
        ok_node = nodes.select(nodes.c.uuid == ok_node_id).execute().first()
        self.assertEqual(istate.States.finished, ok_node['state'])
        # assert err node state is error after the migration
        # even though the default state is finished
        err_node = nodes.select(nodes.c.uuid == err_node_id).execute().first()
        self.assertEqual(istate.States.error, err_node['state'])

    def _pre_upgrade_d00d6e3f38c4(self, engine):
        nodes = db_utils.get_table(engine, 'nodes')
        data = []
        for finished_at in (None, 1234.0):
            node = {'uuid': uuidutils.generate_uuid(),
                    'started_at': 1232.0,
                    'finished_at': finished_at,
                    'error': None}
            nodes.insert().values(node).execute()
            data.append(node)
        return data

    def _check_d00d6e3f38c4(self, engine, data):
        nodes = db_utils.get_table(engine, 'nodes')
        col_names = [column.name for column in nodes.c]

        self.assertIn('started_at', col_names)
        self.assertIn('finished_at', col_names)
        self.assertIsInstance(nodes.c.started_at.type,
                              sqlalchemy.types.DateTime)
        self.assertIsInstance(nodes.c.finished_at.type,
                              sqlalchemy.types.DateTime)

        for node in data:
            finished_at = datetime.datetime.utcfromtimestamp(
                node['finished_at']) if node['finished_at'] else None
            row = nodes.select(nodes.c.uuid == node['uuid']).execute().first()
            self.assertEqual(
                datetime.datetime.utcfromtimestamp(node['started_at']),
                row['started_at'])
            self.assertEqual(
                finished_at,
                row['finished_at'])

    def _pre_upgrade_882b2d84cb1b(self, engine):
        attributes = db_utils.get_table(engine, 'attributes')
        nodes = db_utils.get_table(engine, 'nodes')
        self.node_uuid = uuidutils.generate_uuid()
        node = {
            'uuid': self.node_uuid,
            'started_at': datetime.datetime.utcnow(),
            'finished_at': None,
            'error': None,
            'state': istate.States.starting
        }
        nodes.insert().values(node).execute()
        data = {
            'uuid': self.node_uuid,
            'name': 'foo',
            'value': 'bar'
        }
        attributes.insert().values(data).execute()

    def _check_882b2d84cb1b(self, engine, data):
        attributes = db_utils.get_table(engine, 'attributes')
        col_names = [column.name for column in attributes.c]
        self.assertIn('uuid', col_names)
        self.assertIsInstance(attributes.c.uuid.type, sqlalchemy.types.String)
        self.assertIn('node_uuid', col_names)
        self.assertIsInstance(attributes.c.node_uuid.type,
                              sqlalchemy.types.String)
        self.assertIn('name', col_names)
        self.assertIsInstance(attributes.c.name.type, sqlalchemy.types.String)
        self.assertIn('value', col_names)
        self.assertIsInstance(attributes.c.value.type, sqlalchemy.types.String)

        row = attributes.select(attributes.c.node_uuid ==
                                self.node_uuid).execute().first()
        self.assertEqual(self.node_uuid, row.node_uuid)
        self.assertNotEqual(self.node_uuid, row.uuid)
        self.assertIsNotNone(row.uuid)
        self.assertEqual('foo', row.name)
        self.assertEqual('bar', row.value)

    def _check_2970d2d44edc(self, engine, data):
        nodes = db_utils.get_table(engine, 'nodes')
        data = {'uuid': 'abcd'}
        nodes.insert().execute(data)

        n = nodes.select(nodes.c.uuid == 'abcd').execute().first()
        self.assertIsNone(n['manage_boot'])

    def _check_bf8dec16023c(self, engine, data):
        introspection_data = db_utils.get_table(engine, 'introspection_data')
        col_names = [column.name for column in introspection_data.c]
        self.assertIn('uuid', col_names)
        self.assertIn('processed', col_names)
        self.assertIn('data', col_names)
        self.assertIsInstance(introspection_data.c.uuid.type,
                              sqlalchemy.types.String)
        self.assertIsInstance(introspection_data.c.processed.type,
                              sqlalchemy.types.Boolean)
        self.assertIsInstance(introspection_data.c.data.type,
                              sqlalchemy.types.Text)

    def test_upgrade_and_version(self):
        with patch_with_engine(self.engine):
            self.migration_ext.upgrade('head')
            self.assertIsNotNone(self.migration_ext.version())

    def test_upgrade_twice(self):
        with patch_with_engine(self.engine):
            self.migration_ext.upgrade('578f84f38d')
            v1 = self.migration_ext.version()
            self.migration_ext.upgrade('d588418040d')
            v2 = self.migration_ext.version()
            self.assertNotEqual(v1, v2)


class TestMigrationsMySQL(MigrationCheckersMixin,
                          WalkVersionsMixin,
                          test_fixtures.OpportunisticDBTestMixin,
                          test_base.BaseTestCase):
    FIXTURE = test_fixtures.MySQLOpportunisticFixture


class TestMigrationsPostgreSQL(MigrationCheckersMixin,
                               WalkVersionsMixin,
                               test_fixtures.OpportunisticDBTestMixin,
                               test_base.BaseTestCase):
    FIXTURE = test_fixtures.PostgresqlOpportunisticFixture


class TestMigrationSqlite(MigrationCheckersMixin,
                          WalkVersionsMixin,
                          test_fixtures.OpportunisticDBTestMixin,
                          test_base.BaseTestCase):
    FIXTURE = test_fixtures.OpportunisticDbFixture


class ModelsMigrationSyncMixin(object):

    def setUp(self):
        super(ModelsMigrationSyncMixin, self).setUp()
        self.engine = enginefacade.writer.get_engine()

    def get_metadata(self):
        return db.Base.metadata

    def get_engine(self):
        return self.engine

    def db_sync(self, engine):
        config = dbsync._get_alembic_config()
        config.ironic_inspector_config = CONF
        with patch_with_engine(engine):
            alembic.command.upgrade(config, 'head')


class ModelsMigrationsSyncMysql(ModelsMigrationSyncMixin,
                                test_migrations.ModelsMigrationsSync,
                                test_fixtures.OpportunisticDBTestMixin,
                                test_base.BaseTestCase):
    FIXTURE = test_fixtures.MySQLOpportunisticFixture


class ModelsMigrationsSyncPostgres(ModelsMigrationSyncMixin,
                                   test_migrations.ModelsMigrationsSync,
                                   test_fixtures.OpportunisticDBTestMixin,
                                   test_base.BaseTestCase):
    FIXTURE = test_fixtures.PostgresqlOpportunisticFixture


# NOTE(TheJulia): Sqlite database testing is known to encounter race
# conditions as the default always falls to the same database which
# means a different test runner an collide with the test and fail as
# a result. Commenting out in case we figure out a solid way to
# prevent this. It should be noted we only test actual databases
# in ironic's unit tests. Here we're testing databases and sqlite.
# class ModelsMigrationsSyncSqlite(ModelsMigrationSyncMixin,
#                                  test_migrations.ModelsMigrationsSync,
#                                  test_fixtures.OpportunisticDBTestMixin,
#                                  test_base.BaseTestCase):
#     FIXTURE = test_fixtures.OpportunisticDbFixture

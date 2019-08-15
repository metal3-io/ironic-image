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

import copy
import json
import os
import shutil
import tempfile

import eventlet
import fixtures
from ironicclient import exceptions
import mock
from oslo_config import cfg
from oslo_serialization import base64
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import swift
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector import node_cache
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector.plugins import example as example_plugin
from ironic_inspector.plugins import introspection_data as intros_data_plugin
from ironic_inspector import process
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = cfg.CONF


class BaseTest(test_base.NodeTest):
    def setUp(self):
        super(BaseTest, self).setUp()
        self.started_at = timeutils.utcnow()
        self.all_ports = [mock.Mock(uuid=uuidutils.generate_uuid(),
                                    address=mac) for mac in self.macs]
        self.ports = [self.all_ports[1]]
        self.fake_result_json = 'node json'

        self.cli_fixture = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client', autospec=True))
        self.cli = self.cli_fixture.mock.return_value


class BaseProcessTest(BaseTest):
    def setUp(self):
        super(BaseProcessTest, self).setUp()

        self.cache_fixture = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'find_node', autospec=True))
        self.process_fixture = self.useFixture(
            fixtures.MockPatchObject(process, '_process_node', autospec=True))

        self.find_mock = self.cache_fixture.mock
        self.node_info = node_cache.NodeInfo(
            uuid=self.node.uuid,
            state=istate.States.waiting,
            started_at=self.started_at)
        self.node_info.finished = mock.Mock()
        self.find_mock.return_value = self.node_info
        self.cli.node.get.return_value = self.node
        self.process_mock = self.process_fixture.mock
        self.process_mock.return_value = self.fake_result_json
        self.addCleanup(self._cleanup_lock, self.node_info)

    def _cleanup_lock(self, node_info):
        node_info.release_lock()


class TestProcess(BaseProcessTest):
    def test_ok(self):
        res = process.process(self.data)

        self.assertEqual(self.fake_result_json, res)

        self.find_mock.assert_called_once_with(
            bmc_address=[self.bmc_address, self.bmc_v6address],
            mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.process_mock.assert_called_once_with(
            self.node_info, self.node, self.data)

    def test_no_ipmi(self):
        del self.inventory['bmc_address']
        del self.inventory['bmc_v6address']
        process.process(self.data)

        self.find_mock.assert_called_once_with(bmc_address=[],
                                               mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.process_mock.assert_called_once_with(self.node_info, self.node,
                                                  self.data)

    def test_ipmi_not_detected(self):
        self.inventory['bmc_address'] = '0.0.0.0'
        self.inventory['bmc_v6address'] = '::/0'
        process.process(self.data)

        self.find_mock.assert_called_once_with(bmc_address=[],
                                               mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.process_mock.assert_called_once_with(self.node_info, self.node,
                                                  self.data)

    def test_ipmi_not_detected_with_old_field(self):
        self.inventory['bmc_address'] = '0.0.0.0'
        self.data['ipmi_address'] = '0.0.0.0'
        process.process(self.data)

        self.find_mock.assert_called_once_with(
            bmc_address=[self.bmc_v6address],
            mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.process_mock.assert_called_once_with(self.node_info, self.node,
                                                  self.data)

    def test_not_found_in_cache(self):
        self.find_mock.side_effect = utils.Error('not found')
        self.assertRaisesRegex(utils.Error,
                               'not found',
                               process.process, self.data)
        self.assertFalse(self.cli.node.get.called)
        self.assertFalse(self.process_mock.called)

    @mock.patch.object(node_cache, 'record_node', autospec=True)
    def test_not_found_in_cache_active_introspection(self, mock_record):
        CONF.set_override('permit_active_introspection', True, 'processing')
        self.find_mock.side_effect = utils.NotFoundInCacheError('not found')
        self.cli.node.get.side_effect = exceptions.NotFound('boom')
        self.cache_fixture.mock.acquire_lock = mock.Mock()
        self.cache_fixture.mock.uuid = '1111'
        self.cache_fixture.mock.finished_at = None
        self.cache_fixture.mock.node = mock.Mock()
        mock_record.return_value = self.cache_fixture.mock
        res = process.process(self.data)

        self.assertEqual(self.fake_result_json, res)
        self.find_mock.assert_called_once_with(
            bmc_address=[self.bmc_address, self.bmc_v6address],
            mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        mock_record.assert_called_once_with(
            bmc_addresses=['1.2.3.4',
                           '2001:1234:1234:1234:1234:1234:1234:1234/64'],
            macs=mock.ANY)
        actual_macs = mock_record.call_args[1]['macs']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_not_called()
        self.process_mock.assert_called_once_with(
            mock.ANY, mock.ANY, self.data)

    def test_found_in_cache_active_introspection(self):
        CONF.set_override('permit_active_introspection', True, 'processing')
        self.node.provision_state = 'active'
        self.cache_fixture.mock.acquire_lock = mock.Mock()
        self.cache_fixture.mock.uuid = '1111'
        self.cache_fixture.mock.finished_at = None
        self.cache_fixture.mock.node = mock.Mock()
        res = process.process(self.data)

        self.assertEqual(self.fake_result_json, res)
        self.find_mock.assert_called_once_with(
            bmc_address=[self.bmc_address, self.bmc_v6address],
            mac=mock.ANY)
        actual_macs = self.find_mock.call_args[1]['mac']
        self.assertEqual(sorted(self.all_macs), sorted(actual_macs))
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.process_mock.assert_called_once_with(
            mock.ANY, mock.ANY, self.data)

    def test_not_found_in_ironic(self):
        self.cli.node.get.side_effect = exceptions.NotFound()

        self.assertRaisesRegex(utils.Error,
                               'Node %s was not found' % self.uuid,
                               process.process, self.data)
        self.cli.node.get.assert_called_once_with(self.uuid)
        self.assertFalse(self.process_mock.called)
        self.node_info.finished.assert_called_once_with(
            istate.Events.error, error=mock.ANY)

    def test_already_finished(self):
        self.node_info.finished_at = timeutils.utcnow()
        self.assertRaisesRegex(utils.Error, 'already finished',
                               process.process, self.data)
        self.assertFalse(self.process_mock.called)
        self.assertFalse(self.find_mock.return_value.finished.called)

    def test_expected_exception(self):
        self.process_mock.side_effect = utils.Error('boom')

        self.assertRaisesRegex(utils.Error, 'boom',
                               process.process, self.data)

        self.node_info.finished.assert_called_once_with(
            istate.Events.error, error='boom')

    def test_unexpected_exception(self):
        self.process_mock.side_effect = RuntimeError('boom')

        with self.assertRaisesRegex(utils.Error,
                                    'Unexpected exception') as ctx:
            process.process(self.data)

        self.assertEqual(500, ctx.exception.http_code)
        self.node_info.finished.assert_called_once_with(
            istate.Events.error,
            error='Unexpected exception RuntimeError during processing: boom')

    def test_hook_unexpected_exceptions(self):
        for ext in plugins_base.processing_hooks_manager():
            patcher = mock.patch.object(ext.obj, 'before_processing',
                                        side_effect=RuntimeError('boom'))
            patcher.start()
            self.addCleanup(lambda p=patcher: p.stop())

        self.assertRaisesRegex(utils.Error, 'Unexpected exception',
                               process.process, self.data)

        self.node_info.finished.assert_called_once_with(
            istate.Events.error, error=mock.ANY)
        error_message = self.node_info.finished.call_args[1]['error']
        self.assertIn('RuntimeError', error_message)
        self.assertIn('boom', error_message)

    def test_hook_unexpected_exceptions_no_node(self):
        # Check that error from hooks is raised, not "not found"
        self.find_mock.side_effect = utils.Error('not found')
        for ext in plugins_base.processing_hooks_manager():
            patcher = mock.patch.object(ext.obj, 'before_processing',
                                        side_effect=RuntimeError('boom'))
            patcher.start()
            self.addCleanup(lambda p=patcher: p.stop())

        self.assertRaisesRegex(utils.Error, 'Unexpected exception',
                               process.process, self.data)

        self.assertFalse(self.node_info.finished.called)

    def test_error_if_node_not_found_hook(self):
        self.find_mock.side_effect = utils.NotFoundInCacheError('BOOM')
        self.assertRaisesRegex(utils.Error,
                               'Look up error: BOOM',
                               process.process, self.data)


@mock.patch.object(example_plugin, 'example_not_found_hook',
                   autospec=True)
class TestNodeNotFoundHook(BaseProcessTest):
    def test_node_not_found_hook_run_ok(self, hook_mock):
        CONF.set_override('node_not_found_hook', 'example', 'processing')
        self.find_mock.side_effect = utils.NotFoundInCacheError('BOOM')
        hook_mock.return_value = node_cache.NodeInfo(
            uuid=self.node.uuid,
            started_at=self.started_at)
        res = process.process(self.data)
        self.assertEqual(self.fake_result_json, res)
        hook_mock.assert_called_once_with(self.data)

    def test_node_not_found_hook_run_none(self, hook_mock):
        CONF.set_override('node_not_found_hook', 'example', 'processing')
        self.find_mock.side_effect = utils.NotFoundInCacheError('BOOM')
        hook_mock.return_value = None
        self.assertRaisesRegex(utils.Error,
                               'Node not found hook returned nothing',
                               process.process, self.data)
        hook_mock.assert_called_once_with(self.data)

    def test_node_not_found_hook_exception(self, hook_mock):
        CONF.set_override('node_not_found_hook', 'example', 'processing')
        self.find_mock.side_effect = utils.NotFoundInCacheError('BOOM')
        hook_mock.side_effect = Exception('Hook Error')
        self.assertRaisesRegex(utils.Error,
                               'Node not found hook failed: Hook Error',
                               process.process, self.data)
        hook_mock.assert_called_once_with(self.data)


class TestUnprocessedData(BaseProcessTest):
    @mock.patch.object(process, '_store_unprocessed_data', autospec=True)
    def test_save_unprocessed_data(self, store_mock):
        CONF.set_override('store_data', 'swift', 'processing')
        expected = copy.deepcopy(self.data)

        process.process(self.data)

        store_mock.assert_called_once_with(mock.ANY, expected)

    def test_save_unprocessed_data_failure(self):
        CONF.set_override('store_data', 'swift', 'processing')

        res = process.process(self.data)

        # assert store failure doesn't break processing
        self.assertEqual(self.fake_result_json, res)


@mock.patch.object(example_plugin.ExampleProcessingHook, 'before_processing',
                   autospec=True)
class TestStoreLogs(BaseProcessTest):
    def setUp(self):
        super(TestStoreLogs, self).setUp()
        CONF.set_override('processing_hooks', 'ramdisk_error,example',
                          'processing')

        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tempdir))
        CONF.set_override('ramdisk_logs_dir', self.tempdir, 'processing')

        self.logs = b'test logs'
        self.data['logs'] = base64.encode_as_bytes(self.logs)

    def _check_contents(self, name=None):
        files = os.listdir(self.tempdir)
        self.assertEqual(1, len(files))
        filename = files[0]
        if name is None:
            self.assertTrue(filename.startswith(self.uuid),
                            '%s does not start with uuid' % filename)
        else:
            self.assertEqual(name, filename)
        with open(os.path.join(self.tempdir, filename), 'rb') as fp:
            self.assertEqual(self.logs, fp.read())

    def test_store_on_preprocess_failure(self, hook_mock):
        hook_mock.side_effect = Exception('Hook Error')
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_store_on_process_failure(self, hook_mock):
        self.process_mock.side_effect = utils.Error('boom')
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_store_on_unexpected_process_failure(self, hook_mock):
        self.process_mock.side_effect = RuntimeError('boom')
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_store_on_ramdisk_error(self, hook_mock):
        self.data['error'] = 'boom'
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_store_find_node_error(self, hook_mock):
        self.cli.node.get.side_effect = exceptions.NotFound('boom')
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_no_error_no_logs(self, hook_mock):
        process.process(self.data)
        self.assertEqual([], os.listdir(self.tempdir))

    def test_logs_disabled(self, hook_mock):
        CONF.set_override('ramdisk_logs_dir', None, 'processing')
        hook_mock.side_effect = Exception('Hook Error')
        self.assertRaises(utils.Error, process.process, self.data)
        self.assertEqual([], os.listdir(self.tempdir))

    def test_always_store_logs(self, hook_mock):
        CONF.set_override('always_store_ramdisk_logs', True, 'processing')
        process.process(self.data)
        self._check_contents()

    @mock.patch.object(os, 'makedirs', autospec=True)
    @mock.patch.object(process.LOG, 'exception', autospec=True)
    def test_failure_to_write(self, log_mock, makedirs_mock, hook_mock):
        tempdir = tempfile.mkdtemp()
        logs_dir = os.path.join(tempdir, 'I/never/exist')
        CONF.set_override('always_store_ramdisk_logs', True, 'processing')
        CONF.set_override('ramdisk_logs_dir', logs_dir, 'processing')
        makedirs_mock.side_effect = OSError()
        process.process(self.data)
        os.rmdir(tempdir)
        self.assertEqual([], os.listdir(self.tempdir))
        self.assertTrue(makedirs_mock.called)
        self.assertTrue(log_mock.called)

    def test_directory_is_created(self, hook_mock):
        shutil.rmtree(self.tempdir)
        self.data['error'] = 'boom'
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents()

    def test_store_custom_name(self, hook_mock):
        CONF.set_override('ramdisk_logs_filename_format',
                          '{uuid}-{bmc}-{mac}',
                          'processing')
        self.process_mock.side_effect = utils.Error('boom')
        self.assertRaises(utils.Error, process.process, self.data)
        self._check_contents(name='%s-%s-%s' % (self.uuid,
                                                self.bmc_address,
                                                self.pxe_mac.replace(':', '')))


class TestProcessNode(BaseTest):
    def setUp(self):
        super(TestProcessNode, self).setUp()
        CONF.set_override('processing_hooks',
                          '$processing.default_processing_hooks,example',
                          'processing')
        self.validate_attempts = 5
        self.data['macs'] = self.macs  # validate_interfaces hook
        self.valid_interfaces['eth3'] = {
            'mac': self.macs[1], 'ip': self.ips[1], 'extra': {}, 'pxe': False
        }
        self.data['interfaces'] = self.valid_interfaces
        self.ports = self.all_ports

        self.cli.node.get_boot_device.side_effect = (
            [RuntimeError()] * self.validate_attempts + [None])
        self.cli.port.create.side_effect = self.ports
        self.cli.node.update.return_value = self.node
        self.cli.node.list_ports.return_value = []

        self.useFixture(fixtures.MockPatchObject(
            pxe_filter, 'driver', autospec=True))

        self.useFixture(fixtures.MockPatchObject(
            eventlet.greenthread, 'sleep', autospec=True))
        self.node_info._state = istate.States.waiting
        db.Node(uuid=self.node_info.uuid, state=self.node_info._state,
                started_at=self.node_info.started_at,
                finished_at=self.node_info.finished_at,
                error=self.node_info.error).save(self.session)

    def test_return_includes_uuid(self):
        ret_val = process._process_node(self.node_info, self.node, self.data)
        self.assertEqual(self.uuid, ret_val.get('uuid'))

    @mock.patch.object(example_plugin.ExampleProcessingHook, 'before_update')
    def test_wrong_provision_state(self, post_hook_mock):
        self.node.provision_state = 'active'

        self.assertRaises(utils.Error, process._process_node,
                          self.node_info, self.node, self.data)
        self.assertFalse(post_hook_mock.called)

    @mock.patch.object(example_plugin.ExampleProcessingHook, 'before_update')
    @mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
    def test_ok(self, finished_mock, post_hook_mock):
        process._process_node(self.node_info, self.node, self.data)

        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[0],
                                             extra={},
                                             pxe_enabled=True)
        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[1],
                                             extra={},
                                             pxe_enabled=False)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid, 'off')
        self.assertFalse(self.cli.node.validate.called)

        post_hook_mock.assert_called_once_with(self.data, self.node_info)
        finished_mock.assert_called_once_with(mock.ANY, istate.Events.finish)

    @mock.patch.object(example_plugin.ExampleProcessingHook, 'before_update',
                       autospec=True)
    @mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
    def test_ok_node_active(self, finished_mock, post_hook_mock):
        self.node.provision_state = 'active'
        CONF.set_override('permit_active_introspection', True, 'processing')
        process._process_node(self.node_info, self.node, self.data)

        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[0],
                                             extra={},
                                             pxe_enabled=True)
        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[1],
                                             extra={},
                                             pxe_enabled=False)

        self.cli.node.set_power_state.assert_not_called()
        self.assertFalse(self.cli.node.validate.called)

        post_hook_mock.assert_called_once_with(mock.ANY, self.data,
                                               self.node_info)
        finished_mock.assert_called_once_with(mock.ANY, istate.Events.finish)

    def test_port_failed(self):
        self.cli.port.create.side_effect = (
            [exceptions.Conflict()] + self.ports[1:])

        process._process_node(self.node_info, self.node, self.data)

        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[0],
                                             extra={}, pxe_enabled=True)
        self.cli.port.create.assert_any_call(node_uuid=self.uuid,
                                             address=self.macs[1],
                                             extra={}, pxe_enabled=False)

    @mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
    def test_power_off_failed(self, finished_mock):
        self.cli.node.set_power_state.side_effect = RuntimeError('boom')

        process._process_node(self.node_info, self.node, self.data)

        self.cli.node.set_power_state.assert_called_once_with(self.uuid, 'off')
        finished_mock.assert_called_once_with(
            mock.ANY, istate.Events.error,
            error='Failed to power off node %s, check its power '
            'management configuration: boom' % self.uuid
        )

    @mock.patch.object(example_plugin.ExampleProcessingHook, 'before_update')
    @mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
    def test_power_off_enroll_state(self, finished_mock, post_hook_mock):
        self.node.provision_state = 'enroll'
        self.node_info.node = mock.Mock(return_value=self.node)

        process._process_node(self.node_info, self.node, self.data)

        self.assertTrue(post_hook_mock.called)
        self.assertTrue(self.cli.node.set_power_state.called)
        finished_mock.assert_called_once_with(
            self.node_info, istate.Events.finish)

    @mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
    def test_no_power_off(self, finished_mock):
        CONF.set_override('power_off', False, 'processing')
        process._process_node(self.node_info, self.node, self.data)

        self.assertFalse(self.cli.node.set_power_state.called)
        finished_mock.assert_called_once_with(
            self.node_info, istate.Events.finish)

    @mock.patch.object(swift, 'SwiftAPI', autospec=True)
    def test_store_data_with_swift(self, swift_mock):
        CONF.set_override('store_data', 'swift', 'processing')
        swift_conn = swift_mock.return_value
        name = 'inspector_data-%s' % self.uuid
        expected = self.data

        process._process_node(self.node_info, self.node, self.data)

        swift_conn.create_object.assert_called_once_with(name, mock.ANY)
        self.assertEqual(expected,
                         json.loads(swift_conn.create_object.call_args[0][1]))

    @mock.patch.object(swift, 'SwiftAPI', autospec=True)
    def test_store_data_no_logs_with_swift(self, swift_mock):
        CONF.set_override('store_data', 'swift', 'processing')
        swift_conn = swift_mock.return_value
        name = 'inspector_data-%s' % self.uuid
        self.data['logs'] = 'something'

        process._process_node(self.node_info, self.node, self.data)

        swift_conn.create_object.assert_called_once_with(name, mock.ANY)
        self.assertNotIn('logs',
                         json.loads(swift_conn.create_object.call_args[0][1]))

    @mock.patch.object(node_cache, 'store_introspection_data', autospec=True)
    def test_store_data_with_database(self, store_mock):
        CONF.set_override('store_data', 'database', 'processing')

        process._process_node(self.node_info, self.node, self.data)

        data = intros_data_plugin._filter_data_excluded_keys(self.data)
        store_mock.assert_called_once_with(self.node_info.uuid, data, True)
        self.assertEqual(data, store_mock.call_args[0][1])

    @mock.patch.object(node_cache, 'store_introspection_data', autospec=True)
    def test_store_data_no_logs_with_database(self, store_mock):
        CONF.set_override('store_data', 'database', 'processing')

        self.data['logs'] = 'something'

        process._process_node(self.node_info, self.node, self.data)

        data = intros_data_plugin._filter_data_excluded_keys(self.data)
        store_mock.assert_called_once_with(self.node_info.uuid, data, True)
        self.assertNotIn('logs', store_mock.call_args[0][1])


@mock.patch.object(process, '_reapply', autospec=True)
@mock.patch.object(node_cache, 'get_node', autospec=True)
class TestReapply(BaseTest):
    def prepare_mocks(func):
        @six.wraps(func)
        def wrapper(self, pop_mock, *args, **kw):
            pop_mock.return_value = node_cache.NodeInfo(
                uuid=self.node.uuid,
                started_at=self.started_at)

            pop_mock.return_value.finished = mock.Mock()
            pop_mock.return_value.acquire_lock = mock.Mock()
            return func(self, pop_mock, *args, **kw)

        return wrapper

    def setUp(self):
        super(TestReapply, self).setUp()
        CONF.set_override('store_data', 'swift', 'processing')

    @prepare_mocks
    def test_ok(self, pop_mock, reapply_mock):
        process.reapply(self.uuid)
        pop_mock.assert_called_once_with(self.uuid)
        pop_mock.return_value.acquire_lock.assert_called_once_with(
            blocking=False
        )

        reapply_mock.assert_called_once_with(pop_mock.return_value,
                                             introspection_data=None)

    @prepare_mocks
    def test_locking_failed(self, pop_mock, reapply_mock):
        pop_mock.return_value.acquire_lock.return_value = False
        self.assertRaisesRegex(utils.Error,
                               'Node locked, please, try again later',
                               process.reapply, self.uuid)

        pop_mock.assert_called_once_with(self.uuid)
        pop_mock.return_value.acquire_lock.assert_called_once_with(
            blocking=False
        )

    @prepare_mocks
    def test_reapply_with_data(self, pop_mock, reapply_mock):
        process.reapply(self.uuid, data=self.data)
        pop_mock.assert_called_once_with(self.uuid)
        pop_mock.return_value.acquire_lock.assert_called_once_with(
            blocking=False
        )
        reapply_mock.assert_called_once_with(pop_mock.return_value,
                                             introspection_data=self.data)


@mock.patch.object(example_plugin.ExampleProcessingHook, 'before_update')
@mock.patch.object(process.rules, 'apply', autospec=True)
@mock.patch.object(swift, 'SwiftAPI', autospec=True)
@mock.patch.object(node_cache.NodeInfo, 'finished', autospec=True)
@mock.patch.object(node_cache.NodeInfo, 'release_lock', autospec=True)
class TestReapplyNode(BaseTest):
    def setUp(self):
        super(TestReapplyNode, self).setUp()
        CONF.set_override('processing_hooks',
                          '$processing.default_processing_hooks,example',
                          'processing')
        CONF.set_override('store_data', 'swift', 'processing')
        self.data['macs'] = self.macs
        self.ports = self.all_ports
        self.node_info = node_cache.NodeInfo(uuid=self.uuid,
                                             started_at=self.started_at,
                                             node=self.node)
        self.node_info.invalidate_cache = mock.Mock()

        self.cli.port.create.side_effect = self.ports
        self.cli.node.update.return_value = self.node
        self.cli.node.list_ports.return_value = []
        self.node_info._state = istate.States.finished
        self.commit_fixture = self.useFixture(
            fixtures.MockPatchObject(node_cache.NodeInfo, 'commit',
                                     autospec=True))
        db.Node(uuid=self.node_info.uuid, state=self.node_info._state,
                started_at=self.node_info.started_at,
                finished_at=self.node_info.finished_at,
                error=self.node_info.error).save(self.session)

    def call(self):
        process._reapply(self.node_info, introspection_data=self.data)
        # make sure node_info lock is released after a call
        self.node_info.release_lock.assert_called_once_with(self.node_info)

    def prepare_mocks(fn):
        @six.wraps(fn)
        def wrapper(self, release_mock, finished_mock, swift_mock,
                    *args, **kw):
            finished_mock.side_effect = lambda *a, **kw: \
                release_mock(self.node_info)
            swift_client_mock = swift_mock.return_value
            fn(self, finished_mock, swift_client_mock, *args, **kw)
        return wrapper

    @prepare_mocks
    def test_ok(self, finished_mock, swift_mock, apply_mock, post_hook_mock):
        self.call()

        self.commit_fixture.mock.assert_called_once_with(self.node_info)

        post_hook_mock.assert_called_once_with(mock.ANY, self.node_info)

        self.node_info.invalidate_cache.assert_called_once_with()
        apply_mock.assert_called_once_with(self.node_info, self.data)

        # assert no power operations were performed
        self.assertFalse(self.cli.node.set_power_state.called)
        finished_mock.assert_called_once_with(
            self.node_info, istate.Events.finish)

        # asserting validate_interfaces was called
        self.assertEqual(self.pxe_interfaces, self.data['interfaces'])
        self.assertEqual([self.pxe_mac], self.data['macs'])

        # assert ports were created with whatever there was left
        # behind validate_interfaces
        self.cli.port.create.assert_called_once_with(
            node_uuid=self.uuid,
            address=self.data['macs'][0],
            extra={},
            pxe_enabled=True
        )

    @prepare_mocks
    def test_prehook_failure(self, finished_mock, swift_mock, apply_mock,
                             post_hook_mock):
        CONF.set_override('processing_hooks', 'example',
                          'processing')

        exc = Exception('Failed.')
        swift_mock.get_object.return_value = json.dumps(self.data)

        with mock.patch.object(example_plugin.ExampleProcessingHook,
                               'before_processing') as before_processing_mock:
            before_processing_mock.side_effect = exc
            self.call()

        exc_failure = ('Pre-processing failures detected reapplying '
                       'introspection on stored data:\n'
                       'Unexpected exception %(exc_class)s during '
                       'preprocessing in hook example: %(error)s' %
                       {'exc_class': type(exc).__name__, 'error':
                        exc})
        finished_mock.assert_called_once_with(
            self.node_info, istate.Events.error, error=exc_failure)
        # assert _reapply ended having detected the failure
        self.assertFalse(swift_mock.create_object.called)
        self.assertFalse(apply_mock.called)
        self.assertFalse(post_hook_mock.called)

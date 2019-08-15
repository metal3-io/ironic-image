# Copyright 2011 Justin Santa Barbara
# Copyright 2012 Hewlett-Packard Development Company, L.P.
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
import errno
import os
import os.path

import mock
from oslo_concurrency import processutils
from oslo_config import cfg

from ironic_lib import exception
from ironic_lib.tests import base
from ironic_lib import utils

CONF = cfg.CONF


class BareMetalUtilsTestCase(base.IronicLibTestCase):

    def test_unlink(self):
        with mock.patch.object(os, "unlink", autospec=True) as unlink_mock:
            unlink_mock.return_value = None
            utils.unlink_without_raise("/fake/path")
            unlink_mock.assert_called_once_with("/fake/path")

    def test_unlink_ENOENT(self):
        with mock.patch.object(os, "unlink", autospec=True) as unlink_mock:
            unlink_mock.side_effect = OSError(errno.ENOENT)
            utils.unlink_without_raise("/fake/path")
            unlink_mock.assert_called_once_with("/fake/path")


class ExecuteTestCase(base.IronicLibTestCase):
    # Allow calls to utils.execute() and related functions
    block_execute = False

    @mock.patch.object(processutils, 'execute', autospec=True)
    @mock.patch.object(os.environ, 'copy', return_value={}, autospec=True)
    def test_execute_use_standard_locale_no_env_variables(self, env_mock,
                                                          execute_mock):
        utils.execute('foo', use_standard_locale=True)
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'LC_ALL': 'C'})

    @mock.patch.object(processutils, 'execute', autospec=True)
    def test_execute_use_standard_locale_with_env_variables(self,
                                                            execute_mock):
        utils.execute('foo', use_standard_locale=True,
                      env_variables={'foo': 'bar'})
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'LC_ALL': 'C',
                                                            'foo': 'bar'})

    @mock.patch.object(processutils, 'execute', autospec=True)
    def test_execute_not_use_standard_locale(self, execute_mock):
        utils.execute('foo', use_standard_locale=False,
                      env_variables={'foo': 'bar'})
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'foo': 'bar'})

    def test_execute_without_root_helper(self):
        CONF.set_override('root_helper', None, group='ironic_lib')
        with mock.patch.object(
                processutils, 'execute', autospec=True) as execute_mock:
            utils.execute('foo', run_as_root=False)
            execute_mock.assert_called_once_with('foo', run_as_root=False)

    def test_execute_without_root_helper_run_as_root(self):
        CONF.set_override('root_helper', None, group='ironic_lib')
        with mock.patch.object(
                processutils, 'execute', autospec=True) as execute_mock:
            utils.execute('foo', run_as_root=True)
            execute_mock.assert_called_once_with('foo', run_as_root=False)

    def test_execute_with_root_helper(self):
        with mock.patch.object(
                processutils, 'execute', autospec=True) as execute_mock:
            utils.execute('foo', run_as_root=False)
            execute_mock.assert_called_once_with('foo', run_as_root=False)

    def test_execute_with_root_helper_run_as_root(self):
        with mock.patch.object(
                processutils, 'execute', autospec=True) as execute_mock:
            utils.execute('foo', run_as_root=True)
            execute_mock.assert_called_once_with(
                'foo', run_as_root=True,
                root_helper=CONF.ironic_lib.root_helper)

    @mock.patch.object(utils, 'LOG', autospec=True)
    def _test_execute_with_log_stdout(self, log_mock, log_stdout=None):
        with mock.patch.object(
                processutils, 'execute', autospec=True) as execute_mock:
            execute_mock.return_value = ('stdout', 'stderr')
            if log_stdout is not None:
                utils.execute('foo', log_stdout=log_stdout)
            else:
                utils.execute('foo')
            execute_mock.assert_called_once_with('foo')
            name, args, kwargs = log_mock.debug.mock_calls[1]
            if log_stdout is False:
                self.assertEqual(2, log_mock.debug.call_count)
                self.assertNotIn('stdout', args[0])
            else:
                self.assertEqual(3, log_mock.debug.call_count)
                self.assertIn('stdout', args[0])

    def test_execute_with_log_stdout_default(self):
        self._test_execute_with_log_stdout()

    def test_execute_with_log_stdout_true(self):
        self._test_execute_with_log_stdout(log_stdout=True)

    def test_execute_with_log_stdout_false(self):
        self._test_execute_with_log_stdout(log_stdout=False)


class MkfsTestCase(base.IronicLibTestCase):

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_mkfs(self, execute_mock):
        utils.mkfs('ext4', '/my/block/dev')
        utils.mkfs('msdos', '/my/msdos/block/dev')
        utils.mkfs('swap', '/my/swap/block/dev')

        expected = [mock.call('mkfs', '-t', 'ext4', '-F', '/my/block/dev',
                              run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkfs', '-t', 'msdos', '/my/msdos/block/dev',
                              run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkswap', '/my/swap/block/dev',
                              run_as_root=True,
                              use_standard_locale=True)]
        self.assertEqual(expected, execute_mock.call_args_list)

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_mkfs_with_label(self, execute_mock):
        utils.mkfs('ext4', '/my/block/dev', 'ext4-vol')
        utils.mkfs('msdos', '/my/msdos/block/dev', 'msdos-vol')
        utils.mkfs('swap', '/my/swap/block/dev', 'swap-vol')

        expected = [mock.call('mkfs', '-t', 'ext4', '-F', '-L', 'ext4-vol',
                              '/my/block/dev', run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkfs', '-t', 'msdos', '-n', 'msdos-vol',
                              '/my/msdos/block/dev', run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkswap', '-L', 'swap-vol',
                              '/my/swap/block/dev', run_as_root=True,
                              use_standard_locale=True)]
        self.assertEqual(expected, execute_mock.call_args_list)

    @mock.patch.object(utils, 'execute', autospec=True,
                       side_effect=processutils.ProcessExecutionError(
                           stderr=os.strerror(errno.ENOENT)))
    def test_mkfs_with_unsupported_fs(self, execute_mock):
        self.assertRaises(exception.FileSystemNotSupported,
                          utils.mkfs, 'foo', '/my/block/dev')

    @mock.patch.object(utils, 'execute', autospec=True,
                       side_effect=processutils.ProcessExecutionError(
                           stderr='fake'))
    def test_mkfs_with_unexpected_error(self, execute_mock):
        self.assertRaises(processutils.ProcessExecutionError, utils.mkfs,
                          'ext4', '/my/block/dev', 'ext4-vol')


class IsHttpUrlTestCase(base.IronicLibTestCase):

    def test_is_http_url(self):
        self.assertTrue(utils.is_http_url('http://127.0.0.1'))
        self.assertTrue(utils.is_http_url('https://127.0.0.1'))
        self.assertTrue(utils.is_http_url('HTTP://127.1.2.3'))
        self.assertTrue(utils.is_http_url('HTTPS://127.3.2.1'))
        self.assertFalse(utils.is_http_url('Zm9vYmFy'))
        self.assertFalse(utils.is_http_url('11111111'))


class ParseRootDeviceTestCase(base.IronicLibTestCase):

    def test_parse_root_device_hints_without_operators(self):
        root_device = {
            'wwn': '123456', 'model': 'FOO model', 'size': 12345,
            'serial': 'foo-serial', 'vendor': 'foo VENDOR with space',
            'name': '/dev/sda', 'wwn_with_extension': '123456111',
            'wwn_vendor_extension': '111', 'rotational': True,
            'hctl': '1:0:0:0', 'by_path': '/dev/disk/by-path/1:0:0:0'}
        result = utils.parse_root_device_hints(root_device)
        expected = {
            'wwn': 's== 123456', 'model': 's== foo%20model',
            'size': '== 12345', 'serial': 's== foo-serial',
            'vendor': 's== foo%20vendor%20with%20space',
            'name': 's== /dev/sda', 'wwn_with_extension': 's== 123456111',
            'wwn_vendor_extension': 's== 111', 'rotational': True,
            'hctl': 's== 1%3A0%3A0%3A0',
            'by_path': 's== /dev/disk/by-path/1%3A0%3A0%3A0'}
        self.assertEqual(expected, result)

    def test_parse_root_device_hints_with_operators(self):
        root_device = {
            'wwn': 's== 123456', 'model': 's== foo MODEL', 'size': '>= 12345',
            'serial': 's!= foo-serial', 'vendor': 's== foo VENDOR with space',
            'name': '<or> /dev/sda <or> /dev/sdb',
            'wwn_with_extension': 's!= 123456111',
            'wwn_vendor_extension': 's== 111', 'rotational': True,
            'hctl': 's== 1:0:0:0', 'by_path': 's== /dev/disk/by-path/1:0:0:0'}

        # Validate strings being normalized
        expected = copy.deepcopy(root_device)
        expected['model'] = 's== foo%20model'
        expected['vendor'] = 's== foo%20vendor%20with%20space'
        expected['hctl'] = 's== 1%3A0%3A0%3A0'
        expected['by_path'] = 's== /dev/disk/by-path/1%3A0%3A0%3A0'

        result = utils.parse_root_device_hints(root_device)
        # The hints already contain the operators, make sure we keep it
        self.assertEqual(expected, result)

    def test_parse_root_device_hints_no_hints(self):
        result = utils.parse_root_device_hints({})
        self.assertIsNone(result)

    def test_parse_root_device_hints_convert_size(self):
        for size in (12345, '12345'):
            result = utils.parse_root_device_hints({'size': size})
            self.assertEqual({'size': '== 12345'}, result)

    def test_parse_root_device_hints_invalid_size(self):
        for value in ('not-int', -123, 0):
            self.assertRaises(ValueError, utils.parse_root_device_hints,
                              {'size': value})

    def test_parse_root_device_hints_int_or(self):
        expr = '<or> 123 <or> 456 <or> 789'
        result = utils.parse_root_device_hints({'size': expr})
        self.assertEqual({'size': expr}, result)

    def test_parse_root_device_hints_int_or_invalid(self):
        expr = '<or> 123 <or> non-int <or> 789'
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'size': expr})

    def test_parse_root_device_hints_string_or_space(self):
        expr = '<or> foo <or> foo bar <or> bar'
        expected = '<or> foo <or> foo%20bar <or> bar'
        result = utils.parse_root_device_hints({'model': expr})
        self.assertEqual({'model': expected}, result)

    def _parse_root_device_hints_convert_rotational(self, values,
                                                    expected_value):
        for value in values:
            result = utils.parse_root_device_hints({'rotational': value})
            self.assertEqual({'rotational': expected_value}, result)

    def test_parse_root_device_hints_convert_rotational(self):
        self._parse_root_device_hints_convert_rotational(
            (True, 'true', 'on', 'y', 'yes'), True)

        self._parse_root_device_hints_convert_rotational(
            (False, 'false', 'off', 'n', 'no'), False)

    def test_parse_root_device_hints_invalid_rotational(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'rotational': 'not-bool'})

    def test_parse_root_device_hints_invalid_wwn(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'wwn': 123})

    def test_parse_root_device_hints_invalid_wwn_with_extension(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'wwn_with_extension': 123})

    def test_parse_root_device_hints_invalid_wwn_vendor_extension(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'wwn_vendor_extension': 123})

    def test_parse_root_device_hints_invalid_model(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'model': 123})

    def test_parse_root_device_hints_invalid_serial(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'serial': 123})

    def test_parse_root_device_hints_invalid_vendor(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'vendor': 123})

    def test_parse_root_device_hints_invalid_name(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'name': 123})

    def test_parse_root_device_hints_invalid_hctl(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'hctl': 123})

    def test_parse_root_device_hints_invalid_by_path(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'by_path': 123})

    def test_parse_root_device_hints_non_existent_hint(self):
        self.assertRaises(ValueError, utils.parse_root_device_hints,
                          {'non-existent': 'foo'})

    def test_extract_hint_operator_and_values_single_value(self):
        expected = {'op': '>=', 'values': ['123']}
        self.assertEqual(
            expected, utils._extract_hint_operator_and_values(
                '>= 123', 'size'))

    def test_extract_hint_operator_and_values_multiple_values(self):
        expected = {'op': '<or>', 'values': ['123', '456', '789']}
        expr = '<or> 123 <or> 456 <or> 789'
        self.assertEqual(
            expected, utils._extract_hint_operator_and_values(expr, 'size'))

    def test_extract_hint_operator_and_values_multiple_values_space(self):
        expected = {'op': '<or>', 'values': ['foo', 'foo bar', 'bar']}
        expr = '<or> foo <or> foo bar <or> bar'
        self.assertEqual(
            expected, utils._extract_hint_operator_and_values(expr, 'model'))

    def test_extract_hint_operator_and_values_no_operator(self):
        expected = {'op': '', 'values': ['123']}
        self.assertEqual(
            expected, utils._extract_hint_operator_and_values('123', 'size'))

    def test_extract_hint_operator_and_values_empty_value(self):
        self.assertRaises(
            ValueError, utils._extract_hint_operator_and_values, '', 'size')

    def test_extract_hint_operator_and_values_integer(self):
        expected = {'op': '', 'values': ['123']}
        self.assertEqual(
            expected, utils._extract_hint_operator_and_values(123, 'size'))

    def test__append_operator_to_hints(self):
        root_device = {'serial': 'foo', 'size': 12345,
                       'model': 'foo model', 'rotational': True}
        expected = {'serial': 's== foo', 'size': '== 12345',
                    'model': 's== foo model', 'rotational': True}

        result = utils._append_operator_to_hints(root_device)
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_or(self):
        expr = '<or> foo <or> foo bar <or> bar'
        expected = '<or> foo <or> foo%20bar <or> bar'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_in(self):
        expr = '<in> foo <in> foo bar <in> bar'
        expected = '<in> foo <in> foo%20bar <in> bar'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_op_space(self):
        expr = 's== test string with space'
        expected = 's== test%20string%20with%20space'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_op_no_space(self):
        expr = 's!= SpongeBob'
        expected = 's!= spongebob'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_no_op_space(self):
        expr = 'no operators'
        expected = 'no%20operators'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_no_op_no_space(self):
        expr = 'NoSpace'
        expected = 'nospace'
        result = utils._normalize_hint_expression(expr, 'model')
        self.assertEqual(expected, result)

    def test_normalize_hint_expression_empty_value(self):
        self.assertRaises(
            ValueError, utils._normalize_hint_expression, '', 'size')


class MatchRootDeviceTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(MatchRootDeviceTestCase, self).setUp()
        self.devices = [
            {'name': '/dev/sda', 'size': 64424509440, 'model': 'ok model',
             'serial': 'fakeserial'},
            {'name': '/dev/sdb', 'size': 128849018880, 'model': 'big model',
             'serial': 'veryfakeserial', 'rotational': 'yes'},
            {'name': '/dev/sdc', 'size': 10737418240, 'model': 'small model',
             'serial': 'veryveryfakeserial', 'rotational': False},
        ]

    def test_match_root_device_hints_one_hint(self):
        root_device_hints = {'size': '>= 70'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdb', dev['name'])

    def test_match_root_device_hints_rotational(self):
        root_device_hints = {'rotational': False}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdc', dev['name'])

    def test_match_root_device_hints_rotational_convert_devices_bool(self):
        root_device_hints = {'size': '>=100', 'rotational': True}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdb', dev['name'])

    def test_match_root_device_hints_multiple_hints(self):
        root_device_hints = {'size': '>= 50', 'model': 's==big model',
                             'serial': 's==veryfakeserial'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdb', dev['name'])

    def test_match_root_device_hints_multiple_hints2(self):
        root_device_hints = {
            'size': '<= 20',
            'model': '<or> model 5 <or> foomodel <or> small model <or>',
            'serial': 's== veryveryfakeserial'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdc', dev['name'])

    def test_match_root_device_hints_multiple_hints3(self):
        root_device_hints = {'rotational': False, 'model': '<in> small'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdc', dev['name'])

    def test_match_root_device_hints_no_operators(self):
        root_device_hints = {'size': '120', 'model': 'big model',
                             'serial': 'veryfakeserial'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertEqual('/dev/sdb', dev['name'])

    def test_match_root_device_hints_no_device_found(self):
        root_device_hints = {'size': '>=50', 'model': 's==foo'}
        dev = utils.match_root_device_hints(self.devices, root_device_hints)
        self.assertIsNone(dev)

    @mock.patch.object(utils.LOG, 'warning', autospec=True)
    def test_match_root_device_hints_empty_device_attribute(self, mock_warn):
        empty_dev = [{'name': '/dev/sda', 'model': ' '}]
        dev = utils.match_root_device_hints(empty_dev, {'model': 'foo'})
        self.assertIsNone(dev)
        self.assertTrue(mock_warn.called)


class WaitForDisk(base.IronicLibTestCase):

    def setUp(self):
        super(WaitForDisk, self).setUp()
        CONF.set_override('check_device_interval', .01,
                          group='disk_partitioner')
        CONF.set_override('check_device_max_retries', 2,
                          group='disk_partitioner')

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available(self, mock_exc):
        mock_exc.return_value = ('', '')
        utils.wait_for_disk_to_become_available('fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(1, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True,
                       side_effect=processutils.ProcessExecutionError(
                           stderr='fake'))
    def test_wait_for_disk_to_become_available_no_fuser(self, mock_exc):
        self.assertRaises(exception.IronicException,
                          utils.wait_for_disk_to_become_available,
                          'fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available_device_in_use_psmisc(
            self, mock_exc):
        # Test that the device is not available. This version has the 'psmisc'
        # version of 'fuser' values for stdout and stderr.
        # NOTE(TheJulia): Looks like fuser returns the actual list of pids
        # in the stdout output, where as all other text is returned in
        # stderr.
        # The 'psmisc' version has a leading space character in stdout. The
        # filename is output to stderr
        mock_exc.side_effect = [(' 1234   ', 'fake-dev: '),
                                (' 15503  3919 15510 15511', 'fake-dev:')]
        expected_error = ('Processes with the following PIDs are '
                          'holding device fake-dev: 15503, 3919, 15510, '
                          '15511. Timed out waiting for completion.')
        self.assertRaisesRegex(
            exception.IronicException,
            expected_error,
            utils.wait_for_disk_to_become_available,
            'fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available_device_in_use_busybox(
            self, mock_exc):
        # Test that the device is not available. This version has the 'busybox'
        # version of 'fuser' values for stdout and stderr.
        # NOTE(TheJulia): Looks like fuser returns the actual list of pids
        # in the stdout output, where as all other text is returned in
        # stderr.
        # The 'busybox' version does not have a leading space character in
        # stdout. Also nothing is output to stderr.
        mock_exc.side_effect = [('1234', ''),
                                ('15503  3919 15510 15511', '')]
        expected_error = ('Processes with the following PIDs are '
                          'holding device fake-dev: 15503, 3919, 15510, '
                          '15511. Timed out waiting for completion.')
        self.assertRaisesRegex(
            exception.IronicException,
            expected_error,
            utils.wait_for_disk_to_become_available,
            'fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available_no_device(self, mock_exc):
        # NOTE(TheJulia): Looks like fuser returns the actual list of pids
        # in the stdout output, where as all other text is returned in
        # stderr.

        mock_exc.return_value = ('', 'Specified filename /dev/fake '
                                     'does not exist.')
        expected_error = ('Fuser exited with "Specified filename '
                          '/dev/fake does not exist." while checking '
                          'locks for device fake-dev. Timed out waiting '
                          'for completion.')
        self.assertRaisesRegex(
            exception.IronicException,
            expected_error,
            utils.wait_for_disk_to_become_available,
            'fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available_dev_becomes_avail_psmisc(
            self, mock_exc):
        # Test that initially device is not available but then becomes
        # available. This version has the 'psmisc' version of 'fuser' values
        # for stdout and stderr.
        # The 'psmisc' version has a leading space character in stdout. The
        # filename is output to stderr
        mock_exc.side_effect = [(' 1234   ', 'fake-dev: '),
                                ('', '')]
        utils.wait_for_disk_to_become_available('fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_wait_for_disk_to_become_available_dev_becomes_avail_busybox(
            self, mock_exc):
        # Test that initially device is not available but then becomes
        # available. This version has the 'busybox' version of 'fuser' values
        # for stdout and stderr.
        # The 'busybox' version does not have a leading space character in
        # stdout. Also nothing is output to stderr.
        mock_exc.side_effect = [('1234 5895', ''),
                                ('', '')]
        utils.wait_for_disk_to_become_available('fake-dev')
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        self.assertEqual(2, mock_exc.call_count)
        mock_exc.assert_has_calls([fuser_call, fuser_call])

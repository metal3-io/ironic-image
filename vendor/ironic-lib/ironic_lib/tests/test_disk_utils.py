# Copyright 2014 Red Hat, Inc.
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

import gzip
import os
import shutil
import stat
import tempfile

import mock
from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_serialization import base64
from oslo_utils import imageutils
import requests

from ironic_lib import disk_partitioner
from ironic_lib import disk_utils
from ironic_lib import exception
from ironic_lib.tests import base
from ironic_lib import utils

CONF = cfg.CONF


@mock.patch.object(utils, 'execute', autospec=True)
class ListPartitionsTestCase(base.IronicLibTestCase):

    def test_correct(self, execute_mock):
        output = """
BYT;
/dev/sda:500107862016B:scsi:512:4096:msdos:ATA HGST HTS725050A7:;
1:1.00MiB:501MiB:500MiB:ext4::boot;
2:501MiB:476940MiB:476439MiB:::;
"""
        expected = [
            {'number': 1, 'start': 1, 'end': 501, 'size': 500,
             'filesystem': 'ext4', 'partition_name': '', 'flags': 'boot'},
            {'number': 2, 'start': 501, 'end': 476940, 'size': 476439,
             'filesystem': '', 'partition_name': '', 'flags': ''},
        ]
        execute_mock.return_value = (output, '')
        result = disk_utils.list_partitions('/dev/fake')
        self.assertEqual(expected, result)
        execute_mock.assert_called_once_with(
            'parted', '-s', '-m', '/dev/fake', 'unit', 'MiB', 'print',
            use_standard_locale=True, run_as_root=True)

    @mock.patch.object(disk_utils.LOG, 'warning', autospec=True)
    def test_incorrect(self, log_mock, execute_mock):
        output = """
BYT;
/dev/sda:500107862016B:scsi:512:4096:msdos:ATA HGST HTS725050A7:;
1:XX1076MiB:---:524MiB:ext4::boot;
"""
        execute_mock.return_value = (output, '')
        self.assertEqual([], disk_utils.list_partitions('/dev/fake'))
        self.assertEqual(1, log_mock.call_count)


@mock.patch.object(utils, 'execute', autospec=True)
class ListPartitionsGPTTestCase(base.IronicLibTestCase):

    def test_correct(self, execute_mock):
        output = """
BYT;
/dev/vda:40960MiB:virtblk:512:512:gpt:Virtio Block Device:;
2:1.00MiB:2.00MiB:1.00MiB::Bios partition:bios_grub;
1:4.00MiB:5407MiB:5403MiB:ext4:Root partition:;
3:5407MiB:5507MiB:100MiB:fat16:Boot partition:boot, esp;
"""
        expected = [
            {'end': 2, 'number': 2, 'start': 1, 'flags': 'bios_grub',
             'filesystem': '', 'partition_name': 'Bios partition', 'size': 1},
            {'end': 5407, 'number': 1, 'start': 4, 'flags': '',
             'filesystem': 'ext4', 'partition_name': 'Root partition',
             'size': 5403},
            {'end': 5507, 'number': 3, 'start': 5407,
             'flags': 'boot, esp', 'filesystem': 'fat16',
             'partition_name': 'Boot partition', 'size': 100},
        ]
        execute_mock.return_value = (output, '')
        result = disk_utils.list_partitions('/dev/fake')
        self.assertEqual(expected, result)
        execute_mock.assert_called_once_with(
            'parted', '-s', '-m', '/dev/fake', 'unit', 'MiB', 'print',
            use_standard_locale=True, run_as_root=True)

    @mock.patch.object(disk_utils.LOG, 'warning', autospec=True)
    def test_incorrect(self, log_mock, execute_mock):
        output = """
BYT;
/dev/vda:40960MiB:virtblk:512:512:gpt:Virtio Block Device:;
2:XX1.00MiB:---:1.00MiB::primary:bios_grub;
"""
        execute_mock.return_value = (output, '')
        self.assertEqual([], disk_utils.list_partitions('/dev/fake'))
        self.assertEqual(1, log_mock.call_count)


@mock.patch.object(disk_partitioner.DiskPartitioner, 'commit', lambda _: None)
class WorkOnDiskTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(WorkOnDiskTestCase, self).setUp()
        self.image_path = '/tmp/xyz/image'
        self.root_mb = 128
        self.swap_mb = 64
        self.ephemeral_mb = 0
        self.ephemeral_format = None
        self.configdrive_mb = 0
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"
        self.dev = '/dev/fake'
        self.swap_part = '/dev/fake-part1'
        self.root_part = '/dev/fake-part2'

        self.mock_ibd_obj = mock.patch.object(
            disk_utils, 'is_block_device', autospec=True)
        self.mock_ibd = self.mock_ibd_obj.start()
        self.addCleanup(self.mock_ibd_obj.stop)
        self.mock_mp_obj = mock.patch.object(
            disk_utils, 'make_partitions', autospec=True)
        self.mock_mp = self.mock_mp_obj.start()
        self.addCleanup(self.mock_mp_obj.stop)
        self.mock_remlbl_obj = mock.patch.object(
            disk_utils, 'destroy_disk_metadata', autospec=True)
        self.mock_remlbl = self.mock_remlbl_obj.start()
        self.addCleanup(self.mock_remlbl_obj.stop)
        self.mock_mp.return_value = {'swap': self.swap_part,
                                     'root': self.root_part}

    def test_no_root_partition(self):
        self.mock_ibd.return_value = False
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.work_on_disk, self.dev, self.root_mb,
                          self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path,
                          self.node_uuid)
        self.mock_ibd.assert_called_once_with(self.root_part)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")

    def test_no_swap_partition(self):
        self.mock_ibd.side_effect = iter([True, False])
        calls = [mock.call(self.root_part),
                 mock.call(self.swap_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.work_on_disk, self.dev, self.root_mb,
                          self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path,
                          self.node_uuid)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")

    def test_no_ephemeral_partition(self):
        ephemeral_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'swap': swap_part,
                                     'root': root_part}
        self.mock_ibd.side_effect = iter([True, True, False])
        calls = [mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(ephemeral_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.work_on_disk, self.dev, self.root_mb,
                          self.swap_mb, ephemeral_mb, ephemeral_format,
                          self.image_path, self.node_uuid)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")

    @mock.patch.object(utils, 'unlink_without_raise', autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive', autospec=True)
    def test_no_configdrive_partition(self, mock_configdrive, mock_unlink):
        mock_configdrive.return_value = (10, 'fake-path')
        swap_part = '/dev/fake-part1'
        configdrive_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        configdrive_url = 'http://1.2.3.4/cd'
        configdrive_mb = 10

        self.mock_mp.return_value = {'swap': swap_part,
                                     'configdrive': configdrive_part,
                                     'root': root_part}
        self.mock_ibd.side_effect = iter([True, True, False])
        calls = [mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(configdrive_part)]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.work_on_disk, self.dev, self.root_mb,
                          self.swap_mb, self.ephemeral_mb,
                          self.ephemeral_format, self.image_path,
                          self.node_uuid, preserve_ephemeral=False,
                          configdrive=configdrive_url,
                          boot_option="netboot")
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             configdrive_mb, self.node_uuid,
                                             commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")
        mock_unlink.assert_called_once_with('fake-path')

    @mock.patch.object(utils, 'mkfs', lambda fs, path, label=None: None)
    @mock.patch.object(disk_utils, 'block_uuid', lambda p: 'uuid')
    @mock.patch.object(disk_utils, 'populate_image', autospec=True)
    def test_without_image(self, mock_populate):
        ephemeral_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'swap': swap_part,
                                     'root': root_part}
        self.mock_ibd.return_value = True
        calls = [mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(ephemeral_part)]
        res = disk_utils.work_on_disk(self.dev, self.root_mb,
                                      self.swap_mb, ephemeral_mb,
                                      ephemeral_format,
                                      None, self.node_uuid)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")
        self.assertEqual(root_part, res['partitions']['root'])
        self.assertEqual('uuid', res['root uuid'])
        self.assertFalse(mock_populate.called)

    @mock.patch.object(utils, 'mkfs', lambda fs, path, label=None: None)
    @mock.patch.object(disk_utils, 'block_uuid', lambda p: 'uuid')
    @mock.patch.object(disk_utils, 'populate_image', lambda image_path,
                       root_path, conv_flags=None: None)
    def test_gpt_disk_label(self):
        ephemeral_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'swap': swap_part,
                                     'root': root_part}
        self.mock_ibd.return_value = True
        calls = [mock.call(root_part),
                 mock.call(swap_part),
                 mock.call(ephemeral_part)]
        disk_utils.work_on_disk(self.dev, self.root_mb,
                                self.swap_mb, ephemeral_mb, ephemeral_format,
                                self.image_path, self.node_uuid,
                                disk_label='gpt', conv_flags=None)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label='gpt',
                                             cpu_arch="")

    @mock.patch.object(disk_utils, 'block_uuid', autospec=True)
    @mock.patch.object(disk_utils, 'populate_image', autospec=True)
    @mock.patch.object(utils, 'mkfs', autospec=True)
    def test_uefi_localboot(self, mock_mkfs, mock_populate_image,
                            mock_block_uuid):
        """Test that we create a fat filesystem with UEFI localboot."""
        root_part = '/dev/fake-part1'
        efi_part = '/dev/fake-part2'
        self.mock_mp.return_value = {'root': root_part,
                                     'efi system partition': efi_part}
        self.mock_ibd.return_value = True
        mock_ibd_calls = [mock.call(root_part),
                          mock.call(efi_part)]

        disk_utils.work_on_disk(self.dev, self.root_mb,
                                self.swap_mb, self.ephemeral_mb,
                                self.ephemeral_format,
                                self.image_path, self.node_uuid,
                                boot_option="local", boot_mode="uefi")

        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="local",
                                             boot_mode="uefi",
                                             disk_label=None,
                                             cpu_arch="")
        self.assertEqual(self.mock_ibd.call_args_list, mock_ibd_calls)
        mock_mkfs.assert_called_once_with(fs='vfat', path=efi_part,
                                          label='efi-part')
        mock_populate_image.assert_called_once_with(self.image_path,
                                                    root_part, conv_flags=None)
        mock_block_uuid.assert_any_call(root_part)
        mock_block_uuid.assert_any_call(efi_part)

    @mock.patch.object(disk_utils, 'block_uuid', autospec=True)
    @mock.patch.object(disk_utils, 'populate_image', autospec=True)
    @mock.patch.object(utils, 'mkfs', autospec=True)
    def test_preserve_ephemeral(self, mock_mkfs, mock_populate_image,
                                mock_block_uuid):
        """Test that ephemeral partition doesn't get overwritten."""
        ephemeral_part = '/dev/fake-part1'
        root_part = '/dev/fake-part2'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'root': root_part}
        self.mock_ibd.return_value = True
        calls = [mock.call(root_part),
                 mock.call(ephemeral_part)]
        disk_utils.work_on_disk(self.dev, self.root_mb,
                                self.swap_mb, ephemeral_mb, ephemeral_format,
                                self.image_path, self.node_uuid,
                                preserve_ephemeral=True)
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=False,
                                             boot_option="netboot",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="")
        self.assertFalse(mock_mkfs.called)

    @mock.patch.object(disk_utils, 'block_uuid', autospec=True)
    @mock.patch.object(disk_utils, 'populate_image', autospec=True)
    @mock.patch.object(utils, 'mkfs', autospec=True)
    def test_ppc64le_prep_part(self, mock_mkfs, mock_populate_image,
                               mock_block_uuid):
        """Test that PReP partition uuid is returned."""
        prep_part = '/dev/fake-part1'
        root_part = '/dev/fake-part2'

        self.mock_mp.return_value = {'PReP Boot partition': prep_part,
                                     'root': root_part}
        self.mock_ibd.return_vaue = True
        calls = [mock.call(root_part),
                 mock.call(prep_part)]
        disk_utils.work_on_disk(self.dev, self.root_mb,
                                self.swap_mb, self.ephemeral_mb,
                                self.ephemeral_format, self.image_path,
                                self.node_uuid, boot_option="local",
                                cpu_arch='ppc64le')
        self.assertEqual(self.mock_ibd.call_args_list, calls)
        self.mock_mp.assert_called_once_with(self.dev, self.root_mb,
                                             self.swap_mb, self.ephemeral_mb,
                                             self.configdrive_mb,
                                             self.node_uuid, commit=True,
                                             boot_option="local",
                                             boot_mode="bios",
                                             disk_label=None,
                                             cpu_arch="ppc64le")
        self.assertFalse(mock_mkfs.called)

    @mock.patch.object(disk_utils, 'block_uuid', autospec=True)
    @mock.patch.object(disk_utils, 'populate_image', autospec=True)
    @mock.patch.object(utils, 'mkfs', autospec=True)
    def test_convert_to_sparse(self, mock_mkfs, mock_populate_image,
                               mock_block_uuid):
        ephemeral_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_part = '/dev/fake-part3'
        ephemeral_mb = 256
        ephemeral_format = 'exttest'

        self.mock_mp.return_value = {'ephemeral': ephemeral_part,
                                     'swap': swap_part,
                                     'root': root_part}
        self.mock_ibd.return_value = True
        disk_utils.work_on_disk(self.dev, self.root_mb,
                                self.swap_mb, ephemeral_mb, ephemeral_format,
                                self.image_path, self.node_uuid,
                                disk_label='gpt', conv_flags='sparse')

        mock_populate_image.assert_called_once_with(self.image_path,
                                                    root_part,
                                                    conv_flags='sparse')


class GetUEFIDiskIdentifierTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(GetUEFIDiskIdentifierTestCase, self).setUp()
        self.dev = '/dev/fake'

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_get_uefi_disk_identifier_uefi_bootable_image(self, mock_execute):
        mock_execute.return_value = ('', '')
        fdisk_output = """
Disk /dev/sda: 931.5 GiB, 1000171331584 bytes, 1953459632 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 262144 bytes / 262144 bytes
Disklabel type: gpt
Disk identifier: 73457A6C-3595-4965-8D83-2EA1BD85F327

Device          Start        End    Sectors   Size Type
/dev/fake-part1        2048    1050623    1048576   512M EFI System
/dev/fake-part2     1050624 1920172031 1919121408 915.1G Linux filesystem
/dev/fake-part3  1920172032 1953458175   33286144  15.9G Linux swap
"""
        partition_id = '/dev/fake-part1'
        lsblk_output = 'UUID="ABCD-B05B"\n'
        part_result = 'ABCD-B05B'
        mock_execute.side_effect = [(fdisk_output, ''), (lsblk_output, '')]
        result = disk_utils.get_uefi_disk_identifier(self.dev)
        self.assertEqual(part_result, result)
        execute_calls = [
            mock.call('fdisk', '-l', self.dev, run_as_root=True),
            mock.call('lsblk', '-PbioUUID', partition_id,
                      run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_get_uefi_disk_identifier_non_uefi_bootable_image(self,
                                                              mock_execute):
        mock_execute.return_value = ('', '')
        fdisk_output = """
Disk /dev/vda: 50 GiB, 53687091200 bytes, 104857600 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disklabel type: dos
Disk identifier: 0xb82b9faf

Device     Boot Start       End   Sectors Size Id Type
/dev/fake-part1  *     2048 104857566 104855519  50G 83 Linux
"""
        partition_id = None
        mock_execute.side_effect = [(fdisk_output, ''),
                                    processutils.ProcessExecutionError()]
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.get_uefi_disk_identifier, self.dev)
        execute_calls = [
            mock.call('fdisk', '-l', self.dev, run_as_root=True),
            mock.call('lsblk', '-PbioUUID', partition_id, run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)


@mock.patch.object(utils, 'execute', autospec=True)
class MakePartitionsTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(MakePartitionsTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.root_mb = 1024
        self.swap_mb = 512
        self.ephemeral_mb = 0
        self.configdrive_mb = 0
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"
        self.efi_size = CONF.disk_utils.efi_system_partition_size
        self.bios_size = CONF.disk_utils.bios_boot_partition_size

    def _get_parted_cmd(self, dev, label=None):
        if label is None:
            label = 'msdos'

        return ['parted', '-a', 'optimal', '-s', dev,
                '--', 'unit', 'MiB', 'mklabel', label]

    def _test_make_partitions(self, mock_exc, boot_option, boot_mode='bios',
                              disk_label=None, cpu_arch=""):
        mock_exc.return_value = ('', '')
        disk_utils.make_partitions(self.dev, self.root_mb, self.swap_mb,
                                   self.ephemeral_mb, self.configdrive_mb,
                                   self.node_uuid, boot_option=boot_option,
                                   boot_mode=boot_mode, disk_label=disk_label,
                                   cpu_arch=cpu_arch)

        if boot_option == "local" and boot_mode == "uefi":
            add_efi_sz = lambda x: str(x + self.efi_size)
            expected_mkpart = ['mkpart', 'primary', 'fat32', '1',
                               add_efi_sz(1),
                               'set', '1', 'boot', 'on',
                               'mkpart', 'primary', 'linux-swap',
                               add_efi_sz(1), add_efi_sz(513), 'mkpart',
                               'primary', '', add_efi_sz(513),
                               add_efi_sz(1537)]
        else:
            if boot_option == "local":
                if disk_label == "gpt":
                    if cpu_arch.startswith('ppc64'):
                        expected_mkpart = ['mkpart', 'primary', '', '1', '9',
                                           'set', '1', 'prep', 'on',
                                           'mkpart', 'primary', 'linux-swap',
                                           '9', '521', 'mkpart', 'primary',
                                           '', '521', '1545']
                    else:
                        add_bios_sz = lambda x: str(x + self.bios_size)
                        expected_mkpart = ['mkpart', 'primary', '', '1',
                                           add_bios_sz(1),
                                           'set', '1', 'bios_grub', 'on',
                                           'mkpart', 'primary', 'linux-swap',
                                           add_bios_sz(1), add_bios_sz(513),
                                           'mkpart', 'primary', '',
                                           add_bios_sz(513), add_bios_sz(1537)]
                elif cpu_arch.startswith('ppc64'):
                    expected_mkpart = ['mkpart', 'primary', '', '1', '9',
                                       'set', '1', 'boot', 'on',
                                       'set', '1', 'prep', 'on',
                                       'mkpart', 'primary', 'linux-swap',
                                       '9', '521', 'mkpart', 'primary',
                                       '', '521', '1545']
                else:
                    expected_mkpart = ['mkpart', 'primary', 'linux-swap', '1',
                                       '513', 'mkpart', 'primary', '', '513',
                                       '1537', 'set', '2', 'boot', 'on']
            else:
                expected_mkpart = ['mkpart', 'primary', 'linux-swap', '1',
                                   '513', 'mkpart', 'primary', '', '513',
                                   '1537']
        self.dev = 'fake-dev'
        parted_cmd = (self._get_parted_cmd(self.dev, disk_label) +
                      expected_mkpart)
        parted_call = mock.call(*parted_cmd, use_standard_locale=True,
                                run_as_root=True, check_exit_code=[0])
        fuser_cmd = ['fuser', 'fake-dev']
        fuser_call = mock.call(*fuser_cmd, run_as_root=True,
                               check_exit_code=[0, 1])
        mock_exc.assert_has_calls([parted_call, fuser_call])

    def test_make_partitions(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="netboot")

    def test_make_partitions_local_boot(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="local")

    def test_make_partitions_local_boot_uefi(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="local",
                                   boot_mode="uefi", disk_label="gpt")

    def test_make_partitions_local_boot_gpt_bios(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="local",
                                   disk_label="gpt")

    def test_make_partitions_disk_label_gpt(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="netboot",
                                   disk_label="gpt")

    def test_make_partitions_mbr_with_prep(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="local",
                                   disk_label="msdos", cpu_arch="ppc64le")

    def test_make_partitions_gpt_with_prep(self, mock_exc):
        self._test_make_partitions(mock_exc, boot_option="local",
                                   disk_label="gpt", cpu_arch="ppc64le")

    def test_make_partitions_with_ephemeral(self, mock_exc):
        self.ephemeral_mb = 2048
        expected_mkpart = ['mkpart', 'primary', '', '1', '2049',
                           'mkpart', 'primary', 'linux-swap', '2049', '2561',
                           'mkpart', 'primary', '', '2561', '3585']
        self.dev = 'fake-dev'
        cmd = self._get_parted_cmd(self.dev) + expected_mkpart
        mock_exc.return_value = ('', '')
        disk_utils.make_partitions(self.dev, self.root_mb, self.swap_mb,
                                   self.ephemeral_mb, self.configdrive_mb,
                                   self.node_uuid)

        parted_call = mock.call(*cmd, use_standard_locale=True,
                                run_as_root=True, check_exit_code=[0])
        mock_exc.assert_has_calls([parted_call])

    def test_make_partitions_with_iscsi_device(self, mock_exc):
        self.ephemeral_mb = 2048
        expected_mkpart = ['mkpart', 'primary', '', '1', '2049',
                           'mkpart', 'primary', 'linux-swap', '2049', '2561',
                           'mkpart', 'primary', '', '2561', '3585']
        self.dev = '/dev/iqn.2008-10.org.openstack:%s.fake-9' % self.node_uuid
        ep = '/dev/iqn.2008-10.org.openstack:%s.fake-9-part1' % self.node_uuid
        swap = ('/dev/iqn.2008-10.org.openstack:%s.fake-9-part2'
                % self.node_uuid)
        root = ('/dev/iqn.2008-10.org.openstack:%s.fake-9-part3'
                % self.node_uuid)
        expected_result = {'ephemeral': ep,
                           'swap': swap,
                           'root': root}
        cmd = self._get_parted_cmd(self.dev) + expected_mkpart
        mock_exc.return_value = ('', '')
        result = disk_utils.make_partitions(
            self.dev, self.root_mb, self.swap_mb, self.ephemeral_mb,
            self.configdrive_mb, self.node_uuid)

        parted_call = mock.call(*cmd, use_standard_locale=True,
                                run_as_root=True, check_exit_code=[0])
        mock_exc.assert_has_calls([parted_call])
        self.assertEqual(expected_result, result)

    def test_make_partitions_with_nvme_device(self, mock_exc):
        self.ephemeral_mb = 2048
        expected_mkpart = ['mkpart', 'primary', '', '1', '2049',
                           'mkpart', 'primary', 'linux-swap', '2049', '2561',
                           'mkpart', 'primary', '', '2561', '3585']
        self.dev = '/dev/nvmefake-9'
        ep = '/dev/nvmefake-9p1'
        swap = '/dev/nvmefake-9p2'
        root = '/dev/nvmefake-9p3'
        expected_result = {'ephemeral': ep,
                           'swap': swap,
                           'root': root}
        cmd = self._get_parted_cmd(self.dev) + expected_mkpart
        mock_exc.return_value = ('', '')
        result = disk_utils.make_partitions(
            self.dev, self.root_mb, self.swap_mb, self.ephemeral_mb,
            self.configdrive_mb, self.node_uuid)

        parted_call = mock.call(*cmd, use_standard_locale=True,
                                run_as_root=True, check_exit_code=[0])
        mock_exc.assert_has_calls([parted_call])
        self.assertEqual(expected_result, result)

    def test_make_partitions_with_local_device(self, mock_exc):
        self.ephemeral_mb = 2048
        expected_mkpart = ['mkpart', 'primary', '', '1', '2049',
                           'mkpart', 'primary', 'linux-swap', '2049', '2561',
                           'mkpart', 'primary', '', '2561', '3585']
        self.dev = 'fake-dev'
        expected_result = {'ephemeral': 'fake-dev1',
                           'swap': 'fake-dev2',
                           'root': 'fake-dev3'}
        cmd = self._get_parted_cmd(self.dev) + expected_mkpart
        mock_exc.return_value = ('', '')
        result = disk_utils.make_partitions(
            self.dev, self.root_mb, self.swap_mb, self.ephemeral_mb,
            self.configdrive_mb, self.node_uuid)

        parted_call = mock.call(*cmd, use_standard_locale=True,
                                run_as_root=True, check_exit_code=[0])
        mock_exc.assert_has_calls([parted_call])
        self.assertEqual(expected_result, result)


@mock.patch.object(utils, 'execute', autospec=True, return_value=('', ''))
class DestroyMetaDataTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(DestroyMetaDataTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    def test_destroy_disk_metadata(self, mock_exec):
        expected_calls = [mock.call('wipefs', '--force', '--all', 'fake-dev',
                                    run_as_root=True,
                                    use_standard_locale=True),
                          mock.call('sgdisk', '-Z', 'fake-dev',
                                    run_as_root=True,
                                    use_standard_locale=True),
                          mock.call('fuser', self.dev,
                                    check_exit_code=[0, 1],
                                    run_as_root=True)]
        disk_utils.destroy_disk_metadata(self.dev, self.node_uuid)
        mock_exec.assert_has_calls(expected_calls)

    def test_destroy_disk_metadata_wipefs_fail(self, mock_exec):
        mock_exec.side_effect = processutils.ProcessExecutionError

        expected_call = [mock.call('wipefs', '--force', '--all', 'fake-dev',
                                   run_as_root=True,
                                   use_standard_locale=True)]
        self.assertRaises(processutils.ProcessExecutionError,
                          disk_utils.destroy_disk_metadata,
                          self.dev,
                          self.node_uuid)
        mock_exec.assert_has_calls(expected_call)

    def test_destroy_disk_metadata_sgdisk_fail(self, mock_exec):
        expected_calls = [mock.call('wipefs', '--force', '--all', 'fake-dev',
                                    run_as_root=True,
                                    use_standard_locale=True),
                          mock.call('sgdisk', '-Z', 'fake-dev',
                                    run_as_root=True,
                                    use_standard_locale=True)]
        mock_exec.side_effect = [(None, None),
                                 processutils.ProcessExecutionError()]
        self.assertRaises(processutils.ProcessExecutionError,
                          disk_utils.destroy_disk_metadata,
                          self.dev,
                          self.node_uuid)
        mock_exec.assert_has_calls(expected_calls)

    def test_destroy_disk_metadata_wipefs_not_support_force(self, mock_exec):
        mock_exec.side_effect = iter(
            [processutils.ProcessExecutionError(description='--force'),
             (None, None),
             (None, None),
             ('', '')])

        expected_call = [mock.call('wipefs', '--force', '--all', 'fake-dev',
                                   run_as_root=True,
                                   use_standard_locale=True),
                         mock.call('wipefs', '--all', 'fake-dev',
                                   run_as_root=True,
                                   use_standard_locale=True)]
        disk_utils.destroy_disk_metadata(self.dev, self.node_uuid)
        mock_exec.assert_has_calls(expected_call)


@mock.patch.object(utils, 'execute', autospec=True)
class GetDeviceBlockSizeTestCase(base.IronicLibTestCase):

    def setUp(self):
        super(GetDeviceBlockSizeTestCase, self).setUp()
        self.dev = 'fake-dev'
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    def test_get_dev_block_size(self, mock_exec):
        mock_exec.return_value = ("64", "")
        expected_call = [mock.call('blockdev', '--getsz', self.dev,
                                   run_as_root=True, check_exit_code=[0])]
        disk_utils.get_dev_block_size(self.dev)
        mock_exec.assert_has_calls(expected_call)


@mock.patch.object(disk_utils, 'dd', autospec=True)
@mock.patch.object(disk_utils, 'qemu_img_info', autospec=True)
@mock.patch.object(disk_utils, 'convert_image', autospec=True)
class PopulateImageTestCase(base.IronicLibTestCase):

    def test_populate_raw_image(self, mock_cg, mock_qinfo, mock_dd):
        type(mock_qinfo.return_value).file_format = mock.PropertyMock(
            return_value='raw')
        disk_utils.populate_image('src', 'dst')
        mock_dd.assert_called_once_with('src', 'dst', conv_flags=None)
        self.assertFalse(mock_cg.called)

    def test_populate_raw_image_with_convert(self, mock_cg, mock_qinfo,
                                             mock_dd):
        type(mock_qinfo.return_value).file_format = mock.PropertyMock(
            return_value='raw')
        disk_utils.populate_image('src', 'dst', conv_flags='sparse')
        mock_dd.assert_called_once_with('src', 'dst', conv_flags='sparse')
        self.assertFalse(mock_cg.called)

    def test_populate_qcow2_image(self, mock_cg, mock_qinfo, mock_dd):
        type(mock_qinfo.return_value).file_format = mock.PropertyMock(
            return_value='qcow2')
        disk_utils.populate_image('src', 'dst')
        mock_cg.assert_called_once_with('src', 'dst', 'raw', True)
        self.assertFalse(mock_dd.called)


@mock.patch.object(utils, 'wait_for_disk_to_become_available', lambda *_: None)
@mock.patch.object(disk_utils, 'is_block_device', lambda d: True)
@mock.patch.object(disk_utils, 'block_uuid', lambda p: 'uuid')
@mock.patch.object(disk_utils, 'dd', lambda *_: None)
@mock.patch.object(disk_utils, 'convert_image', lambda *_: None)
@mock.patch.object(utils, 'mkfs', lambda fs, path, label=None: None)
# NOTE(dtantsur): destroy_disk_metadata resets file size, disabling it
@mock.patch.object(disk_utils, 'destroy_disk_metadata', lambda *_: None)
class RealFilePartitioningTestCase(base.IronicLibTestCase):
    """This test applies some real-world partitioning scenario to a file.

    This test covers the whole partitioning, mocking everything not possible
    on a file. That helps us assure, that we do all partitioning math properly
    and also conducts integration testing of DiskPartitioner.
    """

    # Allow calls to utils.execute() and related functions
    block_execute = False

    def setUp(self):
        super(RealFilePartitioningTestCase, self).setUp()
        # NOTE(dtantsur): no parted utility on gate-ironic-python26
        try:
            utils.execute('parted', '--version')
        except OSError as exc:
            self.skipTest('parted utility was not found: %s' % exc)
        self.file = tempfile.NamedTemporaryFile(delete=False)
        # NOTE(ifarkas): the file needs to be closed, so fuser won't report
        #                any usage
        self.file.close()
        # NOTE(dtantsur): 20 MiB file with zeros
        utils.execute('dd', 'if=/dev/zero', 'of=%s' % self.file.name,
                      'bs=1', 'count=0', 'seek=20MiB')

    @staticmethod
    def _run_without_root(func, *args, **kwargs):
        """Make sure root is not required when using utils.execute."""
        real_execute = utils.execute

        def fake_execute(*cmd, **kwargs):
            kwargs['run_as_root'] = False
            return real_execute(*cmd, **kwargs)

        with mock.patch.object(utils, 'execute', fake_execute):
            return func(*args, **kwargs)

    def test_different_sizes(self):
        # NOTE(dtantsur): Keep this list in order with expected partitioning
        fields = ['ephemeral_mb', 'swap_mb', 'root_mb']
        variants = ((0, 0, 12), (4, 2, 8), (0, 4, 10), (5, 0, 10))
        for variant in variants:
            kwargs = dict(zip(fields, variant))
            self._run_without_root(disk_utils.work_on_disk,
                                   self.file.name, ephemeral_format='ext4',
                                   node_uuid='', image_path='path', **kwargs)
            part_table = self._run_without_root(
                disk_utils.list_partitions, self.file.name)
            for part, expected_size in zip(part_table, filter(None, variant)):
                self.assertEqual(expected_size, part['size'],
                                 "comparison failed for %s" % list(variant))

    def test_whole_disk(self):
        # 6 MiB ephemeral + 3 MiB swap + 9 MiB root + 1 MiB for MBR
        # + 1 MiB MAGIC == 20 MiB whole disk
        # TODO(dtantsur): figure out why we need 'magic' 1 more MiB
        # and why the is different on Ubuntu and Fedora (see below)
        self._run_without_root(disk_utils.work_on_disk, self.file.name,
                               root_mb=9, ephemeral_mb=6, swap_mb=3,
                               ephemeral_format='ext4', node_uuid='',
                               image_path='path')
        part_table = self._run_without_root(
            disk_utils.list_partitions, self.file.name)
        sizes = [part['size'] for part in part_table]
        # NOTE(dtantsur): parted in Ubuntu 12.04 will occupy the last MiB,
        # parted in Fedora 20 won't - thus two possible variants for last part
        self.assertEqual([6, 3], sizes[:2],
                         "unexpected partitioning %s" % part_table)
        self.assertIn(sizes[2], (9, 10))


@mock.patch.object(shutil, 'copyfileobj', autospec=True)
@mock.patch.object(requests, 'get', autospec=True)
class GetConfigdriveTestCase(base.IronicLibTestCase):

    @mock.patch.object(gzip, 'GzipFile', autospec=True)
    def test_get_configdrive(self, mock_gzip, mock_requests, mock_copy):
        mock_requests.return_value = mock.MagicMock(content='Zm9vYmFy')
        tempdir = tempfile.mkdtemp()
        (size, path) = disk_utils._get_configdrive('http://1.2.3.4/cd',
                                                   'fake-node-uuid',
                                                   tempdir=tempdir)
        self.assertTrue(path.startswith(tempdir))
        mock_requests.assert_called_once_with('http://1.2.3.4/cd')
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)

    @mock.patch.object(gzip, 'GzipFile', autospec=True)
    def test_get_configdrive_base64_string(self, mock_gzip, mock_requests,
                                           mock_copy):
        disk_utils._get_configdrive('Zm9vYmFy', 'fake-node-uuid')
        self.assertFalse(mock_requests.called)
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)

    def test_get_configdrive_bad_url(self, mock_requests, mock_copy):
        mock_requests.side_effect = requests.exceptions.RequestException
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils._get_configdrive,
                          'http://1.2.3.4/cd', 'fake-node-uuid')
        self.assertFalse(mock_copy.called)

    @mock.patch.object(base64, 'decode_as_bytes', autospec=True)
    def test_get_configdrive_base64_error(self, mock_b64, mock_requests,
                                          mock_copy):
        mock_b64.side_effect = TypeError
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils._get_configdrive,
                          'malformed', 'fake-node-uuid')
        mock_b64.assert_called_once_with('malformed')
        self.assertFalse(mock_copy.called)

    @mock.patch.object(gzip, 'GzipFile', autospec=True)
    def test_get_configdrive_gzip_error(self, mock_gzip, mock_requests,
                                        mock_copy):
        mock_requests.return_value = mock.MagicMock(content='Zm9vYmFy')
        mock_copy.side_effect = IOError
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils._get_configdrive,
                          'http://1.2.3.4/cd', 'fake-node-uuid')
        mock_requests.assert_called_once_with('http://1.2.3.4/cd')
        mock_gzip.assert_called_once_with('configdrive', 'rb',
                                          fileobj=mock.ANY)
        mock_copy.assert_called_once_with(mock.ANY, mock.ANY)


@mock.patch('time.sleep', lambda sec: None)
class OtherFunctionTestCase(base.IronicLibTestCase):

    @mock.patch.object(os, 'stat', autospec=True)
    @mock.patch.object(stat, 'S_ISBLK', autospec=True)
    def test_is_block_device_works(self, mock_is_blk, mock_os):
        device = '/dev/disk/by-path/ip-1.2.3.4:5678-iscsi-iqn.fake-lun-9'
        mock_is_blk.return_value = True
        mock_os().st_mode = 10000
        self.assertTrue(disk_utils.is_block_device(device))
        mock_is_blk.assert_called_once_with(mock_os().st_mode)

    @mock.patch.object(os, 'stat', autospec=True)
    def test_is_block_device_raises(self, mock_os):
        device = '/dev/disk/by-path/ip-1.2.3.4:5678-iscsi-iqn.fake-lun-9'
        mock_os.side_effect = OSError
        self.assertRaises(exception.InstanceDeployFailure,
                          disk_utils.is_block_device, device)
        mock_os.assert_has_calls([mock.call(device)] * 3)

    @mock.patch.object(imageutils, 'QemuImgInfo', autospec=True)
    @mock.patch.object(os.path, 'exists', return_value=False, autospec=True)
    def test_qemu_img_info_path_doesnt_exist(self, path_exists_mock,
                                             qemu_img_info_mock):
        disk_utils.qemu_img_info('noimg')
        path_exists_mock.assert_called_once_with('noimg')
        qemu_img_info_mock.assert_called_once_with()

    @mock.patch.object(utils, 'execute', return_value=('out', 'err'),
                       autospec=True)
    @mock.patch.object(imageutils, 'QemuImgInfo', autospec=True)
    @mock.patch.object(os.path, 'exists', return_value=True, autospec=True)
    def test_qemu_img_info_path_exists(self, path_exists_mock,
                                       qemu_img_info_mock, execute_mock):
        disk_utils.qemu_img_info('img')
        path_exists_mock.assert_called_once_with('img')
        execute_mock.assert_called_once_with('env', 'LC_ALL=C', 'LANG=C',
                                             'qemu-img', 'info', 'img',
                                             prlimit=mock.ANY)
        qemu_img_info_mock.assert_called_once_with('out')

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_convert_image(self, execute_mock):
        disk_utils.convert_image('source', 'dest', 'out_format')
        execute_mock.assert_called_once_with('qemu-img', 'convert', '-O',
                                             'out_format', 'source', 'dest',
                                             run_as_root=False,
                                             prlimit=mock.ANY)

    @mock.patch.object(os.path, 'getsize', autospec=True)
    @mock.patch.object(disk_utils, 'qemu_img_info', autospec=True)
    def test_get_image_mb(self, mock_qinfo, mock_getsize):
        mb = 1024 * 1024

        mock_getsize.return_value = 0
        type(mock_qinfo.return_value).virtual_size = mock.PropertyMock(
            return_value=0)
        self.assertEqual(0, disk_utils.get_image_mb('x', False))
        self.assertEqual(0, disk_utils.get_image_mb('x', True))
        mock_getsize.return_value = 1
        type(mock_qinfo.return_value).virtual_size = mock.PropertyMock(
            return_value=1)
        self.assertEqual(1, disk_utils.get_image_mb('x', False))
        self.assertEqual(1, disk_utils.get_image_mb('x', True))
        mock_getsize.return_value = mb
        type(mock_qinfo.return_value).virtual_size = mock.PropertyMock(
            return_value=mb)
        self.assertEqual(1, disk_utils.get_image_mb('x', False))
        self.assertEqual(1, disk_utils.get_image_mb('x', True))
        mock_getsize.return_value = mb + 1
        type(mock_qinfo.return_value).virtual_size = mock.PropertyMock(
            return_value=mb + 1)
        self.assertEqual(2, disk_utils.get_image_mb('x', False))
        self.assertEqual(2, disk_utils.get_image_mb('x', True))

    def _test_count_mbr_partitions(self, output, mock_execute):
        mock_execute.return_value = (output, '')
        out = disk_utils.count_mbr_partitions('/dev/fake')
        mock_execute.assert_called_once_with('partprobe', '-d', '-s',
                                             '/dev/fake', run_as_root=True,
                                             use_standard_locale=True)
        return out

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_count_mbr_partitions(self, mock_execute):
        output = "/dev/fake: msdos partitions 1 2 3 <5 6>"
        pp, lp = self._test_count_mbr_partitions(output, mock_execute)
        self.assertEqual(3, pp)
        self.assertEqual(2, lp)

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_count_mbr_partitions_no_logical_partitions(self, mock_execute):
        output = "/dev/fake: msdos partitions 1 2"
        pp, lp = self._test_count_mbr_partitions(output, mock_execute)
        self.assertEqual(2, pp)
        self.assertEqual(0, lp)

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_count_mbr_partitions_wrong_partition_table(self, mock_execute):
        output = "/dev/fake: gpt partitions 1 2 3 4 5 6"
        mock_execute.return_value = (output, '')
        self.assertRaises(ValueError, disk_utils.count_mbr_partitions,
                          '/dev/fake')
        mock_execute.assert_called_once_with('partprobe', '-d', '-s',
                                             '/dev/fake', run_as_root=True,
                                             use_standard_locale=True)

    @mock.patch.object(utils, 'execute', autospec=True)
    def test_block_uuid_fallback_to_uuid(self, mock_execute):
        mock_execute.side_effect = [('', ''),
                                    ('value', '')]
        self.assertEqual('value',
                         disk_utils.block_uuid('/dev/fake'))
        execute_calls = [
            mock.call('blkid', '-s', 'UUID', '-o', 'value',
                      '/dev/fake', check_exit_code=[0],
                      run_as_root=True),
            mock.call('blkid', '-s', 'PARTUUID', '-o', 'value',
                      '/dev/fake', check_exit_code=[0],
                      run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)


@mock.patch.object(utils, 'execute', autospec=True)
class WholeDiskPartitionTestCases(base.IronicLibTestCase):

    def setUp(self):
        super(WholeDiskPartitionTestCases, self).setUp()
        self.dev = "/dev/fake"
        self.config_part_label = "config-2"
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    def test_get_partition_present(self, mock_execute):
        lsblk_output = 'NAME="fake12" LABEL="config-2"\n'
        part_result = '/dev/fake12'
        mock_execute.side_effect = [(None, ''), (lsblk_output, '')]
        result = disk_utils._get_labelled_partition(self.dev,
                                                    self.config_part_label,
                                                    self.node_uuid)
        self.assertEqual(part_result, result)
        execute_calls = [
            mock.call('partprobe', self.dev, run_as_root=True, attempts=10),
            mock.call('lsblk', '-Po', 'name,label', self.dev,
                      check_exit_code=[0, 1],
                      use_standard_locale=True, run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)

    def test_get_partition_present_uppercase(self, mock_execute):
        lsblk_output = 'NAME="fake12" LABEL="CONFIG-2"\n'
        part_result = '/dev/fake12'
        mock_execute.side_effect = [(None, ''), (lsblk_output, '')]
        result = disk_utils._get_labelled_partition(self.dev,
                                                    self.config_part_label,
                                                    self.node_uuid)
        self.assertEqual(part_result, result)
        execute_calls = [
            mock.call('partprobe', self.dev, run_as_root=True, attempts=10),
            mock.call('lsblk', '-Po', 'name,label', self.dev,
                      check_exit_code=[0, 1],
                      use_standard_locale=True, run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)

    def test_get_partition_absent(self, mock_execute):
        mock_execute.side_effect = [(None, ''),
                                    (None, '')]
        result = disk_utils._get_labelled_partition(self.dev,
                                                    self.config_part_label,
                                                    self.node_uuid)
        self.assertIsNone(result)
        execute_calls = [
            mock.call('partprobe', self.dev, run_as_root=True, attempts=10),
            mock.call('lsblk', '-Po', 'name,label', self.dev,
                      check_exit_code=[0, 1],
                      use_standard_locale=True, run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)

    def test_get_partition_DeployFail_exc(self, mock_execute):
        label = 'config-2'
        lsblk_output = ('NAME="fake12" LABEL="%s"\n'
                        'NAME="fake13" LABEL="%s"\n' %
                        (label, label))
        mock_execute.side_effect = [(None, ''), (lsblk_output, '')]
        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'fake .*fake12 .*fake13',
                               disk_utils._get_labelled_partition, self.dev,
                               self.config_part_label, self.node_uuid)
        execute_calls = [
            mock.call('partprobe', self.dev, run_as_root=True, attempts=10),
            mock.call('lsblk', '-Po', 'name,label', self.dev,
                      check_exit_code=[0, 1],
                      use_standard_locale=True, run_as_root=True)
        ]
        mock_execute.assert_has_calls(execute_calls)

    @mock.patch.object(disk_utils.LOG, 'error', autospec=True)
    def test_get_partition_exc(self, mock_log, mock_execute):
        mock_execute.side_effect = processutils.ProcessExecutionError
        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to retrieve partition labels',
                               disk_utils._get_labelled_partition, self.dev,
                               self.config_part_label, self.node_uuid)
        mock_execute.assert_called_once_with(
            'partprobe', self.dev, run_as_root=True, attempts=10)
        self.assertEqual(1, mock_log.call_count)

    def _test_is_disk_larger_than_max_size(self, mock_execute, blk_out):
        mock_execute.return_value = ('%s\n' % blk_out, '')
        result = disk_utils._is_disk_larger_than_max_size(self.dev,
                                                          self.node_uuid)
        mock_execute.assert_called_once_with('blockdev', '--getsize64',
                                             '/dev/fake', run_as_root=True,
                                             use_standard_locale=True)
        return result

    def test_is_disk_larger_than_max_size_false(self, mock_execute):
        blkid_out = "53687091200"
        ret = self._test_is_disk_larger_than_max_size(mock_execute,
                                                      blk_out=blkid_out)
        self.assertFalse(ret)

    def test_is_disk_larger_than_max_size_true(self, mock_execute):
        blkid_out = "4398046511104"
        ret = self._test_is_disk_larger_than_max_size(mock_execute,
                                                      blk_out=blkid_out)
        self.assertTrue(ret)

    @mock.patch.object(disk_utils.LOG, 'error', autospec=True)
    def test_is_disk_larger_than_max_size_exc(self, mock_log, mock_execute):
        mock_execute.side_effect = processutils.ProcessExecutionError
        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to get size of disk',
                               disk_utils._is_disk_larger_than_max_size,
                               self.dev, self.node_uuid)
        mock_execute.assert_called_once_with('blockdev', '--getsize64',
                                             '/dev/fake', run_as_root=True,
                                             use_standard_locale=True)
        self.assertEqual(1, mock_log.call_count)

    def test__is_disk_gpt_partitioned_true(self, mock_execute):
        blkid_output = 'gpt\n'
        mock_execute.return_value = (blkid_output, '')
        result = disk_utils._is_disk_gpt_partitioned('/dev/fake',
                                                     self.node_uuid)
        self.assertTrue(result)
        mock_execute.assert_called_once_with('blkid', '-p', '-o', 'value',
                                             '-s', 'PTTYPE', '/dev/fake',
                                             use_standard_locale=True,
                                             run_as_root=True)

    def test_is_disk_gpt_partitioned_false(self, mock_execute):
        blkid_output = 'dos\n'
        mock_execute.return_value = (blkid_output, '')
        result = disk_utils._is_disk_gpt_partitioned('/dev/fake',
                                                     self.node_uuid)
        self.assertFalse(result)
        mock_execute.assert_called_once_with('blkid', '-p', '-o', 'value',
                                             '-s', 'PTTYPE', '/dev/fake',
                                             use_standard_locale=True,
                                             run_as_root=True)

    @mock.patch.object(disk_utils.LOG, 'error', autospec=True)
    def test_is_disk_gpt_partitioned_exc(self, mock_log, mock_execute):
        mock_execute.side_effect = processutils.ProcessExecutionError
        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to retrieve partition table type',
                               disk_utils._is_disk_gpt_partitioned,
                               self.dev, self.node_uuid)
        mock_execute.assert_called_once_with('blkid', '-p', '-o', 'value',
                                             '-s', 'PTTYPE', '/dev/fake',
                                             use_standard_locale=True,
                                             run_as_root=True)
        self.assertEqual(1, mock_log.call_count)

    def test_fix_gpt_structs_fix_required(self, mock_execute):
        sgdisk_v_output = """
Problem: The secondary header's self-pointer indicates that it doesn't reside
at the end of the disk. If you've added a disk to a RAID array, use the 'e'
option on the experts' menu to adjust the secondary header's and partition
table's locations.

Identified 1 problems!
"""
        mock_execute.return_value = (sgdisk_v_output, '')
        execute_calls = [
            mock.call('sgdisk', '-v', '/dev/fake', run_as_root=True),
            mock.call('sgdisk', '-e', '/dev/fake', run_as_root=True)
        ]
        disk_utils._fix_gpt_structs('/dev/fake', self.node_uuid)
        mock_execute.assert_has_calls(execute_calls)

    def test_fix_gpt_structs_fix_not_required(self, mock_execute):
        mock_execute.return_value = ('', '')

        disk_utils._fix_gpt_structs('/dev/fake', self.node_uuid)
        mock_execute.assert_called_once_with('sgdisk', '-v', '/dev/fake',
                                             run_as_root=True)

    @mock.patch.object(disk_utils.LOG, 'error', autospec=True)
    def test_fix_gpt_structs_exc(self, mock_log, mock_execute):
        mock_execute.side_effect = processutils.ProcessExecutionError
        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to fix GPT data structures on disk',
                               disk_utils._fix_gpt_structs,
                               self.dev, self.node_uuid)
        mock_execute.assert_called_once_with('sgdisk', '-v', '/dev/fake',
                                             run_as_root=True)
        self.assertEqual(1, mock_log.call_count)


class WholeDiskConfigDriveTestCases(base.IronicLibTestCase):

    def setUp(self):
        super(WholeDiskConfigDriveTestCases, self).setUp()
        self.dev = "/dev/fake"
        self.config_part_label = "config-2"
        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"

    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_exists(self, mock_get_configdrive,
                                     mock_get_labelled_partition,
                                     mock_list_partitions, mock_is_disk_gpt,
                                     mock_fix_gpt, mock_fix_gpt_partition,
                                     mock_dd, mock_unlink, mock_execute):
        config_url = 'http://1.2.3.4/cd'
        configdrive_part = '/dev/fake-part1'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        mock_get_labelled_partition.return_value = configdrive_part
        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        disk_utils.create_config_drive_partition(self.node_uuid, self.dev,
                                                 config_url)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        mock_get_labelled_partition.assert_called_with(self.dev,
                                                       self.config_part_label,
                                                       self.node_uuid)
        self.assertFalse(mock_list_partitions.called)
        self.assertFalse(mock_execute.called)
        self.assertFalse(mock_is_disk_gpt.called)
        self.assertFalse(mock_fix_gpt.called)
        mock_dd.assert_called_with(configdrive_file, configdrive_part)
        mock_unlink.assert_called_with(configdrive_file)

    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_gpt(self, mock_get_configdrive,
                                  mock_get_labelled_partition,
                                  mock_list_partitions, mock_is_disk_gpt,
                                  mock_fix_gpt, mock_fix_gpt_partition,
                                  mock_dd, mock_unlink, mock_execute):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        initial_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        updated_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 4, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]

        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None

        mock_is_disk_gpt.return_value = True
        mock_list_partitions.side_effect = [initial_partitions,
                                            updated_partitions]
        expected_part = '/dev/fake4'
        disk_utils.create_config_drive_partition(self.node_uuid, self.dev,
                                                 config_url)
        mock_execute.assert_has_calls([
            mock.call('sgdisk', '-n', '0:-64MB:0', self.dev,
                      run_as_root=True),
            mock.call('sync'),
            mock.call('udevadm', 'settle'),
            mock.call('partprobe', self.dev, attempts=10, run_as_root=True),
            mock.call('sgdisk', '-v', self.dev, run_as_root=True),

            mock.call('udevadm', 'settle'),
            mock.call('test', '-e', expected_part, attempts=15,
                      check_exit_code=[0], delay_on_retry=True)
        ])

        self.assertEqual(2, mock_list_partitions.call_count)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        self.assertFalse(mock_fix_gpt.called)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_dd.assert_called_with(configdrive_file, expected_part)
        mock_unlink.assert_called_with(configdrive_file)

    @mock.patch.object(disk_utils, 'count_mbr_partitions', autospec=True)
    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(disk_utils.LOG, 'warning', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_larger_than_max_size',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def _test_create_partition_mbr(self, mock_get_configdrive,
                                   mock_get_labelled_partition,
                                   mock_list_partitions,
                                   mock_is_disk_gpt, mock_fix_gpt,
                                   mock_fix_gpt_partition,
                                   mock_disk_exceeds, mock_dd,
                                   mock_unlink, mock_log, mock_execute,
                                   mock_count, disk_size_exceeds_max=False,
                                   is_iscsi_device=False,
                                   is_nvme_device=False):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10
        mock_disk_exceeds.return_value = disk_size_exceeds_max

        initial_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        updated_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 4, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        mock_list_partitions.side_effect = [initial_partitions,
                                            updated_partitions]
        # 2 primary partitions, 0 logical partitions
        mock_count.return_value = (2, 0)
        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None
        mock_is_disk_gpt.return_value = False

        self.node_uuid = "12345678-1234-1234-1234-1234567890abcxyz"
        if is_iscsi_device:
            self.dev = ('/dev/iqn.2008-10.org.openstack:%s.fake' %
                        self.node_uuid)
            expected_part = '%s-part4' % self.dev
        elif is_nvme_device:
            self.dev = '/dev/nvmefake0'
            expected_part = '%sp4' % self.dev
        else:
            expected_part = '/dev/fake4'

        disk_utils.create_config_drive_partition(self.node_uuid, self.dev,
                                                 config_url)
        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        if disk_size_exceeds_max:
            self.assertEqual(1, mock_log.call_count)
            parted_call = mock.call('parted', '-a', 'optimal', '-s',
                                    '--', self.dev, 'mkpart',
                                    'primary', 'fat32', 2097087,
                                    2097151, run_as_root=True)
        else:
            self.assertEqual(0, mock_log.call_count)
            parted_call = mock.call('parted', '-a', 'optimal', '-s',
                                    '--', self.dev, 'mkpart',
                                    'primary', 'fat32', '-64MiB',
                                    '-0', run_as_root=True)
        mock_execute.assert_has_calls([
            parted_call,
            mock.call('sync'),
            mock.call('udevadm', 'settle'),
            mock.call('partprobe', self.dev, attempts=10, run_as_root=True),
            mock.call('sgdisk', '-v', self.dev, run_as_root=True),
            mock.call('udevadm', 'settle'),
            mock.call('test', '-e', expected_part, attempts=15,
                      check_exit_code=[0], delay_on_retry=True)
        ])
        self.assertEqual(2, mock_list_partitions.call_count)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_disk_exceeds.assert_called_with(self.dev, self.node_uuid)
        mock_dd.assert_called_with(configdrive_file, expected_part)
        mock_unlink.assert_called_with(configdrive_file)
        self.assertFalse(mock_fix_gpt.called)
        self.assertFalse(mock_fix_gpt.called)
        mock_count.assert_called_with(self.dev)

    def test__create_partition_mbr_disk_under_2TB(self):
        self._test_create_partition_mbr(disk_size_exceeds_max=False,
                                        is_iscsi_device=True,
                                        is_nvme_device=False)

    def test__create_partition_mbr_disk_under_2TB_nvme(self):
        self._test_create_partition_mbr(disk_size_exceeds_max=False,
                                        is_iscsi_device=False,
                                        is_nvme_device=True)

    def test__create_partition_mbr_disk_exceeds_2TB(self):
        self._test_create_partition_mbr(disk_size_exceeds_max=True,
                                        is_iscsi_device=False,
                                        is_nvme_device=False)

    def test__create_partition_mbr_disk_exceeds_2TB_nvme(self):
        self._test_create_partition_mbr(disk_size_exceeds_max=True,
                                        is_iscsi_device=False,
                                        is_nvme_device=True)

    @mock.patch.object(disk_utils, 'count_mbr_partitions', autospec=True)
    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_larger_than_max_size',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_part_create_fail(self, mock_get_configdrive,
                                               mock_get_labelled_partition,
                                               mock_list_partitions,
                                               mock_is_disk_gpt, mock_fix_gpt,
                                               mock_fix_gpt_partition,
                                               mock_disk_exceeds, mock_dd,
                                               mock_unlink, mock_execute,
                                               mock_count):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        initial_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        updated_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None
        mock_is_disk_gpt.return_value = False
        mock_disk_exceeds.return_value = False
        mock_list_partitions.side_effect = [initial_partitions,
                                            initial_partitions,
                                            updated_partitions]
        # 2 primary partitions, 0 logical partitions
        mock_count.return_value = (2, 0)

        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Disk partitioning failed on device',
                               disk_utils.create_config_drive_partition,
                               self.node_uuid, self.dev, config_url)

        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        mock_execute.assert_has_calls([
            mock.call('parted', '-a', 'optimal', '-s', '--',
                      self.dev, 'mkpart', 'primary',
                      'fat32', '-64MiB', '-0',
                      run_as_root=True),
            mock.call('sync'),
            mock.call('udevadm', 'settle'),
            mock.call('partprobe', self.dev, attempts=10, run_as_root=True),
            mock.call('sgdisk', '-v', self.dev, run_as_root=True),
        ])

        self.assertEqual(2, mock_list_partitions.call_count)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        mock_disk_exceeds.assert_called_with(self.dev, self.node_uuid)
        self.assertFalse(mock_fix_gpt.called)
        self.assertFalse(mock_dd.called)
        mock_unlink.assert_called_with(configdrive_file)
        mock_count.assert_called_once_with(self.dev)

    @mock.patch.object(disk_utils, 'count_mbr_partitions', autospec=True)
    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_larger_than_max_size',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_part_create_exc(self, mock_get_configdrive,
                                              mock_get_labelled_partition,
                                              mock_list_partitions,
                                              mock_is_disk_gpt, mock_fix_gpt,
                                              mock_fix_gpt_partition,
                                              mock_disk_exceeds, mock_dd,
                                              mock_unlink, mock_execute,
                                              mock_count):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        initial_partitions = [{'end': 49152, 'number': 1, 'start': 1,
                               'flags': 'boot', 'filesystem': 'ext4',
                               'size': 49151},
                              {'end': 51099, 'number': 3, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046},
                              {'end': 51099, 'number': 5, 'start': 49153,
                               'flags': '', 'filesystem': '', 'size': 2046}]
        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None
        mock_is_disk_gpt.return_value = False
        mock_disk_exceeds.return_value = False
        mock_list_partitions.side_effect = [initial_partitions,
                                            initial_partitions]
        # 2 primary partitions, 0 logical partitions
        mock_count.return_value = (2, 0)

        mock_execute.side_effect = processutils.ProcessExecutionError

        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to create config drive on disk',
                               disk_utils.create_config_drive_partition,
                               self.node_uuid, self.dev, config_url)

        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        mock_execute.assert_called_with('parted', '-a', 'optimal', '-s', '--',
                                        self.dev, 'mkpart', 'primary',
                                        'fat32', '-64MiB', '-0',
                                        run_as_root=True)
        self.assertEqual(1, mock_list_partitions.call_count)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        mock_disk_exceeds.assert_called_with(self.dev, self.node_uuid)
        self.assertFalse(mock_fix_gpt.called)
        self.assertFalse(mock_dd.called)
        mock_unlink.assert_called_with(configdrive_file)
        mock_count.assert_called_once_with(self.dev)

    @mock.patch.object(disk_utils, 'count_mbr_partitions', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'dd',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_fix_gpt_structs',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, 'list_partitions',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_num_parts_exceed(self, mock_get_configdrive,
                                               mock_get_labelled_partition,
                                               mock_list_partitions,
                                               mock_is_disk_gpt, mock_fix_gpt,
                                               mock_fix_gpt_partition,
                                               mock_dd, mock_unlink,
                                               mock_count):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        partitions = [{'end': 49152, 'number': 1, 'start': 1,
                       'flags': 'boot', 'filesystem': 'ext4',
                       'size': 49151},
                      {'end': 51099, 'number': 2, 'start': 49153,
                       'flags': '', 'filesystem': '', 'size': 2046},
                      {'end': 51099, 'number': 3, 'start': 49153,
                       'flags': '', 'filesystem': '', 'size': 2046},
                      {'end': 51099, 'number': 4, 'start': 49153,
                       'flags': '', 'filesystem': '', 'size': 2046}]
        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None
        mock_is_disk_gpt.return_value = False
        mock_list_partitions.side_effect = [partitions, partitions]
        # 4 primary partitions, 0 logical partitions
        mock_count.return_value = (4, 0)

        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Config drive cannot be created for node',
                               disk_utils.create_config_drive_partition,
                               self.node_uuid, self.dev, config_url)

        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        self.assertEqual(1, mock_list_partitions.call_count)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        self.assertFalse(mock_fix_gpt.called)
        self.assertFalse(mock_dd.called)
        mock_unlink.assert_called_with(configdrive_file)
        mock_count.assert_called_once_with(self.dev)

    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_conf_drive_sz_exceed(self, mock_get_configdrive,
                                                   mock_get_labelled_partition,
                                                   mock_unlink, mock_execute):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 65

        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None

        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Config drive size exceeds maximum limit',
                               disk_utils.create_config_drive_partition,
                               self.node_uuid, self.dev, config_url)

        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        mock_unlink.assert_called_with(configdrive_file)

    @mock.patch.object(disk_utils, 'count_mbr_partitions', autospec=True)
    @mock.patch.object(utils, 'execute', autospec=True)
    @mock.patch.object(utils, 'unlink_without_raise',
                       autospec=True)
    @mock.patch.object(disk_utils, 'fix_gpt_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_is_disk_gpt_partitioned',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_labelled_partition',
                       autospec=True)
    @mock.patch.object(disk_utils, '_get_configdrive',
                       autospec=True)
    def test_create_partition_conf_drive_error_counting(
            self, mock_get_configdrive, mock_get_labelled_partition,
            mock_is_disk_gpt, mock_fix_gpt_partition,
            mock_unlink, mock_execute, mock_count):
        config_url = 'http://1.2.3.4/cd'
        configdrive_file = '/tmp/xyz'
        configdrive_mb = 10

        mock_get_configdrive.return_value = (configdrive_mb, configdrive_file)
        mock_get_labelled_partition.return_value = None
        mock_is_disk_gpt.return_value = False
        mock_count.side_effect = ValueError('Booooom')

        self.assertRaisesRegex(exception.InstanceDeployFailure,
                               'Failed to check the number of primary ',
                               disk_utils.create_config_drive_partition,
                               self.node_uuid, self.dev, config_url)

        mock_get_configdrive.assert_called_with(config_url, self.node_uuid)
        mock_unlink.assert_called_with(configdrive_file)
        mock_fix_gpt_partition.assert_called_with(self.dev, self.node_uuid)
        mock_is_disk_gpt.assert_called_with(self.dev, self.node_uuid)
        mock_count.assert_called_once_with(self.dev)

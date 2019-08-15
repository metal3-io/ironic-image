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
import logging
import math
import os
import re
import shlex
import shutil
import stat
import tempfile
import time

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_serialization import base64
from oslo_utils import excutils
from oslo_utils import imageutils
from oslo_utils import units
import requests
import six

from ironic_lib.common.i18n import _
from ironic_lib import disk_partitioner
from ironic_lib import exception
from ironic_lib import utils


opts = [
    cfg.IntOpt('efi_system_partition_size',
               default=200,
               help='Size of EFI system partition in MiB when configuring '
                    'UEFI systems for local boot.'),
    cfg.IntOpt('bios_boot_partition_size',
               default=1,
               help='Size of BIOS Boot partition in MiB when configuring '
                    'GPT partitioned systems for local boot in BIOS.'),
    cfg.StrOpt('dd_block_size',
               default='1M',
               help='Block size to use when writing to the nodes disk.'),
    cfg.IntOpt('iscsi_verify_attempts',
               default=3,
               help='Maximum attempts to verify an iSCSI connection is '
                    'active, sleeping 1 second between attempts.'),
    cfg.IntOpt('partprobe_attempts',
               default=10,
               help='Maximum number of attempts to try to read the '
                    'partition.'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group='disk_utils')

LOG = logging.getLogger(__name__)

_PARTED_PRINT_RE = re.compile(r"^(\d+):([\d\.]+)MiB:"
                              "([\d\.]+)MiB:([\d\.]+)MiB:(\w*):(.*):(.*);")

CONFIGDRIVE_LABEL = "config-2"
MAX_CONFIG_DRIVE_SIZE_MB = 64

# Maximum disk size supported by MBR is 2TB (2 * 1024 * 1024 MB)
MAX_DISK_SIZE_MB_SUPPORTED_BY_MBR = 2097152

# Limit the memory address space to 1 GiB when running qemu-img
QEMU_IMG_LIMITS = processutils.ProcessLimits(address_space=1 * units.Gi)


def list_partitions(device):
    """Get partitions information from given device.

    :param device: The device path.
    :returns: list of dictionaries (one per partition) with keys:
              number, start, end, size (in MiB), filesystem, partition_name,
              flags
    """
    output = utils.execute(
        'parted', '-s', '-m', device, 'unit', 'MiB', 'print',
        use_standard_locale=True, run_as_root=True)[0]
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    lines = [line for line in output.split('\n') if line.strip()][2:]
    # Example of line: 1:1.00MiB:501MiB:500MiB:ext4::boot
    fields = ('number', 'start', 'end', 'size', 'filesystem', 'partition_name',
              'flags')
    result = []
    for line in lines:
        match = _PARTED_PRINT_RE.match(line)
        if match is None:
            LOG.warning("Partition information from parted for device "
                        "%(device)s does not match "
                        "expected format: %(line)s",
                        dict(device=device, line=line))
            continue
        # Cast int fields to ints (some are floats and we round them down)
        groups = [int(float(x)) if i < 4 else x
                  for i, x in enumerate(match.groups())]
        result.append(dict(zip(fields, groups)))
    return result


def count_mbr_partitions(device):
    """Count the number of primary and logical partitions on a MBR

    :param device: The device path.
    :returns: A tuple with the number of primary partitions and logical
              partitions.
    :raise: ValueError if the device does not have a valid MBR partition
            table.
    """
    # -d do not update the kernel table
    # -s print a summary of the partition table
    output, err = utils.execute('partprobe', '-d', '-s', device,
                                run_as_root=True, use_standard_locale=True)
    if 'msdos' not in output:
        raise ValueError('The device %s does not have a valid MBR '
                         'partition table' % device)
    # Sample output: /dev/vdb: msdos partitions 1 2 3 <5 6 7>
    # The partitions with number > 4 (and inside <>) are logical partitions
    output = output.replace('<', '').replace('>', '')
    partitions = [int(s) for s in output.split() if s.isdigit()]

    return(sum(i < 5 for i in partitions), sum(i > 4 for i in partitions))


def get_disk_identifier(dev):
    """Get the disk identifier from the disk being exposed by the ramdisk.

    This disk identifier is appended to the pxe config which will then be
    used by chain.c32 to detect the correct disk to chainload. This is helpful
    in deployments to nodes with multiple disks.

    http://www.syslinux.org/wiki/index.php/Comboot/chain.c32#mbr:

    :param dev: Path for the already populated disk device.
    :raises OSError: When the hexdump binary is unavailable.
    :returns: The Disk Identifier.
    """
    disk_identifier = utils.execute('hexdump', '-s', '440', '-n', '4',
                                    '-e', '''\"0x%08x\"''',
                                    dev,
                                    run_as_root=True,
                                    check_exit_code=[0],
                                    attempts=5,
                                    delay_on_retry=True)
    return disk_identifier[0]


def get_uefi_disk_identifier(dev):
    """Get the uuid from the disk being exposed by the ramdisk.

    This uuid is appended to the pxe config which will then be set as the root
    and load the bootx64.efi file using chainloader and boot the machine.
    This is helpful in deployments to nodes with multiple disks.

    https://wiki.gentoo.org/wiki/GRUB2/Chainloading

    :param dev: Path for the already populated disk device.
    :raises InstanceDeployFailure: Image is not UEFI bootable.
    :returns: The UUID of the partition.
    """
    partition_id = None
    try:
        report, _ = utils.execute('fdisk', '-l', dev, run_as_root=True)
    except processutils.ProcessExecutionError as e:
        msg = _('Failed to find the partition on the disk %s ') % e
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)
    for line in report.splitlines():
        if line.startswith(dev) and 'EFI System' in line:
            vals = line.split()
            partition_id = vals[0]
    try:
        lsblk_output, _ = utils.execute('lsblk', '-PbioUUID', partition_id,
                                        run_as_root=True)
        disk_identifier = lsblk_output.split("=")[1].strip()
        disk_identifier = disk_identifier.strip('"')
    except processutils.ProcessExecutionError as e:
        raise exception.InstanceDeployFailure("Image is not UEFI bootable. "
                                              "Error: %s " % e)
    return disk_identifier


def is_iscsi_device(dev, node_uuid):
    """check whether the device path belongs to an iscsi device. """

    iscsi_id = "iqn.2008-10.org.openstack:%s" % node_uuid
    return iscsi_id in dev


def is_last_char_digit(dev):
    """check whether device name ends with a digit"""
    if len(dev) >= 1:
        return dev[-1].isdigit()
    return False


def make_partitions(dev, root_mb, swap_mb, ephemeral_mb,
                    configdrive_mb, node_uuid, commit=True,
                    boot_option="netboot", boot_mode="bios",
                    disk_label=None, cpu_arch=""):
    """Partition the disk device.

    Create partitions for root, swap, ephemeral and configdrive on a
    disk device.

    :param dev: Path for the device to work on.
    :param root_mb: Size of the root partition in mebibytes (MiB).
    :param swap_mb: Size of the swap partition in mebibytes (MiB). If 0,
        no partition will be created.
    :param ephemeral_mb: Size of the ephemeral partition in mebibytes (MiB).
        If 0, no partition will be created.
    :param configdrive_mb: Size of the configdrive partition in
        mebibytes (MiB). If 0, no partition will be created.
    :param commit: True/False. Default for this setting is True. If False
        partitions will not be written to disk.
    :param boot_option: Can be "local" or "netboot". "netboot" by default.
    :param boot_mode: Can be "bios" or "uefi". "bios" by default.
    :param node_uuid: Node's uuid. Used for logging.
    :param disk_label: The disk label to be used when creating the
        partition table. Valid values are: "msdos", "gpt" or None; If None
        Ironic will figure it out according to the boot_mode parameter.
    :param cpu_arch: Architecture of the node the disk device belongs to.
        When using the default value of None, no architecture specific
        steps will be taken. This default should be used for x86_64. When
        set to ppc64*, architecture specific steps are taken for booting a
        partition image locally.
    :returns: A dictionary containing the partition type as Key and partition
        path as Value for the partitions created by this method.

    """
    LOG.debug("Starting to partition the disk device: %(dev)s "
              "for node %(node)s",
              {'dev': dev, 'node': node_uuid})
    # the actual device names in the baremetal are like /dev/sda, /dev/sdb etc.
    # While for the iSCSI device, the naming convention has a format which has
    # iqn also embedded in it.
    # When this function is called by ironic-conductor, the iSCSI device name
    # should be appended by "part%d". While on the baremetal, it should name
    # the device partitions as /dev/sda1 and not /dev/sda-part1.
    if is_iscsi_device(dev, node_uuid):
        part_template = dev + '-part%d'
    elif is_last_char_digit(dev):
        part_template = dev + 'p%d'
    else:
        part_template = dev + '%d'
    part_dict = {}

    if disk_label is None:
        disk_label = 'gpt' if boot_mode == 'uefi' else 'msdos'

    dp = disk_partitioner.DiskPartitioner(dev, disk_label=disk_label)

    # For uefi localboot, switch partition table to gpt and create the efi
    # system partition as the first partition.
    if boot_mode == "uefi" and boot_option == "local":
        part_num = dp.add_partition(CONF.disk_utils.efi_system_partition_size,
                                    fs_type='fat32',
                                    boot_flag='boot')
        part_dict['efi system partition'] = part_template % part_num

    if (boot_mode == "bios" and boot_option == "local" and disk_label == "gpt"
        and not cpu_arch.startswith('ppc64')):
        part_num = dp.add_partition(CONF.disk_utils.bios_boot_partition_size,
                                    boot_flag='bios_grub')
        part_dict['BIOS Boot partition'] = part_template % part_num

    # NOTE(mjturek): With ppc64* nodes, partition images are expected to have
    # a PrEP partition at the start of the disk. This is an 8 MiB partition
    # with the boot and prep flags set. The bootloader should be installed
    # here.
    if (cpu_arch.startswith("ppc64") and boot_mode == "bios" and
        boot_option == "local"):
        LOG.debug("Add PReP boot partition (8 MB) to device: "
                  "%(dev)s for node %(node)s",
                  {'dev': dev, 'node': node_uuid})
        boot_flag = 'boot' if disk_label == 'msdos' else None
        part_num = dp.add_partition(8, part_type='primary',
                                    boot_flag=boot_flag, extra_flags=['prep'])
        part_dict['PReP Boot partition'] = part_template % part_num
    if ephemeral_mb:
        LOG.debug("Add ephemeral partition (%(size)d MB) to device: %(dev)s "
                  "for node %(node)s",
                  {'dev': dev, 'size': ephemeral_mb, 'node': node_uuid})
        part_num = dp.add_partition(ephemeral_mb)
        part_dict['ephemeral'] = part_template % part_num
    if swap_mb:
        LOG.debug("Add Swap partition (%(size)d MB) to device: %(dev)s "
                  "for node %(node)s",
                  {'dev': dev, 'size': swap_mb, 'node': node_uuid})
        part_num = dp.add_partition(swap_mb, fs_type='linux-swap')
        part_dict['swap'] = part_template % part_num
    if configdrive_mb:
        LOG.debug("Add config drive partition (%(size)d MB) to device: "
                  "%(dev)s for node %(node)s",
                  {'dev': dev, 'size': configdrive_mb, 'node': node_uuid})
        part_num = dp.add_partition(configdrive_mb)
        part_dict['configdrive'] = part_template % part_num

    # NOTE(lucasagomes): Make the root partition the last partition. This
    # enables tools like cloud-init's growroot utility to expand the root
    # partition until the end of the disk.
    LOG.debug("Add root partition (%(size)d MB) to device: %(dev)s "
              "for node %(node)s",
              {'dev': dev, 'size': root_mb, 'node': node_uuid})

    boot_val = 'boot' if (not cpu_arch.startswith("ppc64")
                          and boot_mode == "bios"
                          and boot_option == "local"
                          and disk_label == "msdos") else None

    part_num = dp.add_partition(root_mb, boot_flag=boot_val)

    part_dict['root'] = part_template % part_num

    if commit:
        # write to the disk
        dp.commit()
    return part_dict


def is_block_device(dev):
    """Check whether a device is block or not."""
    attempts = CONF.disk_utils.iscsi_verify_attempts
    for attempt in range(attempts):
        try:
            s = os.stat(dev)
        except OSError as e:
            LOG.debug("Unable to stat device %(dev)s. Attempt %(attempt)d "
                      "out of %(total)d. Error: %(err)s",
                      {"dev": dev, "attempt": attempt + 1,
                       "total": attempts, "err": e})
            time.sleep(1)
        else:
            return stat.S_ISBLK(s.st_mode)
    msg = _("Unable to stat device %(dev)s after attempting to verify "
            "%(attempts)d times.") % {'dev': dev, 'attempts': attempts}
    LOG.error(msg)
    raise exception.InstanceDeployFailure(msg)


def dd(src, dst, conv_flags=None):
    """Execute dd from src to dst."""
    if conv_flags:
        extra_args = ['conv=%s' % conv_flags]
    else:
        extra_args = []

    utils.dd(src, dst, 'bs=%s' % CONF.disk_utils.dd_block_size, 'oflag=direct',
             *extra_args)


def qemu_img_info(path):
    """Return an object containing the parsed output from qemu-img info."""
    if not os.path.exists(path):
        return imageutils.QemuImgInfo()

    out, err = utils.execute('env', 'LC_ALL=C', 'LANG=C',
                             'qemu-img', 'info', path,
                             prlimit=QEMU_IMG_LIMITS)
    return imageutils.QemuImgInfo(out)


def convert_image(source, dest, out_format, run_as_root=False):
    """Convert image to other format."""
    cmd = ('qemu-img', 'convert', '-O', out_format, source, dest)
    utils.execute(*cmd, run_as_root=run_as_root, prlimit=QEMU_IMG_LIMITS)


def populate_image(src, dst, conv_flags=None):
    data = qemu_img_info(src)
    if data.file_format == 'raw':
        dd(src, dst, conv_flags=conv_flags)
    else:
        convert_image(src, dst, 'raw', True)


def block_uuid(dev):
    """Get UUID of a block device.

    Try to fetch the UUID, if that fails, try to fetch the PARTUUID.
    """
    out, _err = utils.execute('blkid', '-s', 'UUID', '-o', 'value', dev,
                              run_as_root=True, check_exit_code=[0])
    if not out:
        LOG.debug('Falling back to partition UUID as the block device UUID '
                  'was not found while examining %(device)s',
                  {'device': dev})
        out, _err = utils.execute('blkid', '-s', 'PARTUUID', '-o', 'value',
                                  dev, run_as_root=True, check_exit_code=[0])
    return out.strip()


def get_image_mb(image_path, virtual_size=True):
    """Get size of an image in Megabyte."""
    mb = 1024 * 1024
    if not virtual_size:
        image_byte = os.path.getsize(image_path)
    else:
        data = qemu_img_info(image_path)
        image_byte = data.virtual_size

    # round up size to MB
    image_mb = int((image_byte + mb - 1) / mb)
    return image_mb


def get_dev_block_size(dev):
    """Get the device size in 512 byte sectors."""
    block_sz, cmderr = utils.execute('blockdev', '--getsz', dev,
                                     run_as_root=True, check_exit_code=[0])
    return int(block_sz)


def destroy_disk_metadata(dev, node_uuid):
    """Destroy metadata structures on node's disk.

    Ensure that node's disk magic strings are wiped without zeroing the
    entire drive. To do this we use the wipefs tool from util-linux.

    :param dev: Path for the device to work on.
    :param node_uuid: Node's uuid. Used for logging.
    """
    # NOTE(NobodyCam): This is needed to work around bug:
    # https://bugs.launchpad.net/ironic/+bug/1317647
    LOG.debug("Start destroy disk metadata for node %(node)s.",
              {'node': node_uuid})
    try:
        utils.execute('wipefs', '--force', '--all', dev,
                      run_as_root=True,
                      use_standard_locale=True)
    except processutils.ProcessExecutionError as e:
        with excutils.save_and_reraise_exception() as ctxt:
            # NOTE(zhenguo): Check if --force option is supported for wipefs,
            # if not, we should try without it.
            if '--force' in str(e):
                ctxt.reraise = False
                utils.execute('wipefs', '--all', dev,
                              run_as_root=True,
                              use_standard_locale=True)

    utils.execute('sgdisk', '-Z', dev, run_as_root=True,
                  use_standard_locale=True)

    try:
        utils.wait_for_disk_to_become_available(dev)
    except exception.IronicException as e:
        raise exception.InstanceDeployFailure(
            _('Destroying metadata failed on device %(device)s. '
              'Error: %(error)s')
            % {'device': dev, 'error': e})

    LOG.info("Disk metadata on %(dev)s successfully destroyed for node "
             "%(node)s", {'dev': dev, 'node': node_uuid})


def _get_configdrive(configdrive, node_uuid, tempdir=None):
    """Get the information about size and location of the configdrive.

    :param configdrive: Base64 encoded Gzipped configdrive content or
        configdrive HTTP URL.
    :param node_uuid: Node's uuid. Used for logging.
    :param tempdir: temporary directory for the temporary configdrive file
    :raises: InstanceDeployFailure if it can't download or decode the
       config drive.
    :returns: A tuple with the size in MiB and path to the uncompressed
        configdrive file.

    """
    # Check if the configdrive option is a HTTP URL or the content directly
    is_url = utils.is_http_url(configdrive)
    if is_url:
        try:
            data = requests.get(configdrive).content
        except requests.exceptions.RequestException as e:
            raise exception.InstanceDeployFailure(
                _("Can't download the configdrive content for node %(node)s "
                  "from '%(url)s'. Reason: %(reason)s") %
                {'node': node_uuid, 'url': configdrive, 'reason': e})
    else:
        data = configdrive

    try:
        data = six.BytesIO(base64.decode_as_bytes(data))
    except TypeError:
        error_msg = (_('Config drive for node %s is not base64 encoded '
                       'or the content is malformed.') % node_uuid)
        if is_url:
            error_msg += _(' Downloaded from "%s".') % configdrive
        raise exception.InstanceDeployFailure(error_msg)

    configdrive_file = tempfile.NamedTemporaryFile(delete=False,
                                                   prefix='configdrive',
                                                   dir=tempdir)
    configdrive_mb = 0
    with gzip.GzipFile('configdrive', 'rb', fileobj=data) as gunzipped:
        try:
            shutil.copyfileobj(gunzipped, configdrive_file)
        except EnvironmentError as e:
            # Delete the created file
            utils.unlink_without_raise(configdrive_file.name)
            raise exception.InstanceDeployFailure(
                _('Encountered error while decompressing and writing '
                  'config drive for node %(node)s. Error: %(exc)s') %
                {'node': node_uuid, 'exc': e})
        else:
            # Get the file size and convert to MiB
            configdrive_file.seek(0, os.SEEK_END)
            bytes_ = configdrive_file.tell()
            configdrive_mb = int(math.ceil(float(bytes_) / units.Mi))
        finally:
            configdrive_file.close()

        return (configdrive_mb, configdrive_file.name)


def work_on_disk(dev, root_mb, swap_mb, ephemeral_mb, ephemeral_format,
                 image_path, node_uuid, preserve_ephemeral=False,
                 configdrive=None, boot_option="netboot", boot_mode="bios",
                 tempdir=None, disk_label=None, cpu_arch="", conv_flags=None):
    """Create partitions and copy an image to the root partition.

    :param dev: Path for the device to work on.
    :param root_mb: Size of the root partition in megabytes.
    :param swap_mb: Size of the swap partition in megabytes.
    :param ephemeral_mb: Size of the ephemeral partition in megabytes. If 0,
        no ephemeral partition will be created.
    :param ephemeral_format: The type of file system to format the ephemeral
        partition.
    :param image_path: Path for the instance's disk image. If ``None``,
        the root partition is prepared but not populated.
    :param node_uuid: node's uuid. Used for logging.
    :param preserve_ephemeral: If True, no filesystem is written to the
        ephemeral block device, preserving whatever content it had (if the
        partition table has not changed).
    :param configdrive: Optional. Base64 encoded Gzipped configdrive content
                        or configdrive HTTP URL.
    :param boot_option: Can be "local" or "netboot". "netboot" by default.
    :param boot_mode: Can be "bios" or "uefi". "bios" by default.
    :param tempdir: A temporary directory
    :param disk_label: The disk label to be used when creating the
        partition table. Valid values are: "msdos", "gpt" or None; If None
        Ironic will figure it out according to the boot_mode parameter.
    :param cpu_arch: Architecture of the node the disk device belongs to.
        When using the default value of None, no architecture specific
        steps will be taken. This default should be used for x86_64. When
        set to ppc64*, architecture specific steps are taken for booting a
        partition image locally.
    :param conv_flags: Flags that need to be sent to the dd command, to control
        the conversion of the original file when copying to the host. It can
        contain several options separated by commas.
    :returns: a dictionary containing the following keys:
        'root uuid': UUID of root partition
        'efi system partition uuid': UUID of the uefi system partition
        (if boot mode is uefi).
        `partitions`: mapping of partition types to their device paths.
        NOTE: If key exists but value is None, it means partition doesn't
        exist.
    """
    # the only way for preserve_ephemeral to be set to true is if we are
    # rebuilding an instance with --preserve_ephemeral.
    commit = not preserve_ephemeral
    # now if we are committing the changes to disk clean first.
    if commit:
        destroy_disk_metadata(dev, node_uuid)

    try:
        # If requested, get the configdrive file and determine the size
        # of the configdrive partition
        configdrive_mb = 0
        configdrive_file = None
        if configdrive:
            configdrive_mb, configdrive_file = _get_configdrive(
                configdrive, node_uuid, tempdir=tempdir)

        part_dict = make_partitions(dev, root_mb, swap_mb, ephemeral_mb,
                                    configdrive_mb, node_uuid,
                                    commit=commit,
                                    boot_option=boot_option,
                                    boot_mode=boot_mode,
                                    disk_label=disk_label,
                                    cpu_arch=cpu_arch)
        LOG.info("Successfully completed the disk device"
                 " %(dev)s partitioning for node %(node)s",
                 {'dev': dev, "node": node_uuid})

        ephemeral_part = part_dict.get('ephemeral')
        swap_part = part_dict.get('swap')
        configdrive_part = part_dict.get('configdrive')
        root_part = part_dict.get('root')

        if not is_block_device(root_part):
            raise exception.InstanceDeployFailure(
                _("Root device '%s' not found") % root_part)

        for part in ('swap', 'ephemeral', 'configdrive',
                     'efi system partition', 'PReP Boot partition'):
            part_device = part_dict.get(part)
            LOG.debug("Checking for %(part)s device (%(dev)s) on node "
                      "%(node)s.", {'part': part, 'dev': part_device,
                                    'node': node_uuid})
            if part_device and not is_block_device(part_device):
                raise exception.InstanceDeployFailure(
                    _("'%(partition)s' device '%(part_device)s' not found") %
                    {'partition': part, 'part_device': part_device})

        # If it's a uefi localboot, then we have created the efi system
        # partition.  Create a fat filesystem on it.
        if boot_mode == "uefi" and boot_option == "local":
            efi_system_part = part_dict.get('efi system partition')
            utils.mkfs(fs='vfat', path=efi_system_part, label='efi-part')

        if configdrive_part:
            # Copy the configdrive content to the configdrive partition
            dd(configdrive_file, configdrive_part, conv_flags=conv_flags)
            LOG.info("Configdrive for node %(node)s successfully copied "
                     "onto partition %(partition)s",
                     {'node': node_uuid, 'partition': configdrive_part})

    finally:
        # If the configdrive was requested make sure we delete the file
        # after copying the content to the partition
        if configdrive_file:
            utils.unlink_without_raise(configdrive_file)

    if image_path is not None:
        populate_image(image_path, root_part, conv_flags=conv_flags)
        LOG.info("Image for %(node)s successfully populated",
                 {'node': node_uuid})
    else:
        LOG.debug("Root partition for %s was created, but not populated",
                  node_uuid)

    if swap_part:
        utils.mkfs(fs='swap', path=swap_part, label='swap1')
        LOG.info("Swap partition %(swap)s successfully formatted "
                 "for node %(node)s",
                 {'swap': swap_part, 'node': node_uuid})

    if ephemeral_part and not preserve_ephemeral:
        utils.mkfs(fs=ephemeral_format, path=ephemeral_part,
                   label="ephemeral0")
        LOG.info("Ephemeral partition %(ephemeral)s successfully "
                 "formatted for node %(node)s",
                 {'ephemeral': ephemeral_part, 'node': node_uuid})

    uuids_to_return = {
        'root uuid': root_part,
        'efi system partition uuid': part_dict.get('efi system partition'),
    }

    if cpu_arch.startswith('ppc'):
        uuids_to_return[
            'PReP Boot partition uuid'
        ] = part_dict.get('PReP Boot partition')

    try:
        for part, part_dev in uuids_to_return.items():
            if part_dev:
                uuids_to_return[part] = block_uuid(part_dev)

    except processutils.ProcessExecutionError:
        with excutils.save_and_reraise_exception():
            LOG.error("Failed to detect %s", part)

    return dict(partitions=part_dict, **uuids_to_return)


def list_opts():
    """Entry point for oslo-config-generator."""
    return [('disk_utils', opts)]


def _is_disk_larger_than_max_size(device, node_uuid):
    """Check if total disk size exceeds 2TB msdos limit

    :param device: device path.
    :param node_uuid: node's uuid. Used for logging.
    :raises: InstanceDeployFailure, if any disk partitioning related
        commands fail.
    :returns: True if total disk size exceeds 2TB. Returns False otherwise.
    """
    try:
        disksize_bytes, err = utils.execute('blockdev', '--getsize64',
                                            device,
                                            use_standard_locale=True,
                                            run_as_root=True)
    except (processutils.UnknownArgumentError,
            processutils.ProcessExecutionError, OSError) as e:
        msg = (_('Failed to get size of disk %(disk)s for node %(node)s. '
                 'Error: %(error)s') %
               {'disk': device, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)

    disksize_mb = int(disksize_bytes.strip()) // 1024 // 1024

    return disksize_mb > MAX_DISK_SIZE_MB_SUPPORTED_BY_MBR


def _get_labelled_partition(device_path, label, node_uuid):
    """Check and return if partition with given label exists

    :param device_path: The device path.
    :param label: Partition label
    :param node_uuid: UUID of the Node. Used for logging.
    :raises: InstanceDeployFailure, if any disk partitioning related
        commands fail.
    :returns: block device file for partition if it exists; otherwise it
              returns None.
    """
    try:
        utils.execute('partprobe', device_path, run_as_root=True,
                      attempts=CONF.disk_utils.partprobe_attempts)

        # lsblk command
        output, err = utils.execute('lsblk', '-Po', 'name,label', device_path,
                                    check_exit_code=[0, 1],
                                    use_standard_locale=True, run_as_root=True)

    except (processutils.UnknownArgumentError,
            processutils.ProcessExecutionError, OSError) as e:
        msg = (_('Failed to retrieve partition labels on disk %(disk)s '
                 'for node %(node)s. Error: %(error)s') %
               {'disk': device_path, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)

    found_part = None
    if output:
        for device in output.split('\n'):
            dev = {key: value for key, value in (v.split('=', 1)
                   for v in shlex.split(device))}
            if not dev:
                continue
            if dev['LABEL'].upper() == label.upper():
                if found_part:
                    found_2 = '/dev/%(part)s' % {'part': dev['NAME'].strip()}
                    found = [found_part, found_2]
                    raise exception.InstanceDeployFailure(
                        _('More than one partition with label "%(label)s" '
                          'exists on device %(device)s for node %(node)s: '
                          '%(found)s.') %
                        {'label': label, 'device': device_path,
                         'node': node_uuid, 'found': ' and '.join(found)})
                found_part = '/dev/%(part)s' % {'part': dev['NAME'].strip()}

    return found_part


def _is_disk_gpt_partitioned(device, node_uuid):
    """Checks if the disk is GPT partitioned

    :param device: The device path.
    :param node_uuid: UUID of the Node. Used for logging.
    :raises: InstanceDeployFailure, if any disk partitioning related
        commands fail.
    :param node_uuid: UUID of the Node
    :returns: Boolean. Returns True if disk is GPT partitioned
    """
    try:
        stdout, _stderr = utils.execute(
            'blkid', '-p', '-o', 'value', '-s', 'PTTYPE', device,
            use_standard_locale=True, run_as_root=True)
    except (processutils.UnknownArgumentError,
            processutils.ProcessExecutionError, OSError) as e:
        msg = (_('Failed to retrieve partition table type for disk %(disk)s '
                 'for node %(node)s. Error: %(error)s') %
               {'disk': device, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)

    return (stdout.lower().strip() == 'gpt')


def _fix_gpt_structs(device, node_uuid):
    """Checks backup GPT data structures and moves them to end of the device

    :param device: The device path.
    :param node_uuid: UUID of the Node. Used for logging.
    :raises: InstanceDeployFailure, if any disk partitioning related
        commands fail.
    """
    try:
        output, _err = utils.execute('sgdisk', '-v', device, run_as_root=True)

        search_str = "it doesn't reside\nat the end of the disk"
        if search_str in output:
            utils.execute('sgdisk', '-e', device, run_as_root=True)
    except (processutils.UnknownArgumentError,
            processutils.ProcessExecutionError, OSError) as e:
        msg = (_('Failed to fix GPT data structures on disk %(disk)s '
                 'for node %(node)s. Error: %(error)s') %
               {'disk': device, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)


def fix_gpt_partition(device, node_uuid):
    """Fix GPT partition

    Fix GPT table information when image is written to a disk which
    has a bigger extend (e.g. 30GB image written on a 60Gb physical disk).

    :param device: The device path.
    :param node_uuid: UUID of the Node.
    :raises: InstanceDeployFailure if exception is caught.
    """
    try:
        disk_is_gpt_partitioned = _is_disk_gpt_partitioned(device, node_uuid)
        if disk_is_gpt_partitioned:
            _fix_gpt_structs(device, node_uuid)
    except Exception as e:
        msg = (_('Failed to fix GPT partition on disk %(disk)s '
                 'for node %(node)s. Error: %(error)s') %
               {'disk': device, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)


def create_config_drive_partition(node_uuid, device, configdrive):
    """Create a partition for config drive

    Checks if the device is GPT or MBR partitioned and creates config drive
    partition accordingly.

    :param node_uuid: UUID of the Node.
    :param device: The device path.
    :param configdrive: Base64 encoded Gzipped configdrive content or
        configdrive HTTP URL.
    :raises: InstanceDeployFailure if config drive size exceeds maximum limit
        or if it fails to create config drive.
    """
    confdrive_file = None
    try:
        config_drive_part = _get_labelled_partition(device,
                                                    CONFIGDRIVE_LABEL,
                                                    node_uuid)

        confdrive_mb, confdrive_file = _get_configdrive(configdrive,
                                                        node_uuid)
        if confdrive_mb > MAX_CONFIG_DRIVE_SIZE_MB:
                raise exception.InstanceDeployFailure(
                    _('Config drive size exceeds maximum limit of 64MiB. '
                      'Size of the given config drive is %(size)d MiB for '
                      'node %(node)s.')
                    % {'size': confdrive_mb, 'node': node_uuid})

        LOG.debug("Adding config drive partition %(size)d MiB to "
                  "device: %(dev)s for node %(node)s",
                  {'dev': device, 'size': confdrive_mb, 'node': node_uuid})

        fix_gpt_partition(device, node_uuid)
        if config_drive_part:
            LOG.debug("Configdrive for node %(node)s exists at "
                      "%(part)s",
                      {'node': node_uuid, 'part': config_drive_part})
        else:
            cur_parts = set(part['number'] for part in list_partitions(device))

            if _is_disk_gpt_partitioned(device, node_uuid):
                create_option = '0:-%dMB:0' % MAX_CONFIG_DRIVE_SIZE_MB
                utils.execute('sgdisk', '-n', create_option, device,
                              run_as_root=True)
            else:
                # Check if the disk has 4 partitions. The MBR based disk
                # cannot have more than 4 partitions.
                # TODO(stendulker): One can use logical partitions to create
                # a config drive if there are 3 primary partitions.
                # https://bugs.launchpad.net/ironic/+bug/1561283
                try:
                    pp_count, lp_count = count_mbr_partitions(device)
                except ValueError as e:
                    raise exception.InstanceDeployFailure(
                        _('Failed to check the number of primary partitions '
                          'present on %(dev)s for node %(node)s. Error: '
                          '%(error)s') % {'dev': device, 'node': node_uuid,
                                          'error': e})
                if pp_count > 3:
                    raise exception.InstanceDeployFailure(
                        _('Config drive cannot be created for node %(node)s. '
                          'Disk (%(dev)s) uses MBR partitioning and already '
                          'has %(parts)d primary partitions.')
                        % {'node': node_uuid, 'dev': device,
                           'parts': pp_count})

                # Check if disk size exceeds 2TB msdos limit
                startlimit = '-%dMiB' % MAX_CONFIG_DRIVE_SIZE_MB
                endlimit = '-0'
                if _is_disk_larger_than_max_size(device, node_uuid):
                    # Need to create a small partition at 2TB limit
                    LOG.warning("Disk size is larger than 2TB for "
                                "node %(node)s. Creating config drive "
                                "at the end of the disk %(disk)s.",
                                {'node': node_uuid, 'disk': device})
                    startlimit = (MAX_DISK_SIZE_MB_SUPPORTED_BY_MBR -
                                  MAX_CONFIG_DRIVE_SIZE_MB - 1)
                    endlimit = MAX_DISK_SIZE_MB_SUPPORTED_BY_MBR - 1

                utils.execute('parted', '-a', 'optimal', '-s', '--', device,
                              'mkpart', 'primary', 'fat32', startlimit,
                              endlimit, run_as_root=True)
            # Parted uses fsync to tell the kernel to sync file io
            # however on ramdisks in ramfs, this is an explicit no-op.
            # Explicitly call sync so when the the kernel attempts to read
            # the partition table from disk, it is less likely that the write
            # is still in buffer cache pending write to disk.
            LOG.debug('Explicitly calling sync to force buffer/cache flush.')
            utils.execute('sync')
            # Make sure any additions to the partitioning are reflected in the
            # kernel.
            LOG.debug('Waiting until udev event queue is empty')
            utils.execute('udevadm', 'settle')
            try:
                utils.execute('partprobe', device, run_as_root=True,
                              attempts=CONF.disk_utils.partprobe_attempts)
                # Also verify that the partitioning is correct now.
                utils.execute('sgdisk', '-v', device, run_as_root=True)
            except processutils.ProcessExecutionError as exc:
                LOG.warning('Failed to verify GPT partitioning after creating '
                            'the configdrive partition: %s', exc)

            upd_parts = set(part['number'] for part in list_partitions(device))
            new_part = set(upd_parts) - set(cur_parts)
            if len(new_part) != 1:
                raise exception.InstanceDeployFailure(
                    _('Disk partitioning failed on device %(device)s. '
                      'Unable to retrieve config drive partition information.')
                    % {'device': device})

            if is_iscsi_device(device, node_uuid):
                config_drive_part = '%s-part%s' % (device, new_part.pop())
            elif is_last_char_digit(device):
                config_drive_part = '%sp%s' % (device, new_part.pop())
            else:
                config_drive_part = '%s%s' % (device, new_part.pop())

            LOG.debug('Waiting until udev event queue is empty')
            utils.execute('udevadm', 'settle')

            # NOTE(vsaienko): check that devise actually exists,
            # it is not handled by udevadm when using ISCSI, for more info see:
            # https://bugs.launchpad.net/ironic/+bug/1673731
            # Do not use 'udevadm settle --exit-if-exist' here
            LOG.debug('Waiting for the config drive partition %(part)s '
                      'on node %(node)s to be ready for writing.',
                      {'part': config_drive_part, 'node': node_uuid})
            utils.execute('test', '-e', config_drive_part,
                          check_exit_code=[0], attempts=15,
                          delay_on_retry=True)

        dd(confdrive_file, config_drive_part)
        LOG.info("Configdrive for node %(node)s successfully "
                 "copied onto partition %(part)s",
                 {'node': node_uuid, 'part': config_drive_part})

    except (processutils.UnknownArgumentError,
            processutils.ProcessExecutionError, OSError) as e:
        msg = (_('Failed to create config drive on disk %(disk)s '
                 'for node %(node)s. Error: %(error)s') %
               {'disk': device, 'node': node_uuid, 'error': e})
        LOG.error(msg)
        raise exception.InstanceDeployFailure(msg)
    finally:
        # If the configdrive was requested make sure we delete the file
        # after copying the content to the partition
        if confdrive_file:
            utils.unlink_without_raise(confdrive_file)

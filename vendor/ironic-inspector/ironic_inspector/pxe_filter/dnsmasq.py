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

# NOTE(milan) the filter design relies on the hostdir[1] being in exclusive
# inspector control. The hostdir should be considered a private cache directory
# of inspector that dnsmasq has read access to and polls updates from, through
# the inotify facility.
#
# [1] see the --dhcp-hostsdir option description in
#     http://www.thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html


try:
    import errno
except ImportError:
    import os.errno as errno
import fcntl
import os
import time

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import node_cache
from ironic_inspector.pxe_filter import base as pxe_filter

CONF = cfg.CONF
LOG = log.getLogger(__name__)

_EXCLUSIVE_WRITE_ATTEMPTS = 10
_EXCLUSIVE_WRITE_ATTEMPTS_DELAY = 0.01

_ROOTWRAP_COMMAND = 'sudo ironic-inspector-rootwrap {rootwrap_config!s}'
_MACBL_LEN = len('ff:ff:ff:ff:ff:ff,ignore\n')
_MACWL_LEN = len('ff:ff:ff:ff:ff:ff\n')
_UNKNOWN_HOSTS_FILE = 'unknown_hosts_filter'
_BLACKLIST_UNKNOWN_HOSTS = '*:*:*:*:*:*,ignore\n'
_WHITELIST_UNKNOWN_HOSTS = '*:*:*:*:*:*\n'


def _should_enable_unknown_hosts():
    """Check whether we should enable DHCP for unknown hosts

    We blacklist unknown hosts unless one or more nodes are on introspection
    and node_not_found_hook is not set.
    """
    return (node_cache.introspection_active() or
            CONF.processing.node_not_found_hook is not None)


class DnsmasqFilter(pxe_filter.BaseFilter):
    """The dnsmasq PXE filter driver.

    A pxe filter driver implementation that controls access to dnsmasq
    through amending its configuration.
    """

    def reset(self):
        """Stop dnsmasq and upcall reset."""
        _execute(CONF.dnsmasq_pxe_filter.dnsmasq_stop_command,
                 ignore_errors=True)
        super(DnsmasqFilter, self).reset()

    def _sync(self, ironic):
        """Sync the inspector, ironic and dnsmasq state. Locked.

        :raises: IOError, OSError.
        :returns: None.
        """
        LOG.debug('Syncing the driver')
        timestamp_start = timeutils.utcnow()

        # active_macs are the MACs for which introspection is active
        active_macs = node_cache.active_macs()
        # ironic_macs are all the MACs know to ironic (all ironic ports)
        ironic_macs = set(port.address for port in
                          ir_utils.call_with_retries(ironic.port.list, limit=0,
                                                     fields=['address']))
        blacklist, whitelist = _get_black_white_lists()
        # removedlist are the MACs that are in either blacklist or whitelist,
        # but not kept in ironic (ironic_macs) any more
        removedlist = blacklist.union(whitelist).difference(ironic_macs)

        # Whitelist active MACs that are not already whitelisted
        for mac in active_macs.difference(whitelist):
            _whitelist_mac(mac)
        # Blacklist any ironic MACs that is not active for introspection unless
        # it is already blacklisted
        for mac in ironic_macs.difference(blacklist.union(active_macs)):
            _blacklist_mac(mac)

        # Whitelist or Blacklist unknown hosts and MACs not kept in ironic
        # NOTE(hjensas): Treat unknown hosts and MACs not kept in ironic the
        # same. Neither should boot the inspection image unless introspection
        # is active. Deleted MACs must be whitelisted when introspection is
        # active in case the host is re-enrolled.
        _configure_unknown_hosts()
        _configure_removedlist(removedlist)

        timestamp_end = timeutils.utcnow()
        LOG.debug('The dnsmasq PXE filter was synchronized (took %s)',
                  timestamp_end - timestamp_start)

    @pxe_filter.locked_driver_event(pxe_filter.Events.sync)
    def sync(self, ironic):
        """Sync dnsmasq configuration with current Ironic&Inspector state.

        Polls all ironic ports. Those being inspected, the active ones, are
        whitelisted while the rest are blacklisted in the dnsmasq
        configuration.

        :param ironic: an ironic client instance.
        :raises: OSError, IOError.
        :returns: None.
        """
        self._sync(ironic)

    @pxe_filter.locked_driver_event(pxe_filter.Events.initialize)
    def init_filter(self):
        """Performs an initial sync with ironic and starts dnsmasq.

        The initial _sync() call reduces the chances dnsmasq might lose
        some inotify blacklist events by prefetching the blacklist before
        the dnsmasq is started.

        :raises: OSError, IOError.
        :returns: None.
        """
        _purge_dhcp_hostsdir()
        ironic = ir_utils.get_client()
        self._sync(ironic)
        _execute(CONF.dnsmasq_pxe_filter.dnsmasq_start_command)
        LOG.info('The dnsmasq PXE filter was initialized')


def _purge_dhcp_hostsdir():
    """Remove all the DHCP hosts files.

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid.
             IOError in case of non-writable file or a record not being a file.
    :returns: None.
    """
    dhcp_hostsdir = CONF.dnsmasq_pxe_filter.dhcp_hostsdir
    if not CONF.dnsmasq_pxe_filter.purge_dhcp_hostsdir:
        LOG.debug('Not purging %s; disabled in configuration.', dhcp_hostsdir)
        return

    LOG.debug('Purging %s', dhcp_hostsdir)
    for mac in os.listdir(dhcp_hostsdir):
        path = os.path.join(dhcp_hostsdir, mac)
        # NOTE(milan) relying on a failure here aborting the init_filter() call
        os.remove(path)
        LOG.debug('Removed %s', path)


def _get_black_white_lists():
    """Get addresses currently blacklisted in dnsmasq.

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid.
    :returns: a set of MACs currently blacklisted in dnsmasq.
    """
    hostsdir = CONF.dnsmasq_pxe_filter.dhcp_hostsdir
    # whitelisted MACs lack the ,ignore directive
    blacklist = set()
    whitelist = set()
    for mac in os.listdir(hostsdir):
        if os.stat(os.path.join(hostsdir, mac)).st_size == _MACBL_LEN:
            blacklist.add(mac)
        if os.stat(os.path.join(hostsdir, mac)).st_size == _MACWL_LEN:
            whitelist.add(mac)

    return blacklist, whitelist


def _exclusive_write_or_pass(path, buf):
    """Write exclusively or pass if path locked.

    The intention is to be able to run multiple instances of the filter on the
    same node in multiple inspector processes.

    :param path: where to write to
    :param buf: the content to write
    :raises: FileNotFoundError, IOError
    :returns: True if the write was successful.
    """
    # NOTE(milan) line-buffering enforced to ensure dnsmasq record update
    # through inotify, which reacts on f.close()
    attempts = _EXCLUSIVE_WRITE_ATTEMPTS
    with open(path, 'w', 1) as f:
        while attempts:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                f.write(buf)
                # Go ahead and flush the data now instead of waiting until
                # after the automatic flush with the file close after the
                # file lock is released.
                f.flush()
                return True
            except IOError as e:
                if e.errno == errno.EWOULDBLOCK:
                    LOG.debug('%s locked; will try again (later)', path)
                    attempts -= 1
                    time.sleep(_EXCLUSIVE_WRITE_ATTEMPTS_DELAY)
                    continue
                raise
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    LOG.debug('Failed to write the exclusively-locked path: %(path)s for '
              '%(attempts)s times', {'attempts': _EXCLUSIVE_WRITE_ATTEMPTS,
                                     'path': path})
    return False


def _configure_removedlist(macs):
    """Manages a dhcp_hostsdir ignore/not-ignore record for removed macs

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid,
    :returns: None.
    """

    hostsdir = CONF.dnsmasq_pxe_filter.dhcp_hostsdir

    if _should_enable_unknown_hosts():
        for mac in macs:
            if os.stat(os.path.join(hostsdir, mac)).st_size != _MACWL_LEN:
                _whitelist_mac(mac)
    else:
        for mac in macs:
            if os.stat(os.path.join(hostsdir, mac)).st_size != _MACBL_LEN:
                _blacklist_mac(mac)


def _configure_unknown_hosts():
    """Manages a dhcp_hostsdir ignore/not-ignore record for unknown macs.

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid,
             IOError in case the dhcp host unknown file isn't writable.
    :returns: None.
    """
    path = os.path.join(CONF.dnsmasq_pxe_filter.dhcp_hostsdir,
                        _UNKNOWN_HOSTS_FILE)

    if _should_enable_unknown_hosts():
        wildcard_filter = _WHITELIST_UNKNOWN_HOSTS
        log_wildcard_filter = 'whitelist'
    else:
        wildcard_filter = _BLACKLIST_UNKNOWN_HOSTS
        log_wildcard_filter = 'blacklist'

    # Don't update if unknown hosts are already black/white-listed
    try:
        if os.stat(path).st_size == len(wildcard_filter):
            return
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

    if _exclusive_write_or_pass(path, '%s' % wildcard_filter):
        LOG.debug('A %s record for all unknown hosts using wildcard mac '
                  'created', log_wildcard_filter)
    else:
        LOG.warning('Failed to %s unknown hosts using wildcard mac; '
                    'retrying next periodic sync time', log_wildcard_filter)


def _blacklist_mac(mac):
    """Creates a dhcp_hostsdir ignore record for the MAC.

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid,
             IOError in case the dhcp host MAC file isn't writable.
    :returns: None.
    """
    path = os.path.join(CONF.dnsmasq_pxe_filter.dhcp_hostsdir, mac)
    if _exclusive_write_or_pass(path, '%s,ignore\n' % mac):
        LOG.debug('Blacklisted %s', mac)
    else:
        LOG.warning('Failed to blacklist %s; retrying next periodic sync '
                    'time', mac)


def _whitelist_mac(mac):
    """Un-ignores the dhcp_hostsdir record for the MAC.

    :raises: FileNotFoundError in case the dhcp_hostsdir is invalid,
             IOError in case the dhcp host MAC file isn't writable.
    :returns: None.
    """
    path = os.path.join(CONF.dnsmasq_pxe_filter.dhcp_hostsdir, mac)
    # remove the ,ignore directive
    if _exclusive_write_or_pass(path, '%s\n' % mac):
        LOG.debug('Whitelisted %s', mac)
    else:
        LOG.warning('Failed to whitelist %s; retrying next periodic sync '
                    'time', mac)


def _execute(cmd=None, ignore_errors=False):
    # e.g: '/bin/kill $(cat /var/run/dnsmasq.pid)'
    if not cmd:
        return

    helper = _ROOTWRAP_COMMAND.format(rootwrap_config=CONF.rootwrap_config)
    processutils.execute(cmd, run_as_root=True, root_helper=helper, shell=True,
                         check_exit_code=not ignore_errors)

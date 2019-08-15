Troubleshooting
---------------

Errors when starting introspection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* *Invalid provision state "available"*

  In Kilo release with *python-ironicclient* 0.5.0 or newer Ironic defaults to
  reporting provision state ``AVAILABLE`` for newly enrolled nodes.
  **ironic-inspector** will refuse to conduct introspection in this state, as
  such nodes are supposed to be used by Nova for scheduling. See :ref:`node
  states <node_states>` for instructions on how to put nodes into the correct
  state.

Introspection times out
~~~~~~~~~~~~~~~~~~~~~~~

There may be 3 reasons why introspection can time out after some time
(defaulting to 60 minutes, altered by ``timeout`` configuration option):

#. Fatal failure in processing chain before node was found in the local cache.
   See `Troubleshooting data processing`_ for the hints.

#. Failure to load the ramdisk on the target node. See `Troubleshooting
   PXE boot`_ for the hints.

#. Failure during ramdisk run. See `Troubleshooting ramdisk run`_ for the
   hints.

Troubleshooting data processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In this case **ironic-inspector** logs should give a good idea what went wrong.
E.g. for RDO or Fedora the following command will output the full log::

    sudo journalctl -u openstack-ironic-inspector

(use ``openstack-ironic-discoverd`` for version < 2.0.0).

.. note::
    Service name and specific command might be different for other Linux
    distributions (and for old version of **ironic-inspector**).

If ``ramdisk_error`` plugin is enabled and ``ramdisk_logs_dir`` configuration
option is set, **ironic-inspector** will store logs received from the ramdisk
to the ``ramdisk_logs_dir`` directory. This depends, however, on the ramdisk
implementation.

Troubleshooting PXE boot
^^^^^^^^^^^^^^^^^^^^^^^^

PXE booting most often becomes a problem for bare metal environments with
several physical networks. If the hardware vendor provides a remote console
(e.g. iDRAC for DELL), use it to connect to the machine and see what is going
on. You may need to restart introspection.

Another source of information is DHCP and TFTP server logs. Their location
depends on how the servers were installed and run. For RDO or Fedora use::

    $ sudo journalctl -u openstack-ironic-inspector-dnsmasq

(use ``openstack-ironic-discoverd-dnsmasq`` for version < 2.0.0).

The last resort is ``tcpdump`` utility. Use something like
::

    $ sudo tcpdump -i any port 67 or port 68 or port 69

to watch both DHCP and TFTP traffic going through your machine. Replace
``any`` with a specific network interface to check that DHCP and TFTP
requests really reach it.

If you see node not attempting PXE boot or attempting PXE boot on the wrong
network, reboot the machine into BIOS settings and make sure that only one
relevant NIC is allowed to PXE boot.

If you see node attempting PXE boot using the correct NIC but failing, make
sure that:

#. network switches configuration does not prevent PXE boot requests from
   propagating,

#. there is no additional firewall rules preventing access to port 67 on the
   machine where *ironic-inspector* and its DHCP server are installed.

If you see node receiving DHCP address and then failing to get kernel and/or
ramdisk or to boot them, make sure that:

#. TFTP server is running and accessible (use ``tftp`` utility to verify),

#. no firewall rules prevent access to TFTP port,

#. SELinux is configured properly to allow external TFTP access,

   If SELinux is neither permissive nor disabled,
   you should config ``tftp_home_dir`` in SELinux by executing the command
   ::

    $ sudo setsebool -P tftp_home_dir 1

   See `the man page`_ for more details.

   .. _the man page: https://www.systutorials.com/docs/linux/man/8-tftpd_selinux/

#. DHCP server is correctly set to point to the TFTP server,

#. ``pxelinux.cfg/default`` within TFTP root contains correct reference to the
   kernel and ramdisk.

.. note::
    If using iPXE instead of PXE, check the HTTP server logs and the iPXE
    configuration instead.

Troubleshooting ramdisk run
^^^^^^^^^^^^^^^^^^^^^^^^^^^

First, check if the ramdisk logs were stored locally as described in the
`Troubleshooting data processing`_ section. If not, ensure that the ramdisk
actually booted as described in the `Troubleshooting PXE boot`_ section.

Finally, you can try connecting to the IPA ramdisk. If you have any remote
console access to the machine, you can check the logs as they appear on the
screen. Otherwise, you can rebuild the IPA image with your SSH key to be able
to log into it. Use the `dynamic-login`_ or `devuser`_ element for a DIB-based
build or put an authorized_keys file in ``/usr/share/oem/`` for a CoreOS-based
one.

.. _devuser: https://docs.openstack.org/diskimage-builder/latest/elements/devuser/README.html
.. _dynamic-login: https://docs.openstack.org/diskimage-builder/latest/elements/dynamic-login/README.html

Troubleshooting DNS issues on Ubuntu
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _ubuntu-dns:

Ubuntu uses local DNS caching, so tries localhost for DNS results first
before calling out to an external DNS server. When DNSmasq is installed and
configured for use with ironic-inspector, it can cause problems by interfering
with the local DNS cache. To fix this issue ensure that ``/etc/resolve.conf``
points to your external DNS servers and not to ``127.0.0.1``.

On Ubuntu 14.04 this can be done by editing your
``/etc/resolvconf/resolv.conf.d/head`` and adding your nameservers there.
This will ensure they will come up first when ``/etc/resolv.conf``
is regenerated.

Running Inspector in a VirtualBox environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default VirtualBox does not expose a DMI table to the guest. This prevents
ironic-inspector from being able to discover the properties of the a node. In
order to run ironic-inspector on a VirtualBox guest the host must be configured
to expose DMI data inside the guest. To do this run the following command on
the VirtualBox host::

    VBoxManage setextradata {NodeName} "VBoxInternal/Devices/pcbios/0/Config/DmiExposeMemoryTable" 1

.. note::
    Replace `{NodeName}` with the name of the guest you wish to expose the DMI
    table on. This command will need to be run once per host to enable this
    functionality.

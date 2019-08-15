.. _dnsmasq_pxe_filter:

**dnsmasq** PXE filter
======================

An inspection PXE DHCP stack is often implemented by the **dnsmasq** service.
The **dnsmasq** PXE filter implementation relies on directly configuring the
**dnsmasq** DHCP service to provide a caching PXE traffic filter of node MAC
addresses.

How it works
------------

The filter works by populating the **dnsmasq** DHCP hosts directory with a
configuration file per MAC address. Each file is either enabling or disabling,
thru the ``ignore`` directive, the DHCP service for a particular MAC address::

    $ cat /etc/dnsmasq.d/de-ad-be-ef-de-ad
    de:ad:be:ef:de:ad,ignore
    $

The filename is used to keep track of all MAC addresses in the cache, avoiding
file parsing. The content of the file determines the MAC address access policy.

Thanks to the ``inotify`` facility, **dnsmasq** is notified once a new file is
*created* or an existing file is *modified* in the DHCP hosts directory. Thus,
to white-list a MAC address, the filter removes the ``ignore`` directive::

    $ cat /etc/dnsmasq.d/de-ad-be-ef-de-ad
    de:ad:be:ef:de:ad
    $

The hosts directory content establishes a *cached* MAC addresses filter that is
kept synchronized with the **ironic** port list.

.. note::

  The **dnsmasq** inotify facility implementation doesn't react to a file being
  removed or truncated.

Configuration
-------------

The ``inotify`` facility was introduced_ to **dnsmasq** in the version `2.73`.
This filter driver has been checked by **ironic-inspector** CI with
**dnsmasq** versions `>=2.76`.

.. _introduced: http://www.thekelleys.org.uk/dnsmasq/CHANGELOG

To enable the **dnsmasq** PXE filter, update the PXE filter driver name in the
**ironic-inspector** configuration file::

    [pxe_filter]
    driver = dnsmasq

The DHCP hosts directory can be specified to override the default
``/var/lib/ironic-inspector/dhcp-hostsdir``::

    [dnsmasq_pxe_filter]
    dhcp_hostsdir = /etc/ironic-inspector/dhcp-hostsdir

The filter design relies on the hosts directory being in exclusive
**ironic-inspector** control. The hosts directory should be considered a
*private cache* directory of **ionic-inspector** that **dnsmasq** polls
configuration updates from, through the ``inotify`` facility. The directory
has to be writable by **ironic-inspector** and readable by **dnsmasq**.

It is also possible to override the default (empty) **dnsmasq** start and stop
commands to, for instance, directly control the **dnsmasq** service::

    [dnsmasq_pxe_filter]
    dnsmasq_start_command = dnsmasq --conf-file /etc/ironic-inspector/dnsmasq.conf
    dnsmasq_stop_command = kill $(cat /var/run/dnsmasq.pid)

.. note::

  The commands support shell expansion. The default empty start command means
  the **dnsmasq** service won't be started upon the filter initialization.
  Conversely, the default empty stop command means the service won't be
  stopped upon an (error) exit.


.. note::

  These commands are executed through the rootwrap_ facility, so overriding
  may require a filter file to be created in the ``rootwrap.d`` directory. A
  sample configuration to use with the **systemctl** facility might be:

  .. code-block:: console

    sudo cat > /etc/ironic-inspector/rootwrap.d/ironic-inspector-dnsmasq-systemctl.filters <<EOF
    [Filters]
    # ironic_inspector/pxe_filter/dnsmasq.py
    systemctl: CommandFilter, systemctl, root, restart, dnsmasq
    systemctl: CommandFilter, systemctl, root, stop, dnsmasq
    EOF

  .. _rootwrap: https://docs.openstack.org/oslo.rootwrap/latest/

Caveats
-------

The initial synchronization will put some load on the **dnsmasq** service
starting based on the amount of ports **ironic** keeps. The start-up can take
up to a minute of full CPU load for huge amounts of MACs (tens of thousands).
Subsequent filter synchronizations will only cause the **dnsmasq** to parse
the modified files. Typically those are the bare metal nodes being added or
phased out from the compute service, meaning dozens of file updates per sync
call.

The **ironic-inspector** takes over the control of the DHCP hosts directory to
implement its filter cache. Files are generated dynamically so should not be
edited by hand. To minimize the interference between the deployment and
introspection, **ironic-inspector** has to start the **dnsmasq** service only
after the initial synchronization. Conversely, the **dnsmasq** service is
stopped upon (unexpected) **ironic-inspector** exit.

To avoid accumulating stale DHCP host files over time, the driver cleans up
the DHCP hosts directory before the initial synchronization during the
start-up.

Although the filter driver tries its best to always stop the **dnsmasq**
service, it is recommended that the operator configures the **dnsmasq**
service in such a way that it terminates upon **ironic-inspector**
(unexpected) exit to prevent a stale blacklist from being used by the
**dnsmasq** service.

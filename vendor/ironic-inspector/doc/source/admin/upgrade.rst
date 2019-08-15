Upgrade Guide
-------------

The `release notes <https://docs.openstack.org/releasenotes/ironic-inspector/>`_
should always be read carefully when upgrading the ironic-inspector service.
Starting with the Mitaka series, specific upgrade steps and considerations are
well-documented in the release notes.

Upgrades are only supported one series at a time, or within a series.
Only offline (with downtime) upgrades are currently supported.

When upgrading ironic-inspector, the following steps should always be taken:

* Update ironic-inspector code, without restarting the service yet.

* Stop the ironic-inspector service.

* Run database migrations::

    ironic-inspector-dbsync --config-file <PATH-TO-INSPECTOR.CONF> upgrade

* Start the ironic-inspector service.

* Upgrade the ironic-python-agent image used for introspection.

.. note::
    There is no implicit upgrade order between ironic and ironic-inspector,
    unless the `release notes`_ say otherwise.

Migrating introspection data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Starting with Stein release, ironic-inspector supports two introspection data
storage backends: ``swift`` and ``database``. If you decide to change the
backend, you can use the provided command to migrate the data::

    ironic-inspector-migrate-data --from swift --to database --config-file /etc/ironic-inspector/inspector.conf

.. note::
    Configuration for **both** backends is expected to be present in the
    configuration file for this command to succeed.

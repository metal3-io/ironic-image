===============================================
Hardware introspection for OpenStack Bare Metal
===============================================

Introduction
============

.. image:: https://governance.openstack.org/tc/badges/ironic-inspector.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

This is an auxiliary service for discovering hardware properties for a
node managed by `Ironic`_. Hardware introspection or hardware
properties discovery is a process of getting hardware parameters required for
scheduling from a bare metal node, given its power management credentials
(e.g. IPMI address, user name and password).

* Free software: Apache license
* Source: https://git.openstack.org/cgit/openstack/ironic-inspector
* Bugs: https://storyboard.openstack.org/#!/project/944
* Downloads: https://tarballs.openstack.org/ironic-inspector/
* Documentation: https://docs.openstack.org/ironic-inspector/latest/
* Python client library and CLI tool: `python-ironic-inspector-client
  <https://pypi.org/project/python-ironic-inspector-client>`_
  (`documentation
  <https://docs.openstack.org/python-ironic-inspector-client/latest/>`_).

.. _Ironic: https://wiki.openstack.org/wiki/Ironic

.. note::
    **ironic-inspector** was called *ironic-discoverd* before version 2.0.0.

Release Notes
=============

For information on any current or prior version, see `the release notes`_.

.. _the release notes: https://docs.openstack.org/releasenotes/ironic-inspector/

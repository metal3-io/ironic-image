=================
How To Contribute
=================

Basics
~~~~~~

* Our source code is hosted on `OpenStack GitHub`_, but please do not send pull
  requests there.

* Please follow usual OpenStack `Gerrit Workflow`_ to submit a patch.

* Update change log in README.rst on any significant change.

* It goes without saying that any code change should by accompanied by unit
  tests.

* Note the branch you're proposing changes to. ``master`` is the current focus
  of development, use ``stable/VERSION`` for proposing an urgent fix, where
  ``VERSION`` is the current stable series. E.g. at the moment of writing the
  stable branch is ``stable/1.0``.

* Please file an RFE in StoryBoard_ for any significant code change and a
  regular story for any significant bug fix.

.. _OpenStack GitHub: https://github.com/openstack/ironic-inspector
.. _Gerrit Workflow: https://docs.openstack.org/infra/manual/developers.html#development-workflow
.. _StoryBoard: https://storyboard.openstack.org/#!/project/944

Development Environment
~~~~~~~~~~~~~~~~~~~~~~~

First of all, install *tox* utility. It's likely to be in your distribution
repositories under name of ``python-tox``. Alternatively, you can install it
from PyPI.

Next checkout and create environments::

    git clone https://github.com/openstack/ironic-inspector.git
    cd ironic-inspector
    tox

Repeat *tox* command each time you need to run tests. If you don't have Python
interpreter of one of supported versions (currently 2.7 and 3.4), use
``-e`` flag to select only some environments, e.g.

::

    tox -e py27

.. note::
    Support for Python 3 is highly experimental, stay with Python 2 for the
    production environment for now.

.. note::
    This command also runs tests for database migrations. By default the sqlite
    backend is used. For testing with mysql or postgresql, you need to set up
    a db named 'openstack_citest' with user 'openstack_citest' and password
    'openstack_citest' on localhost. Use the script
    ``tools/test_setup.sh`` to set the database up the same way as
    done in the OpenStack CI environment.

.. note::
    Users of Fedora <= 23 will need to run "sudo dnf --releasever=24 update
    python-virtualenv" to run unit tests

To run the functional tests, use::

    tox -e func

Once you have added new state or transition into inspection state machine, you
should regenerate :ref:`State machine diagram <state_machine_diagram>` with::

    tox -e genstates

Run the service with::

    .tox/py27/bin/ironic-inspector --config-file example.conf

Of course you may have to modify ``example.conf`` to match your OpenStack
environment. See the `install guide <../install#sample-configuration-files>`_
for information on generating or downloading an example configuration file.

You can develop and test **ironic-inspector** using DevStack - see
`Deploying Ironic Inspector with DevStack`_ for the current status.

Deploying Ironic Inspector with DevStack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`DevStack <https://docs.openstack.org/devstack/latest/>`_ provides a way to
quickly build a full OpenStack development environment with requested
components. There is a plugin for installing **ironic-inspector** in DevStack.
Installing **ironic-inspector** requires a machine running Ubuntu 14.04 (or
later) or Fedora 23 (or later). Make sure this machine is fully up to date and
has the latest packages installed before beginning this process.

Download DevStack::

    git clone https://git.openstack.org/openstack-dev/devstack.git
    cd devstack


Create ``local.conf`` file with minimal settings required to
enable both the **ironic** and the **ironic-inspector**. You can start with the
`Example local.conf`_ and extend it as needed.


Example local.conf
------------------

.. literalinclude:: ../../../devstack/example.local.conf


Notes
-----

* Set IRONIC_INSPECTOR_BUILD_RAMDISK to True if you want to build ramdisk.
  Default value is False and ramdisk will be downloaded instead of building.

* 1024 MiB of RAM is a minimum required for the default build of IPA based on
  CoreOS. If you plan to use another operating system and build IPA with
  diskimage-builder 2048 MiB is recommended.

* Network configuration is pretty sensitive, better not to touch it
  without deep understanding.

* This configuration disables **horizon**, **heat**, **cinder** and
  **tempest**, adjust it if you need these services.

Start the install::

    ./stack.sh

Usage
-----

After installation is complete, you can source ``openrc`` in your shell, and
then use the OpenStack CLI to manage your DevStack::

    source openrc admin demo

Show DevStack screens::

    screen -x stack

To exit screen, hit ``CTRL-a d``.

List baremetal nodes::

    openstack baremetal node list

Bring the node to manageable state::

    openstack baremetal node manage <NodeID>

Inspect the node::

    openstack baremetal node inspect <NodeID>

.. note::
    The deploy driver used must support the inspect interface. See also the
    `Ironic Python Agent
    <https://docs.openstack.org/ironic/latest/admin/drivers/ipa.html>`_.

A node can also be inspected using the following command. However, this will
not affect the provision state of the node::

    openstack baremetal introspection start <NodeID>

Check inspection status::

    openstack baremetal introspection status <NodeID>

Optionally, get the inspection data::

    openstack baremetal introspection data save <NodeID>


Writing a Plugin
~~~~~~~~~~~~~~~~

* **ironic-inspector** allows you to hook code into the data processing chain
  after introspection. Inherit ``ProcessingHook`` class defined in
  ironic_inspector.plugins.base_ module and overwrite any or both of
  the following methods:

  ``before_processing(introspection_data,**)``
      called before any data processing, providing the raw data. Each plugin in
      the chain can modify the data, so order in which plugins are loaded
      matters here. Returns nothing.
  ``before_update(introspection_data,node_info,**)``
      called after node is found and ports are created, but before data is
      updated on a node.  Please refer to the docstring for details
      and examples.

  You can optionally define the following attribute:

  ``dependencies``
      a list of entry point names of the hooks this hook depends on. These
      hooks are expected to be enabled before the current hook.

  Make your plugin a setuptools entry point under
  ``ironic_inspector.hooks.processing`` namespace and enable it in the
  configuration file (``processing.processing_hooks`` option).

* **ironic-inspector** allows plugins to override the action when node is not
  found in node cache. Write a callable with the following signature:

  ``(introspection_data,**)``
    called when node is not found in cache, providing the processed data.
    Should return a ``NodeInfo`` class instance.

  Make your plugin a setuptools entry point under
  ``ironic_inspector.hooks.node_not_found`` namespace and enable it in the
  configuration file (``processing.node_not_found_hook`` option).

* **ironic-inspector**  allows more condition types to be added for
  `Introspection Rules`_. Inherit ``RuleConditionPlugin`` class defined in
  ironic_inspector.plugins.base_ module and overwrite at least the following
  method:

  ``check(node_info,field,params,**)``
      called to check that condition holds for a given field. Field value is
      provided as ``field`` argument, ``params`` is a dictionary defined
      at the time of condition creation. Returns boolean value.

  The following methods and attributes may also be overridden:

  ``validate(params,**)``
      called to validate parameters provided during condition creating.
      Default implementation requires keys listed in ``REQUIRED_PARAMS`` (and
      only them).

  ``REQUIRED_PARAMS``
      contains set of required parameters used in the default implementation
      of ``validate`` method, defaults to ``value`` parameter.

  ``ALLOW_NONE``
      if it's set to ``True``, missing fields will be passed as ``None``
      values instead of failing the condition. Defaults to ``False``.

  Make your plugin a setuptools entry point under
  ``ironic_inspector.rules.conditions`` namespace.

* **ironic-inspector** allows more action types to be added for `Introspection
  Rules`_. Inherit ``RuleActionPlugin`` class defined in
  ironic_inspector.plugins.base_ module and overwrite at least the following
  method:

  ``apply(node_info,params,**)``
      called to apply the action.

  The following methods and attributes may also be overridden:

  ``validate(params,**)``
      called to validate parameters provided during actions creating.
      Default implementation requires keys listed in ``REQUIRED_PARAMS`` (and
      only them).

  ``REQUIRED_PARAMS``
      contains set of required parameters used in the default implementation
      of ``validate`` method, defaults to no parameters.

  Make your plugin a setuptools entry point under
  ``ironic_inspector.rules.conditions`` namespace.

.. note::
    ``**`` argument is needed so that we can add optional arguments without
    breaking out-of-tree plugins. Please make sure to include and ignore it.

.. _ironic_inspector.plugins.base: https://docs.openstack.org/ironic-inspector/latest/contributor/api/ironic_inspector.plugins.base.html
.. _Introspection Rules: https://docs.openstack.org/ironic-inspector/latest/user/usage.html#introspection-rules

Making changes to the database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to make a change to the ironic-inspector database you must update the
database models found in ironic_inspector.db_ and then create a migration to
reflect that change.

There are two ways to create a migration which are described below, both of
these generate a new migration file. In this file there is only one function:

* ``upgrade`` - The function to run when
    ``ironic-inspector-dbsync upgrade`` is run, and should be populated with
    code to bring the database up to its new state from the state it was in
    after the last migration.

For further information on creating a migration, refer to
`Create a Migration Script`_ from the alembic documentation.

Autogenerate
------------

This is the simplest way to create a migration. Alembic will compare the models
to an up to date database, and then attempt to write a migration based on the
differences. This should generate correct migrations in most cases however
there are some cases when it can not detect some changes and may require
manual modification, see `What does Autogenerate Detect (and what does it not
detect?)`_ from the alembic documentation.

::

    ironic-inspector-dbsync upgrade
    ironic-inspector-dbsync revision -m "A short description" --autogenerate

Manual
------

This will generate an empty migration file, with the correct revision
information already included. However the upgrade function is left empty
and must be manually populated in order to perform the correct actions on
the database::

    ironic-inspector-dbsync revision -m "A short description"

.. _Create a Migration Script: http://alembic.zzzcomputing.com/en/latest/tutorial.html#create-a-migration-script
.. _ironic_inspector.db: https://docs.openstack.org/ironic-inspector/latest/contributor/api/ironic_inspector.db.html
.. _What does Autogenerate Detect (and what does it not detect?): http://alembic.zzzcomputing.com/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect

Implementing PXE Filter Drivers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Background
----------

**inspector** in-band introspection PXE-boots the Ironic Python Agent "live"
image, to inspect the baremetal server. **ironic** also PXE-boots IPA to
perform tasks on a node, such as deploying an image. **ironic** uses
**neutron** to provide DHCP, however **neutron** does not provide DHCP for
unknown MAC addresses so **inspector** has to use its own DHCP/TFTP stack for
discovery and inspection.

When **ironic** and **inspector** are operating in the same L2 network, there
is a potential for the two DHCPs to race, which could result in a node being
deployed by **ironic** being PXE booted by **inspector**.

To prevent DHCP races between the **inspector** DHCP and **ironic** DHCP,
**inspector** has to be able to filter which nodes can get a DHCP lease from
the **inspector** DHCP server. These filters can then be used to prevent
node's enrolled in **ironic** inventory from being PXE-booted unless they are
explicitly moved into the ``inspected`` state.

Filter Interface
----------------

.. py:currentmodule:: ironic_inspector.pxe_filter.interface

The contract between **inspector** and a PXE filter driver is described in the
:class:`FilterDriver` interface. The methods a driver has to implement are:

* :meth:`~FilterDriver.init_filter` called on the service start to initialize
  internal driver state

* :meth:`~FilterDriver.sync` called both periodically and when a node starts or
  finishes introspection to white or blacklist its ports MAC addresses in the
  driver

* :meth:`~FilterDriver.tear_down_filter` called on service exit to reset the
  internal driver state

.. py:currentmodule:: ironic_inspector.pxe_filter.base

The driver-specific configuration is suggested to be parsed during
instantiation. There's also a convenience generic interface implementation
:class:`BaseFilter` that provides base locking and initialization
implementation. If required, a driver can opt-out from the periodic
synchronization by overriding the :meth:`~BaseFilter.get_periodic_sync_task`.

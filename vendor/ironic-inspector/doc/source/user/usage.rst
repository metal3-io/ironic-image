Usage
-----

.. _usage_guide:

Refer to :ref:`api <http_api>` for information on the HTTP API.
Refer to the `client documentation`_ for information on how to use CLI and
Python library.

.. _client documentation: https://docs.openstack.org/python-ironic-inspector-client/latest/

Using from Ironic API
~~~~~~~~~~~~~~~~~~~~~

Ironic Kilo introduced support for hardware introspection under name of
"inspection". **ironic-inspector** introspection is supported for some generic
drivers, please refer to `Ironic inspection documentation`_ for details.

.. _Ironic inspection documentation: https://docs.openstack.org/ironic/latest/admin/inspection.html

Node States
~~~~~~~~~~~

.. _node_states:

* The nodes should be moved to ``MANAGEABLE`` provision state before
  introspection (requires *python-ironicclient* of version 0.5.0 or newer)::

    openstack baremetal node manage <node>

* After successful introspection and before deploying nodes should be made
  available to Nova, by moving them to ``AVAILABLE`` state::

    openstack baremetal node provide <node>

  .. note::
    Due to how Nova interacts with Ironic driver, you should wait 1 minute
    before Nova becomes aware of available nodes after issuing this command.
    Use ``nova hypervisor-stats`` command output to check it.

Introspection Rules
~~~~~~~~~~~~~~~~~~~

.. _introspection_rules:

Inspector supports a simple JSON-based DSL to define rules to run during
introspection. Inspector provides an API to manage such rules, and will run
them automatically after running all processing hooks.

A rule consists of conditions to check, and actions to run. If conditions
evaluate to true on the introspection data, then actions are run on a node.

Available conditions and actions are defined by plugins, and can be extended,
see :ref:`contributing_link` for details. See :ref:`api <http_api>` for
specific calls to define introspection rules.

Conditions
^^^^^^^^^^

A condition is represented by an object with fields:

``op`` the type of comparison operation, default available operators include:

* ``eq``, ``le``, ``ge``, ``ne``, ``lt``, ``gt`` - basic comparison operators;

* ``in-net`` - checks that an IP address is in a given network;

* ``matches`` - requires a full match against a given regular expression;

* ``contains`` - requires a value to contain a given regular expression;

* ``is-empty`` - checks that field is an empty string, list, dict or
  None value.

``field`` a `JSON path <http://goessner.net/articles/JsonPath/>`_ to the field
in the introspection data to use in comparison.

Starting with the Mitaka release, you can also apply conditions to ironic node
field. Prefix field with schema (``data://`` or ``node://``) to distinguish
between values from introspection data and node. Both schemes use JSON path::

    {"field": "node://property.path", "op": "eq", "value": "val"}
    {"field": "data://introspection.path", "op": "eq", "value": "val"}

if scheme (node or data) is missing, condition compares data with
introspection data.

``invert`` boolean value, whether to invert the result of the comparison.

``multiple`` how to treat situations where the ``field`` query returns multiple
results (e.g. the field contains a list), available options are:

* ``any`` (the default) require any to match,
* ``all`` require all to match,
* ``first`` requrie the first to match.

All other fields are passed to the condition plugin, e.g. numeric comparison
operations require a ``value`` field to compare against.

Actions
^^^^^^^

An action is represented by an object with fields:

``action`` type of action. Possible values are defined by plugins.

All other fields are passed to the action plugin.

Default available actions include:

* ``fail`` fail introspection. Requires a ``message`` parameter for the failure
  message.

* ``set-attribute`` sets an attribute on an Ironic node. Requires a ``path``
  field, which is the path to the attribute as used by ironic (e.g.
  ``/properties/something``), and a ``value`` to set.

* ``set-capability`` sets a capability on an Ironic node. Requires ``name``
  and ``value`` fields, which are the name and the value for a new capability
  accordingly. Existing value for this same capability is replaced.

* ``extend-attribute`` the same as ``set-attribute``, but treats existing
  value as a list and appends value to it. If optional ``unique`` parameter is
  set to ``True``, nothing will be added if given value is already in a list.

* ``add-trait`` adds a trait to an Ironic node. Requires a ``name`` field
  with the name of the trait to add.

* ``remove-trait`` removes a trait from an Ironic node. Requires a ``name``
  field with the name of the trait to remove.

Starting from Mitaka release, ``value`` field in actions supports fetching data
from introspection, using `python string formatting notation
<https://docs.python.org/2/library/string.html#formatspec>`_::

    {"action": "set-attribute", "path": "/driver_info/ipmi_address",
     "value": "{data[inventory][bmc_address]}"}

Note that any value referenced in this way will be converted to a string.

If ``value`` is a dict or list, strings nested at any level within the
structure will be formatted as well::

    {"action": "set-attribute", "path": "/properties/root_device",
     "value": {"serial": "{data[root_device][serial]}"}}

Plugins
~~~~~~~

.. _introspection_plugins:

**ironic-inspector** heavily relies on plugins for data processing. Even the
standard functionality is largely based on plugins. Set ``processing_hooks``
option in the configuration file to change the set of plugins to be run on
introspection data. Note that order does matter in this option, especially
for hooks that have dependencies on other hooks.

These are plugins that are enabled by default and should not be disabled,
unless you understand what you're doing:

``scheduler``
    validates and updates basic hardware scheduling properties: CPU number and
    architecture, memory and disk size.

    .. note::

      Diskless nodes have the disk size property ``local_gb == 0``. Always use
      node driver ``root_device`` hints to prevent unexpected HW failures
      passing silently.

``validate_interfaces``
    validates network interfaces information. Creates new
    ports, optionally deletes ports that were not present in the introspection
    data. Also sets the ``pxe_enabled`` flag for the PXE-booting port and
    unsets it for all the other ports to avoid **nova** picking a random port
    to boot the node.

The following plugins are enabled by default, but can be disabled if not
needed:

``ramdisk_error``
    reports error, if ``error`` field is set by the ramdisk, also optionally
    stores logs from ``logs`` field, see :ref:`api <http_api>` for details.
``capabilities``
    detect node capabilities: CPU, boot mode, etc. See `Capabilities
    Detection`_ for more details.
``pci_devices``
    gathers the list of all PCI devices returned by the ramdisk and compares to
    those defined in ``alias`` field(s) from ``pci_devices`` section of
    configuration file. The recognized PCI devices and their count are then
    stored in node properties. This information can be later used in nova
    flavors for node scheduling.

Here are some plugins that can be additionally enabled:

``example``
    example plugin logging it's input and output.
``raid_device``
    gathers block devices from ramdisk and exposes root device in multiple
    runs.
``extra_hardware``
    stores the value of the 'data' key returned by the ramdisk as a JSON
    encoded string in a Swift object. The plugin will also attempt to convert
    the data into a format usable by introspection rules. If this is successful
    then the new format will be stored in the 'extra' key. The 'data' key is
    then deleted from the introspection data, as unless converted it's assumed
    unusable by introspection rules.
``local_link_connection``
    Processes LLDP data returned from inspection specifically looking for the
    port ID and chassis ID, if found it configures the local link connection
    information on the nodes Ironic ports with that data. To enable LLDP in the
    inventory from IPA ``ipa-collect-lldp=1`` should be passed as a kernel
    parameter to the IPA ramdisk.  In order to avoid processing the raw LLDP
    data twice, the ``lldp_basic`` plugin should also be installed and run
    prior to this plugin.
``lldp_basic``
    Processes LLDP data returned from inspection and parses TLVs from the
    Basic Management (802.1AB), 802.1Q, and 802.3 sets and stores the
    processed data back to the Ironic inspector data in Swift.

Refer to :ref:`contributing_link` for information on how to write your
own plugin.

Discovery
~~~~~~~~~

Starting from Mitaka, **ironic-inspector** is able to register new nodes
in Ironic.

The existing ``node-not-found-hook`` handles what happens if
**ironic-inspector** receives inspection data from a node it can not identify.
This can happen if a node is manually booted without registering it with
Ironic first.

For discovery, the configuration file option ``node_not_found_hook`` should be
set to load the hook called ``enroll``. This hook will enroll the unidentified
node into Ironic using the ``fake-hardware`` hardware type. (This is
a configurable option; set ``enroll_node_driver``, in the **ironic-inspector**
configuration file, to the Ironic hardware type or classic driver you want.)

The ``enroll`` hook will also set the ``ipmi_address`` property on the new
node, if its available in the introspection data we received,
see :ref:`ramdisk_callback <ramdisk_callback>`.

Once the ``enroll`` hook is finished, **ironic-inspector** will process the
introspection data in the same way it would for an identified node. It runs
the processing :ref:`plugins <introspection_plugins>`, and after that it runs
introspection rules, which would allow for more customisable node
configuration, see :ref:`rules <introspection_rules>`.

A rule to set a node's Ironic driver to ``ipmi`` and populate the required
``driver_info`` for that driver would look like::

    [{
        "description": "Set IPMI driver_info if no credentials",
        "actions": [
            {"action": "set-attribute", "path": "driver", "value": "ipmi"},
            {"action": "set-attribute", "path": "driver_info/ipmi_username",
             "value": "username"},
            {"action": "set-attribute", "path": "driver_info/ipmi_password",
             "value": "password"}
        ],
        "conditions": [
            {"op": "is-empty", "field": "node://driver_info.ipmi_password"},
            {"op": "is-empty", "field": "node://driver_info.ipmi_username"}
        ]
    },{
        "description": "Set deploy info if not already set on node",
        "actions": [
            {"action": "set-attribute", "path": "driver_info/deploy_kernel",
             "value": "<glance uuid>"},
            {"action": "set-attribute", "path": "driver_info/deploy_ramdisk",
             "value": "<glance uuid>"}
        ],
        "conditions": [
            {"op": "is-empty", "field": "node://driver_info.deploy_ramdisk"},
            {"op": "is-empty", "field": "node://driver_info.deploy_kernel"}
        ]
    }]

All nodes discovered and enrolled via the ``enroll`` hook, will contain an
``auto_discovered`` flag in the introspection data, this flag makes it
possible to distinguish between manually enrolled nodes and auto-discovered
nodes in the introspection rules using the rule condition ``eq``::

    {
        "description": "Enroll auto-discovered nodes with ipmi hardware type",
        "actions": [
            {"action": "set-attribute", "path": "driver", "value": "ipmi"}
        ],
        "conditions": [
            {"op": "eq", "field": "data://auto_discovered", "value": true}
        ]
    }

Reapplying introspection on stored data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To allow correcting mistakes in introspection rules the API provides
an entry point that triggers the introspection over stored data.  The
data to use for processing is kept in Swift separately from the data
already processed.  Reapplying introspection overwrites processed data
in the store.  Updating the introspection data through the endpoint
isn't supported yet.  Following preconditions are checked before
reapplying introspection:

* no data is being sent along with the request
* Swift store is configured and enabled
* introspection data is stored in Swift for the node UUID
* node record is kept in database for the UUID
* introspection is not ongoing for the node UUID

Should the preconditions fail an immediate response is given to the
user:

* ``400`` if the request contained data or in case Swift store is not
  enabled in configuration
* ``404`` in case Ironic doesn't keep track of the node UUID
* ``409`` if an introspection is already ongoing for the node

If the preconditions are met a background task is executed to carry
out the processing and a ``202 Accepted`` response is returned to the
endpoint user.  As requested, these steps are performed in the
background task:

* preprocessing hooks
* post processing hooks, storing result in Swift
* introspection rules

These steps are avoided, based on the feature requirements:

* ``node_not_found_hook`` is skipped
* power operations
* roll-back actions done by hooks

Limitations:

* there's no way to update the unprocessed data atm.
* the unprocessed data is never cleaned from the store
* check for stored data presence is performed in background;
  missing data situation still results in a ``202`` response

Capabilities Detection
~~~~~~~~~~~~~~~~~~~~~~

Starting with the Newton release, **Ironic Inspector** can optionally discover
several node capabilities. A recent (Newton or newer) IPA image is required
for it to work.

Boot mode
^^^^^^^^^

The current boot mode (BIOS or UEFI) can be detected and recorded as
``boot_mode`` capability in Ironic. It will make some drivers to change their
behaviour to account for this capability. Set the ``[capabilities]boot_mode``
configuration option to ``True`` to enable.

CPU capabilities
^^^^^^^^^^^^^^^^

Several CPU flags are detected by default and recorded as following
capabilities:

* ``cpu_aes`` AES instructions.

* ``cpu_vt`` virtualization support.

* ``cpu_txt`` TXT support.

* ``cpu_hugepages`` huge pages (2 MiB) support.

* ``cpu_hugepages_1g`` huge pages (1 GiB) support.

It is possible to define your own rules for detecting CPU capabilities.
Set the ``[capabilities]cpu_flags`` configuration option to a mapping between
a CPU flag and a capability, for example::

    cpu_flags = aes:cpu_aes,svm:cpu_vt,vmx:cpu_vt

See the default value of this option for a more detail example.

InfiniBand support
^^^^^^^^^^^^^^^^^^
Starting with the Ocata release, **Ironic Inspector** supports detection of
InfiniBand network interfaces. A recent (Ocata or newer) IPA image is required
for that to work. When an InfiniBand network interface is discovered, the
**Ironic Inspector** adds a ``client-id`` attribute to the ``extra`` attribute
in the ironic port. The **Ironic Inspector** should be configured with
``iptables.ethoib_interfaces`` to indicate the Ethernet Over InfiniBand (EoIB)
which are used for physical access to the DHCP network.
For example if **Ironic Inspector** DHCP server is using ``br-inspector`` and
the ``br-inspector`` has EoIB port e.g. ``eth0``,
the ``iptables.ethoib_interfaces`` should be set to ``eth0``.
The ``iptables.ethoib_interfaces`` allows to map the baremetal GUID to it's
EoIB MAC based on the neighs files. This is needed for blocking DHCP traffic
of the nodes (MACs) which are not part of the introspection.

The format of the ``/sys/class/net/<ethoib>/eth/neighs`` file::

 # EMAC=<ethernet mac of the ethoib> IMAC=<qp number:lid:GUID>
 # For example:
 IMAC=97:fe:80:00:00:00:00:00:00:7c:fe:90:03:00:29:26:52
 qp number=97:fe
 lid=80:00:00:00:00:00:00
 GUID=7c:fe:90:03:00:29:26:52

Example of content::

 EMAC=02:00:02:97:00:01 IMAC=97:fe:80:00:00:00:00:00:00:7c:fe:90:03:00:29:26:52
 EMAC=02:00:00:61:00:02 IMAC=61:fe:80:00:00:00:00:00:00:7c:fe:90:03:00:29:24:4f

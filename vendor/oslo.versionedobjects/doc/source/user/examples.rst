==========
 Examples
==========

IOT lightbulb
=============

.. note::

    Full source located at :example:`iot_bulb`.

.. literalinclude:: ../../../oslo_versionedobjects/examples/iot_bulb.py
    :language: python
    :linenos:
    :lines: 14-

Expected (or similar) output::

	The __str__() output of this new object: IOTLightbulb(manufactured_on=2017-03-15T23:25:01Z,serial='abc-123')
	The 'serial' field of the object: abc-123
	Primitive representation of this object: {'versioned_object.version': '1.0', 'versioned_object.changes': ['serial', 'manufactured_on'], 'versioned_object.name': 'IOTLightbulb', 'versioned_object.data': {'serial': u'abc-123', 'manufactured_on': '2017-03-15T23:25:01Z'}, 'versioned_object.namespace': 'versionedobjects.examples'}
	The __str__() output of this new (reconstructed) object: IOTLightbulb(manufactured_on=2017-03-15T23:25:01Z,serial='abc-123')
	After serial number change, the set of fields that have been mutated is: set(['serial'])

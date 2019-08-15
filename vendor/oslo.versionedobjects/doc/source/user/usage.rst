=======
 Usage
=======

Incorporating oslo.versionedobjects into your projects can be accomplished in
the following steps:

1. `Add oslo.versionedobjects to requirements`_
2. `Create objects subdirectory and a base.py inside it`_
3. `Create base object with the project namespace`_
4. `Create other base objects if needed`_
5. `Implement objects and place them in objects/\*.py`_
6. `Implement extra fields in objects/fields.py`_
7. `Create object registry and register all objects`_
8. `Create and attach the object serializer`_
9. `Implement the indirection API`_


Add oslo.versionedobjects to requirements
-----------------------------------------

To use oslo.versionedobjects in an OpenStack project remember to add it to the
requirements.txt


Create objects subdirectory and a base.py inside it
---------------------------------------------------

Objects reside in the `<project>/objects` directory and this is the place
from which all objects should be imported.

Start the implementation by creating `objects/base.py` with these main
classes:


Create base object with the project namespace
---------------------------------------------

:class:`oslo_versionedobjects.base.VersionedObject`

The VersionedObject base class for the project. You have to fill up the
`OBJ_PROJECT_NAMESPACE` property. `OBJ_SERIAL_NAMESPACE` is used only for
backward compatibility and should not be set in new projects.


Create other base objects if needed
-----------------------------------

class:`oslo_versionedobjects.base.VersionedPersistentObject`

A mixin class for persistent objects can be created, defining repeated fields
like `created_at`, `updated_at`. Fields are defined in the fields property
(which is a dict).

If objects were previously passed as dicts (a common situation), a
:class:`oslo_versionedobjects.base.VersionedObjectDictCompat` can be used as a
mixin class to support dict operations.

Implement objects and place them in objects/\*.py
-------------------------------------------------

Objects classes should be created for all resources/objects passed via RPC
as IDs or dicts in order to:

* spare the database (or other resource) from extra calls
* pass objects instead of dicts, which are tagged with their version
* handle all object versions in one place (the `obj_make_compatible` method)

To make sure all objects are accessible at all times, you should import them
in __init__.py in the objects/ directory.


Implement extra fields in objects/fields.py
-------------------------------------------

New field types can be implemented by inheriting from
:class:`oslo_versionedobjects.field.Field` and overwriting the `from_primitive`
and `to_primitive` methods.

By subclassing :class:`oslo_versionedobjects.fields.AutoTypedField` you can
stack multiple fields together, making sure even nested data structures are
being validated.


Create object registry and register all objects
-----------------------------------------------

:class:`oslo_versionedobjects.base.VersionedObjectRegistry`

The place where all objects are registered. All object classes should be
registered by the :attr:`oslo_versionedobjects.base.ObjectRegistry.register`
class decorator.



Create and attach the object serializer
---------------------------------------

:class:`oslo_versionedobjects.base.VersionedObjectSerializer`

To transfer objects by RPC, subclass the
:class:`oslo_versionedobjects.base.VersionedObjectSerializer` setting the
OBJ_BASE_CLASS property to the previously defined Object class.

Connect the serializer to oslo_messaging:

.. code:: python

   serializer = RequestContextSerializer(objects_base.MagnumObjectSerializer())
   target = messaging.Target(topic=topic, server=server)
   self._server = messaging.get_rpc_server(transport, target, handlers, serializer=serializer)


Implement the indirection API
-----------------------------

:class:`oslo_versionedobjects.base.VersionedObjectIndirectionAPI`

oslo.versionedobjects supports `remotable` method calls. These are calls
of the object methods and classmethods which can be executed locally or
remotely depending on the configuration. Setting the indirection_api as a
property of an object relays the calls to decorated methods through the
defined RPC API. The attachment of the indirection_api should be handled
by configuration at startup time.

Second function of the indirection API is backporting. When the object
serializer attempts to deserialize an object with a future version, not
supported by the current instance, it calls the object_backport method in an
attempt to backport the object to a version which can then be handled as
normal.


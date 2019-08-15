# -*- coding: utf-8 -*-

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

from datetime import datetime

from oslo_versionedobjects import base
from oslo_versionedobjects import fields as obj_fields

# INTRO: This example shows how a object (a plain-old-python-object) with
# some associated fields can be used, and some of its built-in methods can
# be used to convert that object into a primitive and back again (as well
# as determine simple changes on it.


# Ensure that we always register our object with an object registry,
# so that it can be deserialized from its primitive form.
@base.VersionedObjectRegistry.register
class IOTLightbulb(base.VersionedObject):
    """Simple light bulb class with some data about it."""

    VERSION = '1.0'  # Initial version

    #: Namespace these examples will use.
    OBJ_PROJECT_NAMESPACE = 'versionedobjects.examples'

    #: Required fields this object **must** declare.
    fields = {
        'serial': obj_fields.StringField(),
        'manufactured_on': obj_fields.DateTimeField(),
    }

# Now do some basic operations on a light bulb.
bulb = IOTLightbulb(serial='abc-123', manufactured_on=datetime.now())
print("The __str__() output of this new object: %s" % bulb)
print("The 'serial' field of the object: %s" % bulb.serial)
bulb_prim = bulb.obj_to_primitive()
print("Primitive representation of this object: %s" % bulb_prim)

# Now convert the primitive back to an object (isn't it easy!)
bulb = IOTLightbulb.obj_from_primitive(bulb_prim)

bulb.obj_reset_changes()
print("The __str__() output of this new (reconstructed)"
      " object: %s" % bulb)

# Mutating a field and showing what changed.
bulb.serial = 'abc-124'
print("After serial number change, the set of fields that"
      " have been mutated is: %s" % bulb.obj_what_changed())

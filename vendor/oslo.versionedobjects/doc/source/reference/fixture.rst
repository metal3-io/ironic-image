=========
 Fixture
=========

.. automodule:: oslo_versionedobjects.fixture
   :members:
   :undoc-members:

ObjectVersionChecker
~~~~~~~~~~~~~~~~~~~~

Fingerprints
------------

One function of the ObjectVersionChecker is to generate fingerprints of versioned objects.
These fingerprints are a combination of the object's version and a hash of the
RPC-critical attributes of the object: fields and remotable methods.

The test_hashes() method is used to retrieve the expected and actual fingerprints
of the objects. When using this method to assert the versions of objects in a
local project, the expected fingerprints are the fingerprints of the previous
state of the objects. These fingerprints are defined locally in the project and
passed to test_hashes(). The actual fingerprints are the dynamically-generated
fingerprints of the current state of the objects. If the expected and actual
fingerprints do not match on an object, this means the RPC contract that was
previously defined in the object is no longer the same. Because of this, the
object's version must be updated. When the version is updated and the tests are
run again, a new fingerprint for the object is generated. This fingerprint
should be written over the previous version of the fingerprint. This shows the
newly generated fingerprint is now the most recent state of the object.

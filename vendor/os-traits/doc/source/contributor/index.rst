============
Contributing
============


Trait lifecycle policy
======================

It is the policy of this project that once registered, traits should
never be removed, even those which will never be used by code (e.g. as
a result of pivots in design or changes to the namespaces).

The general principle behind this policy is simply that an
extensible-only enumeration is easier to manage than one than can be
shrunk.  One particular example concerns the need for the placement
service to keep its database in sync with the strings in os-traits.
Whenever a placement service sees a new version of os-traits it syncs
up its database with the strings that are in the package, creating a
row in the traits table, with an id that becomes a foreign key in other
tables.  If traits could be removed, then extra clean-up code might be
needed in several places to handle this, and this would be
particularly error-prone when execution of that code would need to be
correctly orchestrated across multiple projects.


Generic instructions for contributing
=====================================


.. include:: ../../../CONTRIBUTING.rst

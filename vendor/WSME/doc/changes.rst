Changes
=======

0.8.0 (2015-08-25)
------------------

Changes that may break your app:

* Returns 400 if unexpected attributes are added to complex types (#1277571).

Other changes:

* Returns 415 when Content-Type is invalid (#1419110)
* Returns 400 if a complex input type is not a json object (#1423634)
* Fix error reports with ArrayType and DictType invalid inputs (#1428185, #1428628)
* Update README

0.7.0 (2015-05-13)
------------------

* Ensure UserType objects are converted to basetype
* Convert built-in types when passed as strings
* Multiple protocol accept or content-type matching
* Raise an InvalidInput if you get a ValueError from JSON data
* Remove unsupported python versions from setup.cfg
* Clean up setup.py and add requirements.txt
* Add full MIT license
* Fix i18n when formatting exception
* Cleanup up logging
* Make it possible to use the Response to return a non-default return type
* several fixes for SOAP protocol

0.6.4 (2014-11-20)
------------------

- Include tests in the source distribution

0.6.3 (2014-11-19)
------------------

- Disable universal wheels

0.6.2 (2014-11-18)
------------------

* Flask adapter complex types now supports flask.ext.restful
* Allow disabling complex types auto-register
* Documentation edits
* Various documentation build fixes
* Fix passing Dict and Array based UserType as params

0.6.1 (2014-05-02)
------------------

* Fix error: variable 'kw' referenced before assignment
* Fix default handling for zero values
* Fixing spelling mistakes
* A proper check of UuidType
* pecan: cleanup, use global vars and staticmethod
* args_from_args() to work with an instance of UserType

0.6 (2014-02-06)
----------------

* Add 'readonly' parameter to wsattr
* Fix typos in documents and comments
* Support dynamic types
* Support building wheels (PEP-427)
* Fix a typo in the types documentation
* Add IntegerType and some classes for validation
* Use assertRaises() for negative tests
* Remove the duplicated error message from Enum
* Drop description from 403 flask test case
* Fix SyntaxWarning under Python 3

0.5b6 (2013-10-16)
------------------

*  Add improved support for HTTP response codes in cornice apps.

*  Handle mandatory attributes

*  Fix error code returned when None is used in an Enum

*  Handle list and dict for body type in REST protocol

*  Fix Sphinx for Python 3

*  Add custom error code to ClientSideError

*  Return a ClientSideError if unable to convert data

*  Validate body when using Pecan


0.5b5 (2013-09-16)
------------------

More packaging fixes.

0.5b4 (2013-09-11)
------------------

Fixes some release-related files for the stackforge release process.
No user-facing bug fixes or features over what 0.5b3 provides.

0.5b3 (2013-09-04)
------------------

The project moved to stackforge. Mind the new URLs for the repository, bug
report etc (see the documentation).

*   Allow non-default status code return with the pecan adapter
    (Angus Salked).

*   Fix returning objects with object attributes set to None on rest-json
    & ExtDirect.

*   Allow error details to be set on the Response object (experimental !).

*   Fix: Content-Type header is not set anymore when the return type is None
    on the pecan adapter.

*   Support unicode message in ClientSideError (Mehdi Abaakouk).

*   Use pbr instead of d2to1 (Julien Danjou).

*   Python 3.3 support (Julien Danjou).

*   Pecan adapter: returned status can now be set on exceptions (Vitaly
    Kostenko).

*   TG adapters: returned status can be set on exceptions (Ryan
    Petrello).

*   six >= 1.4.0 support (Julien Danjou).

*   Require ordereddict from pypi for python < 2.6 (Ryan Petrello).

*   Make the code PEP8 compliant (Ryan Petrello).

0.5b2 (2013-04-18)
------------------

*   Changed the way datas of complex types are stored. In previous versions, an
    attribute was added to the type for each attribute, its name being the
    attribute name prefixed with '_'.

    Starting with this version, a single attribute _wsme_dataholder is added to
    the instance.

    The motivation behind this change is to avoid adding too many attributes to
    the object.

*   Add a special type 'HostRequest' that allow a function to ask for the host
    framework request object in its arguments.

*   Pecan adapter: Debug mode (which returns the exception tracebacks to the
    client) can be enabled by the pecan application configuration.

*   New adapter: wsmeext.flask, for the Flask_ framework.

.. _Flask: http://flask.pocoo.org/

*   Fix: the cornice adapter was not usable.

*   Fix: Submodules of wsmeext were missing in the packages.

*   Fix: The demo app was still depending on the WSME-Soap package (which has
    been merged into WSME in 0.5b1).

*   Fix: A function with only on 'body' parameter would fail when being called.

*   Fix: Missing arguments were poorly reported by the frameworks adapters.

0.5b1 (2013-01-30)
------------------

*   Introduce a new kind of adapters that rely on the framework routing.
    Adapters are provided for Pecan, TurboGears and cornice.

*   Reorganised the rest protocol implementation to ease the implementation of
    adapters that rely only on the host framework routing system.

*   The default rest ``@expose`` decorator does not wrap the decorated function
    anymore. If needed to expose a same function several times, a parameter
    ``multiple_expose=True`` has been introduced.

*   Remove the wsme.release module

*   Fix == operator on ArrayType

*   Adapted the wsme.sphinxext module to work with the function exposed by the
    ``wsme.pecan`` adapter.
   
*   Allow promotion of ``int`` to ``float`` on float attributes (Doug Hellman)

*   Add a ``samples_slot`` option to the ``.. autotype`` directive to
    choose where the data samples whould be inserted (Doug Hellman).

*   Add ``sample()`` to ArrayType and DictType (Doug Hellman).

*   New syntax for object arrays as GET parameters, without brackets. Ex:
    ``?o.f1=a&o.f1=b&o.f2=c&o.f2=d`` is an array of two objects:
    [{'f1': 'a', 'f2': 'c']}, {'f1': 'b', 'f2': 'd']}.

*   @signature (and its @wsexpose frontends) has a new parameter:
    ``ignore_extra_args``.

*   Fix boolean as input type support in the soap implementation (Craig
    McDaniel).

*   Fix empty/nil strings distinction in soap (Craig McDaniel).

*   Improved unittests code coverage.

*   Ported the soap implementation to python 3.

*   Moved non-core features (adapters, sphinx extension) to the ``wsmeext`` module.

*   Change the GET parameter name for passing the request body as a parameter
    is now from 'body' to '__body__'

*   The soap, extdirect and sqlalchemy packages have been merged into the main
    package.

*   Changed the documentation theme to "Cloud".

0.4 (2012-10-15)
----------------

*   Automatically converts unicode strings to/from ascii bytes.

*   Use d2to1 to simplify setup.py.

*   Implements the SPORE specification.

*   Fixed a few things in the documentation

0.4b1 (2012-09-14)
------------------

*   Now supports Python 3.2

*   String types handling is clearer.

*   New :class:`wsme.types.File` type.

*   Supports cross-referenced types.

*   Various bugfixes.

*   Tests code coverage is now over 95%.

*   RESTful protocol can now use the http method.

*   UserTypes can now be given a name that will be used in the
    documentation.

*   Complex types can inherit :class:`wsme.types.Base`. They will
    have a default constructor and be registered automatically.

*   Removed the wsme.wsgi.adapt function if favor of
    :meth:`wsme.WSRoot.wsgiapp`

Extensions
~~~~~~~~~~

wsme-soap
    *   Function names now starts with a lowercase letter.

    *   Fixed issues with arrays (issue #3).

    *   Fixed empty array handling.


wsme-sqlalchemy
    This new extension makes it easy to create webservices on top
    of a SQLAlchemy set of mapped classes.

wsme-extdirect
    *   Implements server-side DataStore
        (:class:`wsmeext.extdirect.datastore.DataStoreController`).

    *   Add Store and Model javascript definition auto-generation

    *   Add Store server-side based on SQLAlchemy mapped classes
        (:class:`wsmeext.extdirect.sadatastore.SADataStoreController`).

0.3 (2012-04-20)
----------------

*   Initial Sphinx integration.

0.3b2 (2012-03-29)
------------------

*   Fixed issues with the TG1 adapter.

*   Now handle dict and UserType types as GET/POST params.

*   Better handling of application/x-www-form-urlencoded encoded POSTs
    in rest protocols.

*   :class:`wsattr` now takes a 'default' parameter that will be returned
    instead of 'Unset' if no value has been set.

0.3b1 (2012-01-19)
------------------

*   Per-call database transaction handling.

*   :class:`Unset` is now imported in the wsme module

*   Attributes of complex types can now have a different name in
    the public api and in the implementation.

*   Complex arguments can now be sent as GET/POST params in the rest
    protocols.

*   The restjson protocol do not nest the results in an object anymore.

*   Improved the documentation

*   Fix array attributes validation.

*   Fix date|time parsing errors.

*   Fix Unset values validation.

*   Fix registering of complex types inheriting form already
    registered complex types.

*   Fix user types, str and None values encoding/decoding.

0.2.0 (2011-10-29)
------------------

*   Added batch-calls abilities.

*   Introduce a :class:`UnsetType` and a :data:`Unset` constant
    so that non-mandatory attributes can remain unset (which is
    different from null).

*   Fix: If a complex type was only used as an input type, it was
    not registered.

*   Add support for user types.

*   Add an Enum type (which is a user type).

*   The 'binary' type is now a user type.

*   Complex types:

    -   Fix inspection of complex types with inheritance.

    -   Fix inspection of self-referencing complex types.

    -   wsattr is now a python Descriptor, which makes it possible
        to retrieve the attribute definition on a class while
        manipulating values on the instance.
    
    -   Add strong type validation on assignment (made possible by
        the use of Descriptors).

*   ExtDirect:

    -   Implements batch calls

    -   Fix None values conversion

    -   Fix transaction result : 'action' and 'method' were missing.

0.1.1 (2011-10-20)
------------------

*   Changed the internal API by introducing a CallContext object.
    It makes it easier to implement some protocols that have
    a transaction or call id that has to be returned. It will also
    make it possible to implement batch-calls in a later version.

*   More test coverage.

*   Fix a problem with array attribute types not being registered.

*   Fix the mandatory / default detection on function arguments.

*   Fix issues with the SOAP protocol implementation which should now
    work properly with a suds client.

*   Fix issues with the ExtDirect protocol implementation.

0.1.0 (2011-10-14)
------------------

*   Protocol insertion order now influence the protocol selection

*   Move the soap protocol implementation in a separate lib,
    WSME-Soap

*   Introduce a new protocol ExtDirect in the WSME-ExtDirect lib.

0.1.0a4 (2011-10-12)
--------------------

*   Change the way framework adapters works. Now the adapter modules
    have a simple adapt function that adapt a :class:`wsme.WSRoot`
    instance. This way a same root can be integrated in several
    framework.

*   Protocol lookup now use entry points in the group ``[wsme.protocols]``.

0.1.0a3 (2011-10-11)
--------------------

*   Add specialised WSRoot classes for easy integration as a
    WSGI Application (:class:`wsme.wsgi.WSRoot`) or a
    TurboGears 1.x controller (:class:`wsme.tg1.WSRoot`).

*   Improve the documentation.

*   More unit tests and code-coverage.

0.1.0a2 (2011-10-07)
--------------------

*   Added support for arrays in all the protocols

0.1.0a1 (2011-10-04)
--------------------

Initial public release.

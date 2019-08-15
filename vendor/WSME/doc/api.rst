API
===

Public API
----------

:mod:`wsme` -- Essentials
~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsme

.. autoclass:: signature([return_type, [arg0_type, [arg1_type, ... ] ] ], body=None, status_code=None)

.. autoclass:: wsme.types.Base
.. autoclass:: wsattr
.. autoclass:: wsproperty

.. data:: Unset

    Default value of the complex type attributes.

.. autoclass:: WSRoot
    :members:

Internals
---------

:mod:`wsme.types` -- Types
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: wsme.types
    :members: register_type

:mod:`wsme.api` -- API related api
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: wsme.api
    :members: FunctionArgument, FunctionDefinition

:mod:`wsme.rest.args` -- REST protocol argument handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: wsme.rest.args
    :members:


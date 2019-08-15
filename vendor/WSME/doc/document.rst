Document your API
=================

Web services without a proper documentation are usually useless.

To make it easy to document your own API, WSME provides a Sphinx_ extension.

Install the extension
---------------------

Here we consider that you already quick-started a sphinx project.

#.  In your ``conf.py`` file, add ``'ext'`` to your extensions,
    and optionally set the enabled protocols.

    .. code-block:: python

        extensions = ['ext']

        wsme_protocols = ['restjson', 'restxml', 'extdirect']

#.  Copy :download:`toggle.js <_static/toggle.js>`
    and :download:`toggle.css <_static/toggle.css>`
    in your _static directory.

The ``wsme`` domain
-------------------

The extension will add a new Sphinx domain providing a few directives.

Config values
~~~~~~~~~~~~~

.. confval:: wsme_protocols

    A list of strings that are WSME protocol names. If provided by an
    additional package (for example WSME-Soap or WSME-ExtDirect), that package must
    be installed.

    The types and services generated documentation will include code samples
    for each of these protocols.

.. confval:: wsme_root

    A string that is the full name of the service root controller.
    It will be used
    to determinate the relative path of the other controllers when they
    are autodocumented, and calculate the complete webpath of the other
    controllers.

.. confval:: wsme_webpath

    A string that is the webpath where the :confval:`wsme_root` is mounted.

Directives
~~~~~~~~~~

.. rst:directive:: .. root:: <WSRoot full path>

    Define the service root controller for this documentation source file.
    To set it globally, see :confval:`wsme_root`.

    A ``webpath`` option allows override of :confval:`wsme_webpath`.
    
    Example:

    .. code-block:: rst

        .. wsme:root:: myapp.controllers.MyWSRoot
            :webpath: /api

.. rst:directive:: .. service:: name/space/ServiceName

    Declare a service.

.. rst:directive:: .. type:: MyComplexType

    Equivalent to the :rst:dir:`py:class` directive to document a complex type

.. rst:directive:: .. attribute:: aname

    Equivalent to the :rst:dir:`py:attribute` directive to document a complex type
    attribute. It takes an additional ``:type:`` field.

Example
~~~~~~~

.. list-table::
    :header-rows: 1

    * - Source
      - Result

    * - .. code-block:: rst

            .. wsme:root:: wsmeext.sphinxext.SampleService
                :webpath: /api

            .. wsme:type:: MyType

                .. wsme:attribute:: test

                    :type: int

            .. wsme:service:: name/space/SampleService
                
                .. wsme:function:: doit
                    
      - .. wsme:root:: wsmeext.sphinxext.SampleService
            :webpath: /api

        .. wsme:type:: MyType

            .. wsme:attribute:: test

                :type: int

        .. wsme:service:: name/space/SampleService
            
            .. wsme:function:: getType
                
                Returns a :wsme:type:`MyType <MyType>`


Autodoc directives
~~~~~~~~~~~~~~~~~~

Theses directives scan your code to generate the documentation from the
docstrings and your API types and controllers.

.. rst:directive:: .. autotype:: myapp.MyType

    Generate the myapp.MyType documentation.

.. rst:directive:: .. autoattribute:: myapp.MyType.aname

    Generate the myapp.MyType.aname documentation.

.. rst:directive:: .. autoservice:: myapp.MyService

    Generate the myapp.MyService documentation.

.. rst:directive:: .. autofunction:: myapp.MyService.myfunction

    Generate the myapp.MyService.myfunction documentation.

Full Example
------------

Python source
~~~~~~~~~~~~~

.. literalinclude:: ../wsmeext/sphinxext.py
    :lines: 69-96
    :language: python

Documentation source
~~~~~~~~~~~~~~~~~~~~

.. code-block:: rst

    .. default-domain:: wsmeext

    .. type:: int

        An integer

    .. autotype:: wsmeext.sphinxext.SampleType
        :members:

    .. autoservice:: wsmeext.sphinxext.SampleService
        :members:

Result
~~~~~~

.. default-domain:: wsmeext

.. type:: int

    An integer

.. autotype:: wsmeext.sphinxext.SampleType
    :members:

.. autoservice:: wsmeext.sphinxext.SampleService
    :members:


.. _Sphinx: http://sphinx.pocoo.org/

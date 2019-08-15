Integrating with a Framework
============================

General considerations
----------------------

Using WSME within another framework providing its own REST capabilities is
generally done by using a specific decorator to declare the function signature,
in addition to the framework's own way of declaring exposed functions.

This decorator can have two different names depending on the adapter.

``@wsexpose``
    This decorator will declare the function signature *and*
    take care of calling the adequate decorators of the framework.

    Generally this decorator is provided for frameworks that use
    object-dispatch controllers, such as :ref:`adapter-pecan` and
    :ref:`adapter-tg1`. 

``@signature``
    This decorator only sets the function signature and returns a function
    that can be used by the host framework as a REST request target.

    Generally this decorator is provided for frameworks that expect functions
    taking a request object as a single parameter and returning a response
    object. This is the case for :ref:`adapter-cornice` and
    :ref:`adapter-flask`.

If you want to enable additional protocols, you will need to
mount a :class:`WSRoot` instance somewhere in the application, generally
``/ws``. This subpath will then handle the additional protocols. In a future
version, a WSGI middleware will probably play this role.

.. note::

    Not all the adapters are at the same level of maturity.

WSGI Application
----------------

The :func:`wsme.WSRoot.wsgiapp` function of WSRoot returns a WSGI
application.

Example
~~~~~~~

The following example assumes the REST protocol will be entirely handled by
WSME, which is the case if you write a WSME standalone application.

.. code-block:: python

    from wsme import WSRoot, expose


    class MyRoot(WSRoot):
        @expose(unicode)
        def helloworld(self):
            return u"Hello World !"

    root = MyRoot(protocols=['restjson'])
    application = root.wsgiapp()


.. _adapter-cornice:

Cornice
-------

.. _cornice: http://cornice.readthedocs.org/en/latest/

    *"* Cornice_ *provides helpers to build & document REST-ish Web Services with
    Pyramid, with decent default behaviors. It takes care of following the HTTP
    specification in an automated way where possible."*


:mod:`wsmeext.cornice` -- Cornice adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsmeext.cornice

.. function:: signature
    
    Declare the parameters of a function and returns a function suitable for
    cornice (ie that takes a request and returns a response).

Configuration
~~~~~~~~~~~~~

To use WSME with Cornice you have to add a configuration option to your Pyramid application.

.. code-block:: python

    from pyramid.config import Configurator


    def make_app():
        config = Configurator()
        config.include("cornice")
        config.include("wsmeext.cornice")  # This includes WSME cornice support
        # ...
        return config.make_wsgi_app()

Example
~~~~~~~

.. code-block:: python

    from cornice import Service
    from wsmeext.cornice import signature
    import wsme.types

    hello = Service(name='hello', path='/', description="Simplest app")

    class Info(wsme.types.Base):
        message = wsme.types.text


    @hello.get()
    @signature(Info)
    def get_info():
        """Returns Hello in JSON or XML."""
        return Info(message='Hello World')


    @hello.post()
    @signature(None, Info)
    def set_info(info):
        print("Got a message: %s" % info.message)
    

.. _adapter-flask:

Flask
-----

    *"Flask is a microframework for Python based on Werkzeug, Jinja 2 and good
    intentions. And before you ask: It's BSD licensed! "*


.. warning::

    Flask support is limited to function signature handling. It does not
    support additional protocols. This is a temporary limitation, if you have
    needs on that matter please tell us at python-wsme@googlegroups.com.


:mod:`wsmeext.flask` -- Flask adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsmeext.flask

.. function:: signature(return_type, \*arg_types, \*\*options)

    See @\ :func:`signature` for parameters documentation.

    Can be used on a function before routing it with flask.

Example
~~~~~~~

.. code-block:: python

    from wsmeext.flask import signature

    @app.route('/multiply')
    @signature(int, int, int)
    def multiply(a, b):
        return a * b

.. _adapter-pecan:

Pecan
-----

    *"*\ Pecan_ *was created to fill a void in the Python web-framework world –
    a very lightweight framework that provides object-dispatch style routing.
    Pecan does not aim to be a "full stack" framework, and therefore includes
    no out of the box support for things like sessions or databases. Pecan
    instead focuses on HTTP itself."*

.. warning::

    A pecan application is not able to mount another WSGI application on a
    subpath. For that reason, additional protocols are not supported for now,
    until WSME provides a middleware that can do the same as a mounted
    WSRoot.

:mod:`wsmeext.pecan` -- Pecan adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsmeext.pecan

.. function:: wsexpose(return_type, \*arg_types, \*\*options)

    See @\ :func:`signature` for parameters documentation.

    Can be used on any function of a pecan
    `RestController <http://pecan.readthedocs.org/en/latest/rest.html>`_
    instead of the expose decorator from Pecan.

Configuration
~~~~~~~~~~~~~

WSME can be configured through the application configation, by adding a 'wsme'
configuration entry in ``config.py``:

.. code-block:: python

    wsme = {
        'debug': True
    }

Valid configuration variables are :

-   ``'debug'``: Whether or not to include exception tracebacks in the returned
    server-side errors.

Example
~~~~~~~

The `example <http://pecan.readthedocs.org/en/latest/rest.html#nesting-restcontroller>`_ from the Pecan documentation becomes:

.. code-block:: python

    from wsmeext.pecan import wsexpose
        
    class BooksController(RestController):
        @wsexpose(Book, int, int)
        def get(self, author_id, id):
            # ..

        @wsexpose(Book, int, int, body=Book)
        def put(self, author_id, id, book):
            # ..

    class AuthorsController(RestController):
            books = BooksController()

.. _Pecan: http://pecanpy.org/

.. _adapter-tg1:

Turbogears 1.x
--------------

The TG adapters have an api very similar to TGWebServices. Migrating from it
should be straightforward (a little howto migrate would not hurt though, and it
will be written as soon as possible).

:mod:`wsmeext.tg11` -- TG 1.1 adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsmeext.tg11

.. function:: wsexpose(return_type, \*arg_types, \*\*options)

    See @\ :func:`signature` for parameters documentation.

    Can be used on any function of a controller
    instead of the expose decorator from TG.

.. function:: wsvalidate(\*arg_types)

    Set the argument types of an exposed function. This decorator is provided
    so that WSME is an almost drop-in replacement for TGWebServices. If
    starting from scratch you can use \ :func:`wsexpose` only

.. function:: adapt(wsroot)

    Returns a TG1 controller instance that publish a :class:`wsme.WSRoot`.
    It can then be mounted on a TG1 controller.

    Because the adapt function modifies the cherrypy filters of the controller
    the 'webpath' of the WSRoot instance must be consistent with the path it
    will be mounted on.

:mod:`wsmeext.tg15` -- TG 1.5 adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. module:: wsmeext.tg15

This adapter has the exact same api as :mod:`wsmeext.tg11`.

Example
~~~~~~~

In a freshly quickstarted tg1 application (let's say, wsmedemo), you can add
REST-ish functions anywhere in your controller tree. Here directly on the root,
in controllers.py:

.. code-block:: python

    # ...

    # For tg 1.5, import from wsmeext.tg15 instead :
    from wsmeext.tg11 import wsexpose, WSRoot

    class Root(controllers.RootController):
        # Having a WSRoot on /ws is only required to enable additional
        # protocols. For REST-only services, it can be ignored.
        ws = adapt(
            WSRoot(webpath='/ws', protocols=['soap'])
        )

        @wsexpose(int, int, int)
        def multiply(self, a, b):
            return a * b

.. _TurboGears: http://www.turbogears.org/

Other frameworks
----------------

Bottle
~~~~~~

No adapter is provided yet but it should not be hard to write one, by taking
example on the cornice adapter.

This example only show how to mount a WSRoot inside a bottle application.

.. code-block:: python

    import bottle
    import wsme

    class MyRoot(wsme.WSRoot):
        @wsme.expose(unicode)
        def helloworld(self):
            return u"Hello World !"

    root = MyRoot(webpath='/ws', protocols=['restjson'])

    bottle.mount('/ws', root.wsgiapp())
    bottle.run()

Pyramid
~~~~~~~

The recommended way of using WSME inside Pyramid is to use
:ref:`adapter-cornice`.

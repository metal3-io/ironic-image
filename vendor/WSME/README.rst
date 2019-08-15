Web Services Made Easy
======================

Introduction
------------

Web Services Made Easy (WSME) simplifies the writing of REST web services
by providing simple yet powerful typing, removing the need to directly
manipulate the request and the response objects.

WSME can work standalone or on top of your favorite Python web
(micro)framework, so you can use both your preferred way of routing your REST
requests and most of the features of WSME that rely on the typing system like:

-   Alternate protocols, including those supporting batch-calls
-   Easy documentation through a Sphinx_ extension

WSME is originally a rewrite of TGWebServices
with a focus on extensibility, framework-independance and better type handling.

How Easy ?
~~~~~~~~~~

Here is a standalone wsgi example::
    
    from wsme import WSRoot, expose

    class MyService(WSRoot):
        @expose(unicode, unicode)  # First parameter is the return type,
                                   # then the function argument types
        def hello(self, who=u'World'):
            return u"Hello {0} !".format(who)

    ws = MyService(protocols=['restjson', 'restxml', 'soap'])
    application = ws.wsgiapp()

With this published at the ``/ws`` path of your application, you can access
your hello function in various protocols:

.. list-table::
    :header-rows: 1

    * - URL
      - Returns
    
    * - ``http://<server>/ws/hello.json?who=you``
      - ``"Hello you !"``

    * - ``http://<server>/ws/hello.xml``
      - ``<result>Hello World !</result>``

    * - ``http://<server>/ws/api.wsdl``
      - A WSDL description for any SOAP client.


Main features
~~~~~~~~~~~~~

-   Very simple API.
-   Supports user-defined simple and complex types.
-   Multi-protocol : REST+Json, REST+XML, SOAP, ExtDirect and more to come.
-   Extensible : easy to add more protocols or more base types.
-   Framework independence : adapters are provided to easily integrate
    your API in any web framework, for example a wsgi container,
    Pecan_, TurboGears_, Flask_, cornice_...
-   Very few runtime dependencies: webob, simplegeneric. Optionnaly lxml and
    simplejson if you need better performances.
-   Integration in `Sphinx`_ for making clean documentation with
    ``wsmeext.sphinxext``.

.. _Pecan: http://pecanpy.org/
.. _TurboGears: http://www.turbogears.org/
.. _Flask: http://flask.pocoo.org/
.. _cornice: http://pypi.python.org/pypi/cornice

Install
~~~~~~~

::

    pip install WSME

or, if you do not have pip on your system or virtualenv

::

    easy_install WSME

Changes
~~~~~~~

-   Read the `Changelog`_

Getting Help
~~~~~~~~~~~~

-   Read the `WSME Documentation`_.
-   Questions about WSME should go to the `python-wsme mailinglist`_.

Contribute
~~~~~~~~~~

* Documentation: http://packages.python.org/WSME/
* Source: http://git.openstack.org/cgit/openstack/wsme
* Bugs: https://bugs.launchpad.net/wsme/+bugs
* Code review: https://review.openstack.org/#/q/project:openstack/wsme,n,z

.. _Changelog: http://packages.python.org/WSME/changes.html
.. _python-wsme mailinglist: http://groups.google.com/group/python-wsme
.. _WSME Documentation: http://packages.python.org/WSME/
.. _WSME issue tracker: https://bugs.launchpad.net/wsme/+bugs
.. _Sphinx: http://sphinx.pocoo.org/

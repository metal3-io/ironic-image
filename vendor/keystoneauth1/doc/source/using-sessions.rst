==============
Using Sessions
==============

Introduction
============

The :py:class:`keystoneauth1.session.Session` class was introduced into
keystoneauth1 as an attempt to bring a unified interface to the various
OpenStack clients that share common authentication and request parameters
between a variety of services.

The model for using a Session and auth plugin as well as the general terms used
have been heavily inspired by the `requests <http://docs.python-requests.org>`_
library. However neither the Session class nor any of the authentication
plugins rely directly on those concepts from the requests library so you should
not expect a direct translation.

Features
--------

- Common client authentication

  Authentication is handled by one of a variety of authentication plugins and
  then this authentication information is shared between all the services that
  use the same Session object.

- Security maintenance

  Security code is maintained in a single place and reused between all
  clients such that in the event of problems it can be fixed in a single
  location.

- Standard service and version discovery

  Clients are not expected to have any knowledge of an identity token or any
  other form of identification credential. Service, endpoint, major version
  discovery, and microversion support discovery are handled by the Session and
  plugins. Discovery information is automatically cached in memory, so the user
  need not worry about excessive use of discovery metadata.

- Safe logging of HTTP interactions

  Clients need to be able to enable logging of the HTTP interactions, but some
  things, such as the token or secrets, need to be ommitted.

Sessions for Users
==================

The Session object is the contact point to your OpenStack cloud services. It
stores the authentication credentials and connection information required to
communicate with OpenStack such that it can be reused to communicate with many
services.  When creating services this Session object is passed to the client
so that it may use this information.

A Session will authenticate on demand. When a request that requires
authentication passes through the Session the authentication plugin will be
asked for a valid token. If a valid token is available it will be used
otherwise the authentication plugin may attempt to contact the authentication
service and fetch a new one.

An example using keystoneclient to wrap a Session::

    >>> from keystoneauth1.identity import v3
    >>> from keystoneauth1 import session
    >>> from keystoneclient.v3 import client

    >>> auth = v3.Password(auth_url='https://my.keystone.com:5000/v3',
    ...                    username='myuser',
    ...                    password='mypassword',
    ...                    project_name='proj',
    ...                    user_domain_id='default',
    ...                    project_domain_id='default')
    >>> sess = session.Session(auth=auth,
    ...                        verify='/path/to/ca.cert')
    >>> ks = client.Client(session=sess)
    >>> users = ks.users.list()

As other OpenStack client libraries adopt this means of operating they will be
created in a similar fashion by passing the Session object to the client's
constructor.


Sharing Authentication Plugins
------------------------------

A Session can only contain one authentication plugin. However, there is
nothing that specifically binds the authentication plugin to that Session - a
new Session can be created that reuses the existing authentication plugin::

    >>> new_sess = session.Session(auth=sess.auth,
                                   verify='/path/to/different-cas.cert')

In this case we cannot know which Session object will be used when the plugin
performs the authentication call so the command must be able to succeed with
either.

Authentication plugins can also be provided on a per-request basis. This will
be beneficial in a situation where a single Session is juggling multiple
authentication credentials::

    >>> sess.get('https://my.keystone.com:5000/v3',
                 auth=my_auth_plugin)

If an auth plugin is provided via parameter then it will override any auth
plugin on the Session.

Sessions for Client Developers
==============================

Sessions are intended to take away much of the hassle of dealing with
authentication data and token formats. Clients should be able to specify filter
parameters for selecting the endpoint and have the parsing of the catalog
managed for them.

Major Version Discovery and Microversion Support
------------------------------------------------

In OpenStack, the root URLs of available services are distributed to the user
in an object called the Service Catalog, which is part of the token they
receive. Clients are expected to use the URLs from the Service Catalog rather
than have them provided. The root URL of a given service is referred to as the
`endpoint` of the service. The URL of a specific version of a service is
referred to as a `versioned endpoint`. REST requests for a service are made
against a given `versioned endpoint`.

The topic of Major API versions and microversions can be confusing. As
`keystoneauth` provides facilities for discovery of versioned endpoints
associated with a Major API Version and for fetching information about
the microversions that versioned endpoint supports, it is important to be aware
of the distinction between the two.

Conceptually the most important thing to understand is that a Major API Version
describes the URL of a discrete versioned endpoint, while a given versioned
endpoint might have properties that express that it supports a range of
microversions.

When a user wants to make a REST request against a service, the user expresses
the Major API version and the type of service so that the appropriate versioned
endpoint can be found and used. For example, a user might request
version 2 of the compute service from cloud.example.com and end up with a
versioned endpoint of ``https://compute.example.com/v2``.

Each service provides a discovery document at the root of each versioned
endpoint that contains information about that versioned endpoint. Each service
also provides a document at the root of the unversioned endpoint that contains
a list of the discovery documents for all of the available versioned endpoints.
By examining these documents, it is possible to find the versioned endpoint
that corresponds with the user's desired Major API version.

Each of those documents may also indicate that the given versioned endpoint
supports microversions by listing a minimum and maximum microversion that it
understands. As a result of having found the versioned endpoint for the
requested Major API version, the user will also know which microversions,
if any, may be used in requests to that versioned endpoint.

When a client makes REST requests to the Major API version's endpoint, the
client can, optionally, on a request-by-request basis, include a header
specifying that the individual request use the behavior defined by the given
microversion. If a client does not request a microversion, the service will
behave as if the minimum supported microversion was specified.

.. note: The changes that each microversion reflects are documented elsewhere
         and are not information provided by the discovery process.

The overall transaction then has three parts:

* What is the endpoint for a given Major API version of a given service?
* What are the minimum and maximum microversions supported at that endpoint?
* Which one of that range of microversions, if any, does the user want to use
  for a given request?

`keystoneauth` provides facilities for discovering the endpoint for a given
Major API of a given service, as well as reporting the available microversion
ranges that endpoint supports, if any.

More information is available in the `API-WG Specs`_ on the topics of
`Microversions`_ and `Consuming the Catalog`_.

Authentication
--------------

When making a request with a Session object you can simply pass the keyword
parameter ``authenticated`` to indicate whether the argument should contain a
token, by default a token is included if an authentication plugin is available::

    >>> # In keystone this route is unprotected by default
    >>> resp = sess.get('https://my.keystone.com:5000/v3',
                        authenticated=False)


Service Discovery
-----------------


In general a client does not need to know the full URL for the server that they
are communicating with, simply that it should send a request to a path
belonging to the correct service.

This is controlled by the ``endpoint_filter`` parameter to a request which
contains all the information an authentication plugin requires to determine the
correct URL to which to send a request. When using this mode only the path for
the request needs to be specified::

    >>> resp = session.get('/users',
                           endpoint_filter={'service_type': 'identity',
                                            'interface': 'admin',
                                            'region_name': 'myregion',
                                            'min_version': '2.0',
                                            'max_version': '3.4',
                                            'discover_versions': False})

.. note:: The min_version and max_version arguments in this example indicate
          acceptable range for finding the endpoint for the given Major API
          versions. They are in the endpoint_filter, they are not requesting
          the call to ``/users`` be made at a specific microversion.

`endpoint_filter` accepts a number of arguments with which it can determine an
endpoint url:

service_type
  the type of service. For example ``identity``, ``compute``, ``volume`` or
  many other predefined identifiers.

interface
  the network exposure the interface has. Can also be a list, in which case the
  first matching interface will be used. Valid values are:

  - ``public``: An endpoint that is available to the wider internet or network.
  - ``internal``: An endpoint that is only accessible within the private
    network.
  - ``admin``: An endpoint to be used for administrative tasks.

region_name
  the name of the region where the endpoint resides.

version
  the minimum version, restricted to a given Major API. For instance, a
  `version` of ``2.2`` will match ``2.2`` and ``2.3`` but not ``2.1`` or
  ``3.0``. Mutually exclusive with `min_version` and `max_version`.

min_version
  the minimum version of a given API, intended to be used as the lower bound of
  a range with `max_version`. See `max_version` for examples. Mutually
  exclusive with `version`.

max_version
  the maximum version of a given API, intended to be used as the upper bound of
  a range with `min_version`. For example::

    'min_version': '2.2',
    'max_version': '3.3'

  will match ``2.2``, ``2.10``, ``3.0``, and ``3.3``, but not ``1.42``,
  ``2.1``, or ``3.20``. Mutually exclusive with `version`.

.. note:: version, min_version and max_version are all used to help determine
          the endpoint for a given Major API version of a service.

discover_versions
  whether or not version discovery should be run, even if not strictly
  necessary. It is often possible to fulfill an endpoint request purely
  from the catalog, meaning the version discovery API is a potentially
  wasted additional call. However, it's possible that running discovery
  instead of inference is desired. Defaults to ``True``.

All version arguments (`version`, `min_version` and `max_version`) can
be given as:

* string: ``'2.0'``
* int: ``2``
* float: ``2.0``
* tuple of ints: ``(2, 0)``

`version` and `max_version` can also be given the string ``latest``, which
indicates that the highest available version should be used.

The endpoint filter is a simple key-value filter and can be provided with any
number of arguments. It is then up to the auth plugin to correctly use the
parameters it understands.

If you want to further limit your service discovery by allowing experimental
APIs or disallowing deprecated APIs, you can use the ``allow`` parameter::

    >>> resp = session.get('/<project-id>/volumes',
                           endpoint_filter={'service_type': 'volume',
                                            'interface': 'public',
                                            'version': 1},
                           allow={'allow_deprecated': False})

The discoverable types of endpoints that `allow` can recognize are:

- `allow_deprecated`: Allow deprecated version endpoints.

- `allow_experimental`: Allow experimental version endpoints.

- `allow_unknown`: Allow endpoints with an unrecognised status.

The Session object creates a valid request by determining the URL matching the
filters and appending it to the provided path. If multiple URL matches are
found then any one may be chosen.

While authentication plugins will endeavour to maintain a consistent set of
arguments for an ``endpoint_filter`` the concept of an authentication plugin is
purposefully generic. A specific mechanism may not know how to interpret
certain arguments in which case it may ignore them. For example the
:class:`keystoneauth1.token_endpoint.Token` plugin (which is used when you want
to always use a specific endpoint and token combination) will always return the
same endpoint regardless of the parameters to ``endpoint_filter`` or a custom
OpenStack authentication mechanism may not have the concept of multiple
``interface`` options and choose to ignore that parameter.

There is some expectation on the user that they understand the limitations of
the authentication system they are using.

Using Adapters
--------------

If the developer would prefer not to provide `endpoint_filter` with every API
call, a :class:`keystoneauth1.adapter.Adapter` can be created. The `Adapter`
constructor takes the same arguments as `endpoint_filter`, as well as a
`Session`. An `Adapter` behaves much like a `Session`, with the same REST
methods, but is "mounted" on the endpoint that would be found by
`endpoint_filter`.

.. code-block:: python

    adapter = keystoneauth1.adapter.Adapter(
        session=session,
        service_type='volume',
        interface='public',
        version=1)
    response = adapter.get('/volumes')

As with ``endpoint_filter`` on a Session, the ``version``, ``min_version``
and ``max_version`` parameters exist to help determine the appropriate
endpoint for a Major API of a service.

Endpoint Metadata
-----------------

Both :class:`keystoneauth1.adapter.Adapter` and
:class:`keystoneauth1.session.Session` have a method for getting metadata about
the endpoint found for a given service: ``get_endpoint_data``.

On the :class:`keystoneauth1.session.Session` it takes the same arguments as
`endpoint_filter`.

On the :class:`keystoneauth1.adapter.Adapter` it does not take arguments, as
it returns the information for the Endpoint the Adapter is mounted on.

``get_endpoint_data`` returns an :class:`keystoneauth1.discovery.EndpointData`
object. This object can be used to find information about the Endpoint,
including which major `api_version` was found, or which `interface` in case
of ranges, lists of input values or ``latest`` version.

It can also be used to determine the `min_microversion` and `max_microversion`
supported by the API. If an API does not support microversions, the values for
both will be ``None``. It will also contain values for `next_min_version` and
`not_before` if they exist for the endpoint, or ``None`` if they do not. The
:class:`keystoneauth1.discovery.EndpointData` object will always contain
microversion related attributes regardless of whether the REST document does
or not.

``get_endpoint_data`` makes use of the same cache as the rest of the discovery
process, so calling it should incur no undue expense. By default it will make
at least one version discovery call so that it can fetch microversion metadata.
If the user knows a service does not support microversions and is merely
curious as to which major version was discovered, ``discover_versions`` can be
set to ``False`` to prevent fetching microversion metadata.

Requesting a Microversion
-------------------------

A user who wants to specify a microversion for a given request can pass it to
the ``microversion`` parameter of the `request` method on the
:class:`keystoneauth1.session.Session` object, or the
:class:`keystoneauth1.adapter.Adapter` object. This will cause `keystoneauth`
to pass the appropriate header to the service informing the service of the
microversion the user wants.

.. code-block:: python

    resp = session.get('/volumes',
                       microversion='3.15',
                       endpoint_filter={'service_type': 'volume',
                                        'interface': 'public',
                                        'min_version': '3',
                                        'max_version': 'latest'})

If the user is using a :class:`keystoneauth1.adapter.Adapter`, the
`service_type`, which is a part of the data sent in the microversion header,
will be taken from the Adapter's `service_type`.

.. code-block:: python

    adapter = keystoneauth1.adapter.Adapter(
        session=session,
        service_type='compute',
        interface='public',
        min_version='2.1')
    response = adapter.get('/servers', microversion='2.38')

The user can also provide a ``default_microversion`` parameter to the Adapter
constructor which will be used on all requests where an explicit microversion
is not requested.

.. code-block:: python

    adapter = keystoneauth1.adapter.Adapter(
        session=session,
        service_type='compute',
        interface='public',
        min_version='2.1',
        default_microversion='2.38')
    response = adapter.get('/servers')

If the user is using a :class:`keystoneauth1.session.Session`, the
`service_type` will be taken from the `service_type` in `endpoint_filter`.

If the `service_type` is the incorrect value to use for the microversion header
for the service in question, the parameter `microversion_service_type` can be
given. For instance, although keystoneauth already knows about Cinder, the
`service_type` for Cinder is ``block-storage`` but the microversion header
expects ``volume``.

.. code-block:: python

    # Interactions with cinder do not need to explicitly override the
    # microversion_service_type - it is only being used as an example for the
    # use of the parameter.
    resp = session.get('/volumes',
                       microversion='3.15',
                       microversion_service_type='volume',
                       endpoint_filter={'service_type': 'block-storage',
                                        'interface': 'public',
                                        'min_version': '3',
                                        'max_version': 'latest'})

Logging
=======

The logging system uses standard `python logging`_ rooted on the
``keystoneauth`` namespace as would be expected. There are two possibilities
of where log messages about HTTP interactions will go.

By default, all messages will go to the ``keystoneauth.session`` logger.

If the ``split_loggers`` option on the :class:`keystoneauth1.session.Session`
constructor is set to ``True``, the HTTP content will be split across four
subloggers to allow for fine-grained control of what is logged and how:

keystoneauth.session.request-id
  Emits a log entry at the ``DEBUG`` level for every http request
  including information about the URL, ``service-type`` and ``request-id``.

keystoneauth.session.request
  Emits a log entry at the ``DEBUG`` level for every http request including a
  curl formatted string of the request.

keystoneauth.session.response
  Emits a log entry at the ``DEBUG`` level for every http response received,
  including the status code, and the headers received.

keystoneauth.session.body
  Emits a log entry at the ``DEBUG`` level containing the contents of the
  response body if the ``content-type`` is either ``text`` or ``json``.

Using loggers
-------------

A full description of how to consume `python logging`_ is out of scope of this
document, but a few simple examples are provided.

If you would like to configure logging to log keystoneuath at the ``INFO``
level with no ``DEBUG`` messages:

.. code-block:: python

  import keystoneauth1
  import logging

  logger = logging.getLogger('keystoneauth')
  logger.addHandler(logging.StreamHandler())
  logger.setLevel(logging.INFO)

If you would like to get a full HTTP debug trace including bodies:

.. code-block:: python

  import keystoneauth1
  import logging

  logger = logging.getLogger('keystoneauth')
  logger.addHandler(logging.StreamHandler())
  logger.setLevel(logging.DEBUG)

If you would like to get a full HTTP debug trace bug with no bodies:

.. code-block:: python

  import keystoneauth1
  import keystoneauth1.session
  import logging

  logger = logging.getLogger('keystoneauth')
  logger.addHandler(logging.StreamHandler())
  logger.setLevel(logging.DEBUG)
  body_logger = logging.getLogger('keystoneauth.session.body')
  body_logger.setLevel(logging.WARN)
  session = keystoneauth1.session.Session(split_loggers=True)

Finally, if you would like to log request-ids and response headers to one file,
request commands, response headers and response bodies to a different file,
and everything else to the console:

.. code-block:: python

  import keystoneauth1
  import keystoneauth1.session
  import logging

  # Create a handler that outputs only outputs INFO level messages to stdout
  stream_handler = logging.StreamHandler()
  stream_handler.setLevel(logging.INFO)

  # Configure the default behavior of all keystoneauth logging to log at the
  # INFO level.
  logger = logging.getLogger('keystoneauth')
  logger.setLevel(logging.INFO)

  # Emit INFO messages from all keystoneauth loggers to stdout
  logger.addHandler(stream_handler)

  # Create an output formatter that includes logger name and timestamp.
  formatter = logging.Formatter('%(asctime)s %(name)s %(message)s')

  # Create a file output for request ids and response headers
  request_handler = logging.FileHandler('request.log')
  request_handler.setFormatter(formatter)

  # Create a file output for request commands, response headers and bodies
  body_handler = logging.FileHandler('response-body.log')
  body_handler.setFormatter(formatter)

  # Log all HTTP interactions at the DEBUG level
  session_logger = logging.getLogger('keystoneauth.session')
  session_logger.setLevel(logging.DEBUG)

  # Emit request ids to the request log
  request_id_logger = logging.getLogger('keystoneauth.session.request-id')
  request_id_logger.addHandler(request_handler)

  # Emit response headers to both the request log and the body log
  header_logger = logging.getLogger('keystoneauth.session.response')
  header_logger.addHandler(request_handler)
  header_logger.addHandler(body_handler)

  # Emit request commands to the body log
  request_logger = logging.getLogger('keystoneauth.session.request')
  request_logger.addHandler(body_handler)

  # Emit bodies only to the body log
  body_logger = logging.getLogger('keystoneauth.session.body')
  body_logger.addHandler(body_handler)

  session = keystoneauth1.session.Session(split_loggers=True)

The above will produce messages like the following in request.log:

::

  2017-09-19 22:10:09,466 keystoneauth.session.request-id  GET call to volumev2 for http://cloud.example.com/volume/v2/137155c35fb34172a284a3c2540c92ab/volumes/detail used request id req-f4f2058a-9308-4c4a-94e6-5ee1cd6c78bd
  2017-09-19 22:10:09,751 keystoneauth.session.response    [200] Date: Tue, 19 Sep 2017 22:10:09 GMT Server: Apache/2.4.18 (Ubuntu) x-compute-request-id: req-2e9181d2-9f3e-404e-a12f-1f1566736ab3 Content-Type: application/json Content-Length: 15 x-openstack-request-id: req-2e9181d2-9f3e-404e-a12f-1f1566736ab3 Connection: close

And content like the following into response-body.log:

::

  2017-09-19 22:10:09,490 keystoneauth.session.request     curl -g -i -X GET http://cloud.example.com/volume/v2/137155c35fb34172a284a3c2540c92ab/volumes/detail?marker=34cd00cf-bf67-4667-a900-5ce233e383d5 -H "User-Agent: os-client-config/1.28.0 shade/1.23.1 keystoneauth1/3.2.0 python-requests/2.18.4 CPython/2.7.12" -H "X-Auth-Token: {SHA1}a1d03d2a4cbee590a55f1786d452e1027d5fd781"
  2017-09-19 22:10:09,751 keystoneauth.session.response    [200] Date: Tue, 19 Sep 2017 22:10:09 GMT Server: Apache/2.4.18 (Ubuntu) x-compute-request-id: req-2e9181d2-9f3e-404e-a12f-1f1566736ab3 Content-Type: application/json Content-Length: 15 x-openstack-request-id: req-2e9181d2-9f3e-404e-a12f-1f1566736ab3 Connection: close
  2017-09-19 22:10:09,751 keystoneauth.session.body        {"volumes": []}

User Provided Loggers
---------------------

The HTTP methods (request, get, post, put, etc) on
`keystoneauth1.session.Session` and `keystoneauth1.adapter.Adapter` all support
a ``logger`` parameter. A user can provide their own `logger`_ which will
override the session loggers mentioned above. If a single logger is provided
in this manner, request, response and body content will all be logged to that
logger at the ``DEBUG`` level, and the strings ``REQ:``, ``RESP:`` and
``RESP BODY:`` will be pre-pended as appropriate.

.. _API-WG Specs: https://specs.openstack.org/openstack/api-wg/
.. _Consuming the Catalog: https://specs.openstack.org/openstack/api-wg/guidelines/consuming-catalog.html
.. _Microversions: https://specs.openstack.org/openstack/api-wg/guidelines/microversion_specification.html#version-discovery
.. _python logging: https://docs.python.org/3/library/logging.html
.. _logger: https://docs.python.org/3/library/logging.html#logging.Logger

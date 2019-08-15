Protocols
=========

In this document the same webservice example will be used to
illustrate the different protocols. Its source code is in the
last chapter (:ref:`protocols-the-example`).

REST
----

.. note::

    This chapter applies for all adapters, not just the native REST
    implementation.

The two REST protocols share common characterics.

Each function corresponds to distinct webpath that starts with the
root webpath, followed by the controllers names if any, and finally
the function name.

The example's exposed functions will be mapped to the following paths:

-   ``/ws/persons/create``
-   ``/ws/persons/get``
-   ``/ws/persons/list``
-   ``/ws/persons/update``
-   ``/ws/persons/destroy``

In addition to this trivial function mapping, a `method` option can
be given to the `expose` decorator. In such a case, the function
name can be omitted by the caller, and the dispatch will look at the
HTTP method used in the request to select the correct function.

The function parameters can be transmitted in two ways (if using
the HTTP method to select the function, one way or the other
may be usable) :

#.  As a GET query string or POST form parameters.

    Simple types are straight forward :

    ``/ws/person/get?id=5``

    Complex types can be transmitted this way:

    ``/ws/person/update?p.id=1&p.name=Ross&p.hobbies[0]=Dinausaurs&p.hobbies[1]=Rachel``

#.  In a Json or XML encoded POST body (see below)

The result will be returned Json or XML encoded (see below).

In case of error, a 400 or 500 status code is returned, and the
response body contains details about the error (see below).

REST+Json
---------

:name: ``'restjson'``

Implements a REST+Json protocol.

This protocol is selected if:

-   The request content-type is either 'text/javascript' or 'application/json'
-   The request 'Accept' header contains 'text/javascript' or 'application/json'
-   A trailing '.json' is added to the path
-   A 'wsmeproto=restjson' is added in the query string

Options
~~~~~~~

:nest_result: Nest the encoded result in a result param of an object.
              For example, a result of ``2`` would be ``{'result': 2}``

Types
~~~~~

+---------------+-------------------------------+
| Type          | Json type                     |
+===============+===============================+
| ``str``       | String                        |
+---------------+-------------------------------+
| ``unicode``   | String                        |
+---------------+-------------------------------+
| ``int``       | Number                        |
+---------------+-------------------------------+
| ``float``     | Number                        |
+---------------+-------------------------------+
| ``bool``      | Boolean                       |
+---------------+-------------------------------+
| ``Decimal``   | String                        |
+---------------+-------------------------------+
| ``date``      | String (YYYY-MM-DD)           |
+---------------+-------------------------------+
| ``time``      | String (hh:mm:ss)             |
+---------------+-------------------------------+
| ``datetime``  | String (YYYY-MM-DDThh:mm:ss)  |
+---------------+-------------------------------+
| Arrays        | Array                         |
+---------------+-------------------------------+
| None          | null                          |
+---------------+-------------------------------+
| Complex types | Object                        |
+---------------+-------------------------------+

Return
~~~~~~

The Json encoded result when the response code is 200, or a Json object
with error properties ('faulcode', 'faultstring' and 'debuginfo' if
available) on error.

For example, the '/ws/person/get' result looks like:

.. code-block:: javascript

    {
        'id': 2
        'fistname': 'Monica',
        'lastname': 'Geller',
        'age': 28,
        'hobbies': [
            'Food',
            'Cleaning'
        ]
    }

And in case of error:

.. code-block:: javascript
    
    {
        'faultcode': 'Client',
        'faultstring': 'id is missing'
    }

REST+XML
--------

:name: ``'restxml'``

This protocol is selected if

-   The request content-type is 'text/xml'
-   The request 'Accept' header contains 'text/xml'
-   A trailing '.xml' is added to the path
-   A 'wsmeproto=restxml' is added in the query string

Types
~~~~~

+---------------+----------------------------------------+
| Type          | XML example                            |
+===============+========================================+
| ``str``       | .. code-block:: xml                    |
|               |                                        |
|               |     <value>a string</value>            |
+---------------+----------------------------------------+
| ``unicode``   | .. code-block:: xml                    |
|               |                                        |
|               |     <value>a string</value>            |
+---------------+----------------------------------------+
| ``int``       | .. code-block:: xml                    |
|               |                                        |
|               |     <value>5</value>                   |
+---------------+----------------------------------------+
| ``float``     | .. code-block:: xml                    |
|               |                                        |
|               |     <value>3.14</value>                |
+---------------+----------------------------------------+
| ``bool``      | .. code-block:: xml                    |
|               |                                        |
|               |     <value>true</value>                |
+---------------+----------------------------------------+
| ``Decimal``   | .. code-block:: xml                    |
|               |                                        |
|               |     <value>5.46</value>                |
+---------------+----------------------------------------+
| ``date``      | .. code-block:: xml                    |
|               |                                        |
|               |     <value>2010-04-27</value>          |
+---------------+----------------------------------------+
| ``time``      | .. code-block:: xml                    |
|               |                                        |
|               |     <value>12:54:18</value>            |
+---------------+----------------------------------------+
| ``datetime``  | .. code-block:: xml                    |
|               |                                        |
|               |     <value>2010-04-27T12:54:18</value> |
+---------------+----------------------------------------+
| Arrays        | .. code-block:: xml                    |
|               |                                        |
|               |     <value>                            |
|               |         <item>Dinausaurs<item>         |
|               |         <item>Rachel<item>             |
|               |     </value>                           |
+---------------+----------------------------------------+
| None          | .. code-block:: xml                    |
|               |                                        |
|               |     <value nil="true"/>                |
+---------------+----------------------------------------+
| Complex types | .. code-block:: xml                    |
|               |                                        |
|               |     <value>                            |
|               |         <id>1</id>                     |
|               |         <fistname>Ross</fistname>      |
|               |     </value>                           |
+---------------+----------------------------------------+

Return
~~~~~~

A xml tree with a top 'result' element.

.. code-block:: xml

    <result>
        <id>1</id>
        <firstname>Ross</firstname>
        <lastname>Geller</lastname>
    </result>

Errors
~~~~~~

A xml tree with a top 'error' element, having 'faultcode', 'faultstring'
and 'debuginfo' subelements:

.. code-block:: xml

    <error>
        <faultcode>Client</faultcode>
        <faultstring>id is missing</faultstring>
    </error>

SOAP
----

:name: ``'soap'``

Implements the SOAP protocol.

A wsdl definition of the webservice is available at the 'api.wsdl' subpath.
(``/ws/api.wsdl`` in our example).

The protocol is selected if the request matches one of the following condition:

-   The Content-Type is 'application/soap+xml'
-   A header 'Soapaction' is present

Options
~~~~~~~

:tns: Type namespace

ExtDirect
---------

:name: ``extdirect``

Implements the `Ext Direct`_ protocol.

The provider definition is made available at the ``/extdirect/api.js`` subpath.

The router url is ``/extdirect/router[/subnamespace]``.

Options
~~~~~~~

:namespace: Base namespace of the api. Used for the provider definition.
:params_notation: Default notation for function call parameters. Can be
    overridden for individual functions by adding the
    ``extdirect_params_notation`` extra option to @expose.

    The possible notations are :

    -   ``'named'``  -- The function will take only one object parameter
        in which each property will be one of the parameters.
    -   ``'positional'`` -- The function will take as many parameters as
        the function has, and their position will determine which parameter
        they are.

expose extra options
~~~~~~~~~~~~~~~~~~~~

:extdirect_params_notation: Override the params_notation for a particular
    function.

.. _Ext Direct: http://www.sencha.com/products/extjs/extdirect

.. _protocols-the-example:

The example
-----------

In this document the same webservice example will be used to
illustrate the different protocols:

.. code-block:: python

    class Person(object):
        id = int
        lastname = unicode
        firstname = unicode
        age = int

        hobbies = [unicode]

        def __init__(self, id=None, lastname=None, firstname=None, age=None,
                    hobbies=None):
            if id:
                self.id = id
            if lastname:
                self.lastname = lastname
            if firstname:
                self.firstname = firstname
            if age:
                self.age = age
            if hobbies:
                self.hobbies = hobbies

    persons = {
        1: Person(1, "Geller", "Ross", 30, ["Dinosaurs", "Rachel"]),
        2: Person(2, "Geller", "Monica", 28, ["Food", "Cleaning"])
    }

    class PersonController(object):
        @expose(Person)
        @validate(int)
        def get(self, id):
            return persons[id]

        @expose([Person])
        def list(self):
            return persons.values()

        @expose(Person)
        @validate(Person)
        def update(self, p):
            if p.id is Unset:
                raise ClientSideError("id is missing")
            persons[p.id] = p
            return p

        @expose(Person)
        @validate(Person)
        def create(self, p):
            if p.id is not Unset:
                raise ClientSideError("I don't want an id")
            p.id = max(persons.keys()) + 1
            persons[p.id] = p
            return p

        @expose()
        @validate(int)
        def destroy(self, id):
            if id not in persons:
                raise ClientSideError("Unknown ID")


    class WS(WSRoot):
        person = PersonController()

    root = WS(webpath='ws')


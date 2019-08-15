Functions
=========

WSME is based on the idea that most of the time the input and output of web
services are actually strictly typed. It uses this idea to ease the
implementation of the actual functions by handling those input/output.
It also proposes alternate protocols on top of a proper REST api.

This chapter explains in detail how to 'sign' a function with WSME.

The decorators
--------------

Depending on the framework you are using, you will have to use either a
@\ :class:`wsme.signature` decorator or a  @\ :class:`wsme.wsexpose` decorator.

@signature 
~~~~~~~~~~

The base @\ :class:`wsme.signature` decorator defines the return and argument types
of the function, and if needed a few more options.

The Flask and Cornice adapters both propose a specific version of it, which
also wrap the function so that it becomes suitable for the host framework.

In any case, the use of  @\ :class:`wsme.signature` has the same meaning: tell WSME what is the
signature of the function.

@wsexpose
~~~~~~~~~

The native Rest implementation, and the TG and Pecan adapters add a  @\ :class:`wsme.wsexpose`
decorator.

It does what  @\ :class:`wsme.signature` does, *and* exposes the function in the routing system
of the host framework.

This decorator is generally used in an object-dispatch routing context.

.. note::

    Since both decorators play the same role, the rest of this
    document will alway use @signature.

Signing a function
------------------

Signing a function is just a matter of decorating it with @signature:

.. code-block:: python

    @signature(int, int, int)
    def multiply(a, b):
        return a * b

In this trivial example, we tell WSME that the 'multiply' function returns an
integer, and takes two integer parameters.

WSME will match the argument types by order to determine the exact type of each
named argument. This is important since most of the web service protocols don't
provide strict argument ordering but only named parameters.

Optional arguments
~~~~~~~~~~~~~~~~~~

Defining an argument as optional is done by providing a default value:

.. code-block:: python

    @signature(int, int, int):
    def increment(value, delta=1):
        return value + delta

In this example, the caller may omit the 'delta' argument, and no
'MissingArgument' error will be raised.

Additionally, this argument will be documented as optional by the sphinx
extension.

Body argument
~~~~~~~~~~~~~

When defining a Rest CRUD API, we generally have a URL to which we POST data.

For example:

.. code-block:: python

    @signature(Author, Author)
    def update_author(data):
        # ...
        return data

Such a function will take at least one parameter, 'data', that is a structured
type. With the default way of handling parameters, the body of the request
would look like this:

.. code-block:: javascript

    {
        "data":
        {
            "id": 1,
            "name": "Pierre-Joseph"
        }
    }

If you think (and you should) that it has one extra level of nesting, the 'body'
argument is here for you::

    @signature(Author, body=Author)
    def update_author(data):
        # ...
        return data

With this syntax, we can now post a simpler body:

.. code-block:: javascript

    {
        "id": 1,
        "name": "Pierre-Joseph"
    }

Note that this does not prevent the function from having multiple parameters; it just requires
the body argument to be the last:

.. code-block:: python

    @signature(Author, bool, body=Author)
    def update_author(force_update=False, data=None):
        # ...
        return data

In this case, the other arguments can be passed in the URL, in addition to the
body parameter. For example, a POST on ``/author/SOMEID?force_update=true``.

Status code
~~~~~~~~~~~

The default status codes returned by WSME are 200, 400 (if the client sends invalid
inputs) and 500 (for server-side errors).

Since a proper Rest API should use different return codes (201, etc), one can
use the 'status_code=' option of @signature to do so.

.. code-block:: python

    @signature(Author, body=Author, status_code=201)
    def create_author(data):
        # ...
        return data

Of course this code will only be used if no error occurs.

In case the function needs to change the status code on a per-request basis, it
can return a :class:`wsme.Response` object, allowing it to override the status
code:

.. code-block:: python

    @signature(Author, body=Author, status_code=202)
    def update_author(data):
        # ...
        response = Response(data)
        if transaction_finished_and_successful:
            response.status_code = 200
        return response

Extra arguments
~~~~~~~~~~~~~~~

The default behavior of WSME is to reject requests that give extra/unknown
arguments.  In some (rare) cases, this is undesirable.

Adding 'ignore_extra_args=True' to @signature changes this behavior.

.. note::

    If using this option seems to solve your problem, please think twice
    before using it!

Accessing the request
~~~~~~~~~~~~~~~~~~~~~

Most of the time direct access to the request object should not be needed, but
in some cases it is.

On frameworks that propose a global access to the current request it is not an
issue, but on frameworks like pyramid it is not the way to go.

To handle this use case, WSME has a special type, :class:`HostRequest`:

.. code-block:: python

    from wsme.types import HostRequest

    @signature(Author, HostRequest, body=Author)
    def create_author(request, newauthor):
        # ...
        return newauthor

In this example, the request object of the host framework will be passed as the
``request`` parameter of the create_author function.

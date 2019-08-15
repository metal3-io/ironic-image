=======
 Usage
=======

oslo.context is used in conjunction with `oslo.log`_ to provide context
aware log records when specifying a :class:`~oslo_context.context.RequestContext`
object.

This code example demonstrates two INFO log records with varying output
format due to the use of RequestContext.

.. _oslo.log: https://docs.openstack.org/oslo.log/latest/

.. highlight:: python
.. literalinclude:: examples/usage_simple.py
   :linenos:
   :lines: 28-42
   :emphasize-lines: 2,14

Source: :ref:`example_usage_simple.py`

**Example Logging Output:**

.. code-block:: none

    2016-01-20 21:56:29.283 8428 INFO __main__ [-] Message without context
    2016-01-20 21:56:29.284 8428 INFO __main__ [req-929d23e9-f50e-46ae-a8a7-02bc8c3fd2c8 - - - - -] Message with context

The format of these log records are defined by the
`logging_default_format_string`_ and `logging_context_format_string`_
configuration options respectively. The `logging_user_identity_format`_ option
also provides further context aware definition flexibility.

.. _logging_default_format_string: https://docs.openstack.org/oslo.log/latest/configuration/index.html#DEFAULT.logging_default_format_string
.. _logging_context_format_string: https://docs.openstack.org/oslo.log/latest/configuration/index.html#DEFAULT.logging_context_format_string
.. _logging_user_identity_format: https://docs.openstack.org/oslo.log/latest/configuration/index.html#DEFAULT.logging_user_identity_format

-----------------
Context Variables
-----------------

The oslo.context variables used in the **logging_context_format_string** and
**logging_user_identity_format** configuration options include:

* global_request_id - A request id
  (e.g. req-9f2c484a-b504-4fd9-b44c-4357544cca50) which may have been
  sent in from another service to indicate this is part of a chain of requests.
* request_id - A request id (e.g. req-9f2c484a-b504-4fd9-b44c-4357544cca50)
* user - A user id (e.g. e5bc7033e6b7473c9fe8ee1bd4df79a3)
* tenant - A tenant/project id (e.g. 79e338475db84f7c91ee4e86b79b34c1)
* domain - A domain id
* user_domain - A user domain id
* project_domain - A project domain id


This code example demonstrates defining a context with specific attributes
that are presented in the output log record.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 28-46
   :emphasize-lines: 2,16-18

Source: :ref:`example_usage.py`

**Example Logging Output:**

.. code-block:: none

    2016-01-21 17:30:50.263 12201 INFO __main__ [-] Message without context
    2016-01-21 17:30:50.264 12201 INFO __main__ [req-e591e881-36c3-4627-a5d8-54df200168ef 6ce90b4d d6134462 - - a6b9360e] Message with context

A context object can also be passed as an argument to any logging level
message.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 48-51
   :emphasize-lines: 4

**Example Logging Output:**

.. code-block:: none

    2016-01-21 22:43:55.621 17295 INFO __main__ [req-ac2d4a3a-ff3c-4c2b-97a0-2b76b33d9e72 ace90b4d b6134462 - - c6b9360e] Message with passed context

.. note::

    To maintain consistent log messages for operators across multiple
    OpenStack projects it is highly recommended that
    **logging_default_format_string** and **logging_context_format_string** are
    not modified from oslo.log default values.


--------------------------
Project Specific Variables
--------------------------

Individual projects can also subclass :class:`~oslo_context.context.RequestContext`
to provide additional attributes that can be using with oslo.log. The Nova
`RequestContext`_ class for example provides additional variables including
user_name and project_name.

.. _RequestContext: https://git.openstack.org/cgit/openstack/nova/tree/nova/context.py

This can for example enable the defining of **logging_user_identity_format =
%(user_name)s %(project_name)s** which would produce a log record
containing a context portion using names instead of ids such as
**[req-e4b9a194-a9b1-4829-b7d0-35226fc101fc admin demo]**

This following code example shows how a modified **logging_user_identity_format**
configuration alters the context portion of the log record.

.. literalinclude:: examples/usage_user_identity.py
   :linenos:
   :lines: 28-48
   :emphasize-lines: 9

Source: :ref:`example_usage_user_identity.py`


**Example Logging Output:**

.. code-block:: none

    2016-01-21 20:56:43.964 14816 INFO __main__ [-] Message without context
    2016-01-21 20:56:43.965 14816 INFO __main__ [req-abc 6ce90b4d/d6134462@a6b9360e] Message with context

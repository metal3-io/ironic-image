=======
 Usage
=======

.. _usage-app:

In an Application
=================

When using `Python's standard logging library`_ the following minimal setup
demonstrates basic logging.

.. _Python's standard logging library: https://docs.python.org/2/library/logging.html

.. highlight:: python
.. literalinclude:: examples/python_logging.py
   :linenos:
   :lines: 17-26

Source: :ref:`examples/python_logging.py <example_python_logging.py>`

When using Oslo Logging the following setup demonstrates a comparative
syntax with Python standard logging.


.. literalinclude:: examples/oslo_logging.py
   :linenos:
   :lines: 17-30
   :emphasize-lines: 8,9

Source: :ref:`examples/oslo_logging.py <example_oslo_logging.py>`

Oslo Logging Setup Methods
--------------------------

Applications need to use the oslo.log configuration functions to register
logging-related configuration options and configure the root and other
default loggers before using standard logging functions.

Call :func:`~oslo_log.log.register_options` with an oslo.config CONF object
before parsing any application command line options.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 33,36-37,46-49
   :emphasize-lines: 7

Optionally call :func:`~oslo_log.log.set_defaults` before setup to
change default logging levels if necessary.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 51-53,61-69
   :emphasize-lines: 10

Call :func:`~oslo_log.log.setup` with the oslo.config CONF object used
when registering objects, along with the domain and optionally a version
to configure logging for the application.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 34,36-37,70-72
   :emphasize-lines: 6

Source: :ref:`examples/usage.py <example_usage.py>`

Oslo Logging Functions
----------------------

Use standard Python logging functions to produce log records at applicable
log levels.

.. literalinclude:: examples/usage.py
   :linenos:
   :lines: 77-83

**Example Logging Output:**

::

    2016-01-14 21:07:51.394 12945 INFO __main__ [-] Welcome to Oslo Logging
    2016-01-14 21:07:51.395 12945 WARNING __main__ [-] A warning occurred
    2016-01-14 21:07:51.395 12945 ERROR __main__ [-] An error occurred
    2016-01-14 21:07:51.396 12945 ERROR __main__ [-] An Exception occurred
    2016-01-14 21:07:51.396 12945 ERROR __main__ None
    2016-01-14 21:07:51.396 12945 ERROR __main__

Logging within an application should use `Oslo International Utilities (i18n)`_ marker
functions to provide language translation capabilities.

.. _Oslo International Utilities (i18n): https://docs.openstack.org/oslo.i18n/latest

.. literalinclude:: examples/usage_i18n.py
   :linenos:
   :lines: 31-32,76,79-85
   :emphasize-lines: 1

Source: :ref:`examples/usage_i18n.py <example_usage_i18n.py>`

With the use of `Oslo Context`_, log records can also contain
additional contextual information applicable for your application.

.. _Oslo Context: https://docs.openstack.org/oslo.context/latest

.. literalinclude:: examples/usage_context.py
   :linenos:
   :lines: 80-85
   :emphasize-lines: 3-5

**Example Logging Output:**

::

    2016-01-14 20:04:34.562 11266 INFO __main__ [-] Welcome to Oslo Logging
    2016-01-14 20:04:34.563 11266 INFO __main__ [-] Without context
    2016-01-14 20:04:34.563 11266 INFO __main__ [req-bbc837a6-be80-4eb2-8ca3-53043a93b78d 6ce90b4d d6134462 a6b9360e - -] With context

The log record output format without context is defined with
:oslo.config:option:`logging_default_format_string` configuration
variable.  When specifying context the
:oslo.config:option:`logging_context_format_string` configuration
variable is used.

The Oslo RequestContext object contains a number of attributes that can be
specified in :oslo.config:option:`logging_context_format_string`. An
application can extend this object to provide additional attributes that can
be specified in log records.



Examples
--------

:ref:`examples/usage.py <example_usage.py>` provides a documented
example of Oslo Logging setup.

:ref:`examples/usage_helper.py <example_usage_helper.py>` provides an
example showing debugging logging at each step details the configuration
and logging at each step of Oslo Logging setup.

:ref:`examples/usage_i18n.py <example_usage_i18n.py>` provides a
documented example of Oslo Logging with Oslo i18n supported messages.

:ref:`examples/usage_context.py <example_usage_context.py>` provides
a documented example of Oslo Logging with Oslo Context.


General Logging Guidelines
==========================

The `OpenStack Logging Guidelines`_ in openstack-specs repository
explain how to use different logging levels, and the desired logging
patterns to be used in OpenStack applications.

.. _OpenStack Logging Guidelines: https://specs.openstack.org/openstack/openstack-specs/specs/log-guidelines.html

In a Library
============

oslo.log is primarily used for configuring logging in an application,
but it does include helpers that can be useful from libraries.

:func:`~oslo_log.log.getLogger` wraps the function of the same name
from Python's standard library to add a
:class:`~oslo_log.log.KeywordArgumentAdapter`, making it easier to
pass data to the formatters provided by oslo.log and configured by an
application.

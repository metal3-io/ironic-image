.. _opts:

=======================
 Configuration Options
=======================

oslo.log uses oslo.config to define and manage configuration options
to allow the deployer to control how an application's logs are
handled.

.. show-options:: oslo.log

Format Strings and Log Record Metadata
======================================

oslo.log builds on top of the Python standard library logging
module. The format string supports all of the built-in replacement
keys provided by that library, with some additions. Some of the more
useful keys are listed here. Refer to the `section on LogRecord
attributes
<https://docs.python.org/3.5/library/logging.html#logrecord-attributes>`__
in the library documentation for complete details about the built-in
values.

Basic Information
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(message)s``
     * The message passed from the application code.

Time Information
----------------

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(asctime)s``
     * Human-readable time stamp of when the logging record was
       created, formatted as '2003-07-08 16:49:45,896' (the numbers
       after the comma are milliseconds).
   - * ``%(isotime)s``
     * Human-readable time stamp of when the logging record was
       created, using `Python's isoformat()
       <https://docs.python.org/3.5/library/datetime.html#datetime.datetime.isoformat>`__
       function in ISO 8601 format (``YYYY-MM-DDTHH:MM:SS.mmmmmm`` or,
       if the microseconds value is 0, ``YYYY-MM-DDTHH:MM:SS``).

Location Information
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(pathname)s``
     * Full name of the source file where the logging call was issued,
       when it is available.
   - * ``%(filename)s``
     * Filename portion of ``pathname``.
   - * ``%(lineno)d``
     * Source line number where the logging call was issued, when it
       is available.
   - * ``%(module)s``
     * The module name is derived from the filename.
   - * ``%(name)s``
     * The name of the logger used to log the call. For OpenStack
       projects, this usually corresponds to the full module name
       (i.e., ``nova.api`` or ``oslo_config.cfg``).

Severity Information
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(levelname)s``
     * Text logging level for the message (``DEBUG``, ``INFO``,
       ``WARNING``, ``ERROR``, ``CRITICAL``).
   - * ``%(levelno)s``
     * Numeric logging level for the message. DEBUG level messages
       have a lower numerical value than INFO, which have a lower
       value than WARNING, etc.

Error Handling Information
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(error_summary)s``
     * The name of the exception being processed and any message
       associated with it.

Identity Information
--------------------

*These keys are only available in OpenStack applications that also use
oslo.context.*

.. list-table::
   :header-rows: 1
   :widths: 25,75

   - * Format key
     * Description
   - * ``%(user_identity)s``
     * The pre-formatted identity information about the user. See the
       ``logging_user_identity_format`` configuration option.
   - * ``%(user_name)s``
     * The name of the authenticated user, if available.
   - * ``%(user)s``
     * The ID of the authenticated user, if available.
   - * ``%(tenant_name)s``
     * The name of the authenticated tenant, if available.
   - * ``%(tenant)s``
     * The ID of the authenticated tenant, if available.
   - * ``%(user_domain)s``
     * The ID of the authenticated user domain, if available.
   - * ``%(project_domain)s``
     * The ID of the authenticated project/tenant, if available.
   - * ``%(request_id)s``
     * The ID of the current request. This value can be used to tie
       multiple log messages together as relating to the same
       operation.
   - * ``%(resource_uuid)s``
     * The ID of the resource on which the current operation will have
       effect. For example, the instance, network, volume, etc.

.. seealso::

   * `Python logging library LogRecord attributes
     <https://docs.python.org/3.5/library/logging.html#logrecord-attributes>`__

=========================
 Systemd Journal Support
=========================

One of the newer features in oslo.log is the ability to integrate with
the systemd journal service (journald) natively on newer Linux
systems. When using native journald support, additional metadata will
be logged on each log message in addition to the message itself, which
can later be used to do some interesting searching through your logs.

Enabling
========

In order to enable the support you must have Python bindings for
systemd installed. On Red Hat based systems, run::

  yum install systemd-python

On Ubuntu/Debian based systems, run::

  apt install python-systemd

If there is no native package for your distribution, or you are
running in a virtualenv, you can install with pip.::

  pip install systemd-python

.. note::

   There are also many non official systemd python modules on pypi,
   with confusingly close names. Make sure you install `systemd-python
   <https://pypi.org/project/systemd-python>`_.

After the package is installed, you must enable journald support
manually in all services that will be using it. Add the following to
the config files for all services:

.. code-block:: ini

   [DEFAULT]
   use_journal = True

In all relevant config files.

Extra Metadata
==============

Journald supports the concept of adding structured metadata in
addition to the log message in question. This makes it much easier to
take the output of journald and push it into other logging systems
like Elastic Search, without needing to regex guess relevant data. It
also allows you to search the journal by these fields using
``journalctl``.

We use this facility to add our own structured information, if it is
known at the time of logging the message.

CODE_FILE=, CODE_LINE=, CODE_FUNC=

   The code location generating this message, if known. Contains the
   source filename, the line number and the function name. (This is the
   same as systemd uses)

THREAD_NAME=, PROCESS_NAME=

   Information about the thread and process, if known. (This is the same
   as systemd uses)

EXCEPTION_TEXT=, EXCEPTION_INFO=

   Information about an exception, if an exception has been logged.

LOGGER_NAME=

   The name of the python logger that emitted the log
   message. Very often this is the module where the log message was
   emitted from.

LOGGER_LEVEL=

   The name of the python logging level, which allows seeing all
   'ERROR' messages very easily without remembering how they are
   translated to syslog priorities.

SYSLOG_IDENTIFIER=

   The binary name identified for syslog compatibility. It will be the
   basename of the process that emits the log messages
   (e.g. ``nova-api``, ``neutron-l3-agent``)

PRIORITY=

   The syslog priority (based on LOGGER_LEVEL), which allows syslog
   style filtering of messages based on their priority (an
   openstack.err log file for instance).

REQUEST_ID=

   Most OpenStack services generate a unique ``request-id`` on every
   REST API call, which is then passed between it's sub services as
   that request is handled. For example, this can be very useful in
   tracking the build of a nova server from the initial HTTP POST to
   final VM create.

PROJECT_ID=, PROJECT_NAME=, USER_ID=, USER_NAME=

   The keystone known user and project information about the
   requestor. Both the id and name are provided for easier
   searching. This can be used to understand when particular users or
   projects are reporting issues in the environment.


Additional fields may be added over time. It is unlikely that fields
will be removed, but if so they will be deprecated for one release
cycle before that happens.


Using Journalctl
================

Because systemd is relatively new in the Linux ecosystem, it's worth
noting how one can effectively use journal control.

If you want to follow all the journal logs you would do so with::

  journalctl -f

That's going to be nearly everything on your system, which you will
probably find overwhelming. You can limit this to a smaller number of
things using the ``SYSLOG_IDENTIFIER=``::

  journalctl -f SYSLOG_IDENTIFIER=nova-compute SYSLOG_IDENTIFIER=neutron-l3-agent

Specifying a query parameter multiple times defaults to an ``OR``
operation, so that will show either nova-compute or neutron-l3-agent
logs.

You can also query by request id to see the entire flow of a REST
call::

  journalctl REQUEST_ID=req-b1903300-77a8-401d-984c-8e7d17e4a15f


References
==========

- A complete list of the systemd journal fields is here, it is worth
  making yourself familiar with them -
  https://www.freedesktop.org/software/systemd/man/systemd.journal-fields.html

- The complete journalctl manual is worth reading, especially the
  ``-o`` parameter, as default displayed time resolution is only in
  seconds (even though systemd internally is tracking microsecs) -
  https://www.freedesktop.org/software/systemd/man/journalctl.html

- The guide for using systemd in devstack provides additional examples
  of effective journalctl queries -
  https://opendev.org/openstack/devstack/src/branch/master/doc/source/systemd.rst

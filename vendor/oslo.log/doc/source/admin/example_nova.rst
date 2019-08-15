=========================================
 Example Configuration File for ``nova``
=========================================

This sample configuration file demonstrates how the OpenStack compute
service (nova) might be configured.

.. literalinclude:: nova_sample.conf
   :language: ini
   :prepend: # nova_sample.conf

Two logger nodes are set up, ``root`` and ``nova``.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 1-2

Several handlers are created, to send messages to different outputs.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 4-5

And two formatters are created to be used based on whether the logging
location will have OpenStack request context information available or
not.
A Fluentd formatter is also shown.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 7-8

The ``root`` logger is configured to send messages to the ``null``
handler, silencing most messages that are not part of the nova
application code namespace.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 10-12

The ``nova`` logger is configured to send messages marked as ``INFO``
and higher level to the standard error stream.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 14-17

The ``amqp`` and ``amqplib`` loggers, used by the module that connects
the application to the message bus, are configured to emit warning
messages to the standard error stream.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 19-27

The ``sqlalchemy`` logger, used by the module that connects the
application to the database, is configured to emit warning messages to
the standard error stream.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 29-35

Similarly, ``boto``, ``suds``, and ``eventlet.wsgi.server`` are
configured to send warnings to the standard error stream.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 37-53

The ``stderr`` handler, being used by most of the loggers above, is
configured to write to the standard error stream on the console.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 55-58

The ``stderr`` handler uses the ``context`` formatter, which takes its
configuration settings from ``oslo.config``.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 85-86

The ``stdout`` and ``syslog`` handlers are defined, but not used.

The ``fluent`` handler is useful to send logs to ``fluentd``.
It is a part of fluent-logger-python and you can install it as following.

::

    $ pip install fluent-logger

This handler is configured to use ``fluent`` formatter.

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 75-78

.. literalinclude:: nova_sample.conf
   :language: ini
   :lines: 91-92

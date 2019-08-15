==============================
 Advanced Configuration Files
==============================

The oslo.config options described in :ref:`opts` make it easy to
enable some default logging configuration behavior such as setting the
default log level and output file. For more advanced configurations
using translations or multiple output destinations oslo.log relies on
the Python standard library logging module configuration file
features.

The configuration file can be used to tie together the loggers,
handlers, and formatters and provide all of the necessary
configuration values to enable any desired behavior.  Refer to the
`Python logging Module Tutorial`_ for descriptions of these concepts.

Logger Names
============

Loggers are configured by name. Most OpenStack applications use logger
names based on the source file where the message is coming from. A
file named ``myapp/package/module.py`` corresponds to a logger named
``myapp.package.module``.

Loggers are configured in a tree structure, and the names reflect
their location in this hierarchy. It is not necessary to configure
every logger, since messages are passed up the tree during
processing. To control the logging for ``myapp``, for example, it is
only necessary to set up a logger for ``myapp`` and not
``myapp.package.module``.

The base of the tree, through which all log message may pass unless
otherwise discarded, is called the ``root`` logger.

Example Files
=============

.. toctree::
   :glob:

   example*

.. seealso::

   * `Python logging Module Tutorial`_

.. _Python logging Module Tutorial: https://docs.python.org/2.7/howto/logging.html

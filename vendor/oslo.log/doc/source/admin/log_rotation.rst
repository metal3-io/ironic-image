=============
 Log rotation
=============

oslo.log can work with ``logrotate``, picking up file changes once log files
are rotated. Make sure to set the ``watch-log-file`` config option.

Log rotation on Windows
-----------------------

On Windows, in-use files cannot be renamed or moved. For this reason,
oslo.log allows setting maximum log file sizes or log rotation interval,
in which case the service itself will take care of the log rotation (as
opposed to having an external daemon).

Configuring log rotation
------------------------

Use the following options to set a maximum log file size. In this sample,
log files will be rotated when reaching 1GB, having at most 30 log files.

.. code-block:: ini

    [DEFAULT]
    log_rotation_type = size
    max_logfile_size_mb = 1024  # MB
    max_logfile_count = 30

The following sample configures log rotation to be performed every 12 hours.

.. code-block:: ini

    [DEFAULT]
    log_rotation_type = interval
    log_rotate_interval = 12
    log_rotate_interval_type = Hours
    max_logfile_count = 60

.. note::

    The time of the next rotation is computed when the service starts or when a
    log rotation is performed, using the time of the last file modification or
    the service start time, to which the configured log rotation interval is
    added. This means that service restarts may delay periodic log file
    rotations.

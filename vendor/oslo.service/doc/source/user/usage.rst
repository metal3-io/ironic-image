=====
Usage
=====

To use oslo.service in a project::

    import oslo_service

Migrating to oslo.service
=========================

The ``oslo.service`` library no longer assumes a global configuration object is
available. Instead the following functions and classes have been
changed to expect the consuming application to pass in an ``oslo.config``
configuration object:

* :func:`~oslo_service.eventlet_backdoor.initialize_if_enabled`
* :py:class:`oslo_service.periodic_task.PeriodicTasks`
* :func:`~oslo_service.service.launch`
* :py:class:`oslo_service.service.ProcessLauncher`
* :py:class:`oslo_service.service.ServiceLauncher`
* :func:`~oslo_service.sslutils.is_enabled`
* :func:`~oslo_service.sslutils.wrap`

When using service from oslo-incubator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    from foo.openstack.common import service

    launcher = service.launch(service, workers=2)

When using oslo.service
~~~~~~~~~~~~~~~~~~~~~~~

::

    from oslo_config import cfg
    from oslo_service import service

    CONF = cfg.CONF
    launcher = service.launch(CONF, service, workers=2)

Using oslo.service with oslo-config-generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``oslo.service`` provides several entry points to generate a configuration
files.

* :func:`oslo.service.service <oslo_service.service.list_opts>`
    The options from the service and eventlet_backdoor modules for
    the [DEFAULT] section.

* :func:`oslo.service.periodic_task <oslo_service.periodic_task.list_opts>`
    The options from the periodic_task module for the [DEFAULT] section.

* :func:`oslo.service.sslutils <oslo_service.sslutils.list_opts>`
    The options from the sslutils module for the [ssl] section.

* :func:`oslo.service.wsgi <oslo_service.wsgi.list_opts>`
    The options from the wsgi module for the [DEFAULT] section.

**ATTENTION:** The library doesn't provide an oslo.service entry point.

.. code-block:: bash

    $ oslo-config-generator --namespace oslo.service.service \
    --namespace oslo.service.periodic_task \
    --namespace oslo.service.sslutils

Launching and controlling services
==================================

oslo_service.service module provides tools for launching OpenStack
services and controlling their lifecycles.

A service is an instance of any class that
subclasses :py:class:`oslo_service.service.ServiceBase`.
:py:class:`ServiceBase <oslo_service.service.ServiceBase>` is an
abstract class that defines an interface every
service should implement. :py:class:`oslo_service.service.Service` can
serve as a base for constructing new services.

Launchers
~~~~~~~~~

oslo_service.service module provides two launchers for running services:

* :py:class:`oslo_service.service.ServiceLauncher` - used for
  running one or more service in a parent process.
* :py:class:`oslo_service.service.ProcessLauncher` - forks a given
  number of workers in which service(s) are then started.

It is possible to initialize whatever launcher is needed and then
launch a service using it.

.. code-block:: python

    from oslo_config import cfg
    from oslo_service import service

    CONF = cfg.CONF


    service_launcher = service.ServiceLauncher(CONF)
    service_launcher.launch_service(service.Service())

    process_launcher = service.ProcessLauncher(CONF, wait_interval=1.0)
    process_launcher.launch_service(service.Service(), workers=2)

Or one can simply call :func:`oslo_service.service.launch` which will
automatically pick an appropriate launcher based on a number of workers that
are passed to it (ServiceLauncher in case workers=1 or None and
ProcessLauncher in other case).

.. code-block:: python

    from oslo_config import cfg
    from oslo_service import service

    CONF = cfg.CONF

    launcher = service.launch(CONF, service.Service(), workers=3)

*NOTE:* Please be informed that it is highly recommended to use no
more than one instance of ServiceLauncher and ProcessLauncher classes
per process.

Signal handling
~~~~~~~~~~~~~~~

oslo_service.service provides handlers for such signals as SIGTERM, SIGINT
and SIGHUP.

SIGTERM is used for graceful termination of services. This can allow a
server to wait for all clients to close connections while rejecting new
incoming requests. Config option graceful_shutdown_timeout specifies how
many seconds after receiving a SIGTERM signal, a server should continue
to run, handling the existing connections. Setting graceful_shutdown_timeout
to zero means that the server will wait indefinitely until all remaining
requests have been fully served.

To force instantaneous termination SIGINT signal must be sent.

On receiving SIGHUP configuration files are reloaded and a service
is being reset and started again. Then all child workers are gracefully
stopped using SIGTERM and workers with new configuration are
spawned. Thus, SIGHUP can be used for changing config options on the go.

*NOTE:* SIGHUP is not supported on Windows.
*NOTE:* Config option graceful_shutdown_timeout is not supported on Windows.

Below is the example of a service with a reset method that allows reloading
logging options by sending a SIGHUP.

.. code-block:: python

    from oslo_config import cfg
    from oslo_log import log as logging
    from oslo_service import service

    CONF = cfg.CONF

    LOG = logging.getLogger(__name__)

    class FooService(service.ServiceBase):

        def start(self):
            pass

        def wait(self):
            pass

        def stop(self):
            pass

        def reset(self):
            logging.setup(cfg.CONF, 'foo')


Profiling
~~~~~~~~~

Processes spawned through oslo_service.service can be profiled (function
calltrace) through eventlet_backdoor module. Service has to configure
backdoor_port option to enable it's workers to listen on TCP ports.
Then user can send "prof()" command to capture worker processes function
calltrace.

1) To start profiling send "prof()" command on processes listening port

2) To stop profiling and capture "pstat" calltrace to a file, send prof
   command with filename as argument i.e "prof(filename)"
   on worker processes listening port. Stats file (in pstat format) with
   user provided filename by adding .prof as suffix will be generated
   in temp directory.

For example, to profile neutron server process (which is listening on
port 8002 configured through backdoor_port option),

.. code-block:: bash

    $ echo "prof()" | nc localhost 8002
    $ neutron net-create n1; neutron port-create --name p1 n1;
    $ neutron port-delete p1; neutron port-delete p1
    $ echo "prof('neutron')" | nc localhost 8002


This will generate "/tmp/neutron.prof" as stats file. Later user can print
the stats from the trace file like below

.. code-block:: python

    import pstats

    stats = pstats.Stats('/tmp/neutron.prof')
    stats.print_stats()

=======
 Usage
=======

Every long running service process should have a call to install a
signal handler which will trigger the guru meditation framework upon
receipt of SIGUSR1/SIGUSR2. This will result in the process dumping a
complete report of its current state to stderr.

For RPC listeners, it may also be desirable to install some kind of hook in
the RPC request dispatcher that will save a guru meditation report whenever
the processing of a request results in an uncaught exception. It could save
these reports to a well known directory
(/var/log/openstack/<project>/<service>/) for later analysis by the sysadmin
or automated bug analysis tools.

To use oslo.reports in a project, you need to add the following call to
:py:func:`~oslo_reports.TextGuruMeditation.setup_autorun` somewhere really
early in the startup sequence of the process::

    from oslo_reports import guru_meditation_report as gmr

    gmr.TextGuruMeditation.setup_autorun(version='13.0.0')

Note that the version parameter is the version of the component itself.

To trigger the report to be generated::

    kill -SIGUSR2 <process_id>

.. note::

   On SELinux platforms the report process may fail with an AccessDenied
   exception.  If this happens, temporarily disable SELinux enforcement
   by running ``sudo setenforce 0``, trigger the report, then turn SELinux
   back on by running ``sudo setenforce 1``.

Here is a sample report:

.. include:: report.txt
     :literal:

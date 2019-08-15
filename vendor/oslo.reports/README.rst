========================
Team and repository tags
========================

.. image:: https://governance.openstack.org/tc/badges/oslo.reports.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

.. Change things from this point on

===================================
oslo.reports
===================================

.. image:: https://img.shields.io/pypi/v/oslo.reports.svg
    :target: https://pypi.org/project/oslo.reports/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/dm/oslo.reports.svg
    :target: https://pypi.org/project/oslo.reports/
    :alt: Downloads

When things go wrong in (production) deployments of OpenStack collecting debug
data is a key first step in the process of triaging & ultimately resolving the
problem. Projects like Nova has extensively used logging capabilities which
produce a vast amount of data. This does not, however, enable an admin to
obtain an accurate view on the current live state of the system. For example,
what threads are running, what config parameters are in effect, and more.

The project oslo.reports hosts a general purpose error report generation
framework, known as the "guru meditation report"
(cf http://en.wikipedia.org/wiki/Guru_Meditation) to address the issues
described above.

Models: These classes define structured data for a variety of interesting
pieces of state. For example, stack traces, threads, config parameters,
package version info, etc. They are capable of being serialized to XML / JSON
or a plain text representation

Generators: These classes are used to populate the model classes with the
current runtime state of the system

Views: views serialize models into say JSON, text or xml. There is also
a predefined view that utilizes Jinja templating system.

There will be a number of standard models / generators available for all
OpenStack services

StackTraceModel: a base class for any model which includes a stack trace
ThreadModel: a class for information about a thread
ExceptionModel: a class for information about a caught exception
ConfigModel: a class for information about configuration file settings
PackageModel: a class for information about vendor/product/version/package information

Each OpenStack project will have the ability to register further generator
classes to provide custom project specific data.

* Free software: Apache license
* Documentation: https://docs.openstack.org/oslo.reports/latest
* Source: https://git.openstack.org/cgit/openstack/oslo.reports
* Bugs: https://bugs.launchpad.net/oslo.reports
* Release notes: https://docs.openstack.org/releasenotes/oslo.reports/

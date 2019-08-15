=======================================================
Python Middleware for OpenStack Identity API (Keystone)
=======================================================

This is the middleware provided for integrating with the OpenStack
Identity API and handling authorization enforcement based upon the
data within the OpenStack Identity tokens. Also included is middleware that
provides the ability to create audit events based on API requests.

Contents:

.. toctree::
   :maxdepth: 1

   middlewarearchitecture
   audit
   installation

Related Identity Projects
=========================

In addition to creating the Python Middleware for OpenStack Identity
API, the Keystone team also provides `Identity Service`_, as well as
`Python Client Library`_.

.. _`Identity Service`: https://docs.openstack.org/keystone/latest/
.. _`Python Client Library`: https://docs.openstack.org/python-keystoneclient/latest/

Release Notes
=============

`Release Notes`_

.. _Release Notes: https://docs.openstack.org/releasenotes/keystonemiddleware/

Contributing
============

Code is hosted `on GitHub`_. Submit bugs to the Keystone project on
`Launchpad`_. Submit code to the ``openstack/keystonemiddleware`` project
using `Gerrit`_.

.. _on GitHub: https://github.com/openstack/keystonemiddleware
.. _Launchpad: https://launchpad.net/keystonemiddleware
.. _Gerrit: https://docs.openstack.org/infra/manual/developers.html#development-workflow

Run tests with ``tox -e py27`` if running with python 2.7. See the
``tox.ini`` file for other test environment options.

Code Documentation
==================
.. toctree::
   :maxdepth: 1

   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


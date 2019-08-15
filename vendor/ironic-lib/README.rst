==========
ironic-lib
==========

Team and repository tags
------------------------

.. image:: https://governance.openstack.org/tc/badges/ironic-lib.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

Overview
--------

A common library to be used **exclusively** by projects under the `Ironic
governance <https://governance.openstack.org/tc/reference/projects/ironic.html>`_.

Running Tests
-------------

To run tests in virtualenvs (preferred)::

  $ sudo pip install tox
  $ tox

To run tests in the current environment::

  $ sudo pip install -r requirements.txt -r test-requirements.txt
  $ stestr run


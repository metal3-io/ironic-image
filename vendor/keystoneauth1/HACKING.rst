Keystone Style Commandments
===========================

- Step 1: Read the OpenStack Style Commandments
  https://docs.openstack.org/hacking/latest/
- Step 2: Read on

Exceptions
----------

When dealing with exceptions from underlying libraries, translate those
exceptions to an instance or subclass of ClientException.

=======
Testing
=======

keystoneauth uses testtools and stestr for its unittest suite
and its test runner. Basic workflow around our use of tox and stestr can
be found at https://wiki.openstack.org/testr. If you'd like to learn more
in depth:

  https://testtools.readthedocs.io/en/latest/
  https://stestr.readthedocs.io/en/latest/

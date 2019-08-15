======
Extras
======

The extensibility of keystoneauth plugins is purposefully designed to allow a
range of different authentication mechanisms that don't have to reside in the
upstream packages. There are however a number of plugins that upstream supports
that involve additional dependencies that the keystoneauth package cannot
depend upon directly.

To get around this we utilize setuptools `extras dependencies <https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies>`_ for additional
plugins. To use a plugin like the kerberos plugin that has additional
dependencies you must install the additional dependencies like::

    pip install keystoneauth1[kerberos]

By convention (not a requirement) extra plugins have a module located in the
keystoneauth1.extras module with the same name as the dependency. eg::

    from keystoneauth1.extras import kerberos

There is no keystoneauth specific check that the correct dependencies are
installed for accessing a module. You would expect to see standard python
ImportError when the required dependencies are not found.

Examples
========

All extras plugins follow the pattern:

1. import plugin module
2. instantiate the plugin
3. call get_token method of the plugin passing it a session object
   to get a token

Kerberos
--------

Get domain-scoped token using
:py:class:`~keystoneauth1.extras.kerberos.Kerberos`::

    from keystoneauth1.extras import kerberos
    from keystoneauth1 import session

    plugin = kerberos.Kerberos('http://example.com:5000/v3')
    sess = session.Session(plugin)
    token = plugin.get_token(sess)

Get unscoped federated token::

    from keystoneauth1.extras import kerberos
    from keystoneauth1 import session

    plugin = kerberos.MappedKerberos(
        auth_url='http://example.com:5000/v3', protocol='example_protocol',
        identity_provider='example_identity_provider')

    sess = session.Session()
    token = plugin.get_token(sess)

Get project scoped federated token::

    from keystoneauth1.extras import kerberos
    from keystoneauth1 import session

    plugin = kerberos.MappedKerberos(
        auth_url='http://example.com:5000/v3', protocol='example_protocol',
        identity_provider='example_identity_provider',
        project_id='example_project_id')

    sess = session.Session()
    token = plugin.get_token(sess)
    project_id = plugin.get_project_id(sess)

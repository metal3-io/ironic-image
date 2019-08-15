==============
Plugin Options
==============

Using plugins via config file
-----------------------------

When using the plugins via config file you define the plugin name as
``auth_type``. The options of the plugin are then specified while replacing
``-`` with ``_`` to be valid in configuration.

For example to use the password_ plugin in a config file you would specify:

.. code-block:: ini

    [section]
    auth_url = http://keystone.example.com:5000/
    auth_type = password
    username = myuser
    password = mypassword
    project_name = myproject
    default_domain_name = mydomain


Using plugins via CLI
---------------------

When using auth plugins via CLI via ``os-client-config`` or ``shade`` you can
specify parameters via environment configuration by using the pattern ``OS_``
followed by the uppercase parameter name replacing ``-`` with ``_``.

For example to use the password_ plugin via environment variable you specify:

.. code-block:: bash

    export OS_AUTH_TYPE=password
    export OS_AUTH_URL=http://keystone.example.com:5000/
    export OS_USERNAME=myuser
    export OS_PASSWORD=mypassword
    export OS_PROJECT_NAME=myproject
    export OS_DEFAULT_DOMAIN_NAME=mydomain

Specifying operations via CLI parameter will override the environment
parameter. These are specified with the pattern ``--os-`` and the parameter
name. Using the password_ example again:

.. code-block:: bash

    openstack --os-auth-type password \
              --os-auth-url http://keystone.example.com:5000/ \
              --os-username myuser \
              --os-password mypassword \
              --os-project-name myproject \
              --os-default-domain-name mydomain \
              operation

Additional loaders
------------------

The configuration and CLI loaders are quite commonly used however similar
concepts are found in other situations such as ``os-client-config`` in which
you specify authentication and other cloud parameters in a ``clouds.yaml``
file.

Loaders such as these use the same plugin options listed below, but via their
own mechanism. In ``os-client-config`` the password_ plugin looks like:

.. code-block:: yaml

    clouds:
      mycloud:
        auth_type: password
        auth:
          auth_url: http://keystone.example.com:5000/
          auth_type: password
          username: myuser
          password: mypassword
          project_name: myproject
          default_domain_name: mydomain

However different services may implement loaders in their own way and you
should consult their relevant documentation. The same auth options will be
available.


Available Plugins
-----------------

This is a listing of all included plugins and the options that they accept.
Plugins are listed alphabetically and not in any order of priority.

.. list-auth-plugins::

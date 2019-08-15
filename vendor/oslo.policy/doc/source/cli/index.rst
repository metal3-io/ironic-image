======================
Command Line Interface
======================

This document describes the various command line tools exposed by
``oslo.policy`` to manage policies and policy files.

oslopolicy-checker
==================

Run the command line ``oslopolicy-checker`` to check policy against the
OpenStack Identity API access information.

Command-line arguments:

* ``--policy POLICY`` path to policy file.
* ``--access ACCESS`` path to access token file.
* ``--rule RULE`` (optional) rule to test.  If omitted, tests all rules.
* ``--is_admin IS_ADMIN`` (optional) set is_admin=True on the credentials.

Sample access tokens are provided in the ``sample_data`` directory.

Examples
--------

Test all of Nova's policy with an admin token

.. code-block:: bash

   tox -e venv -- oslopolicy-checker \
     --policy  /opt/stack/nova/etc/nova/policy.json
     --access sample_data/auth_v3_token_admin.json

Test the ``compute_extension:flavorextraspecs:index`` rule in Nova's policy
with the admin member token and ``is_admin`` set to ``True``

.. code-block:: bash

   tox -e venv -- oslopolicy-checker \
     --policy  /opt/stack/nova/etc/nova/policy.json \
     --access sample_data/auth_v3_token_admin.json \
     --is_admin=true --rule compute_extension:flavorextraspecs:index

Test the ``compute_extension:flavorextraspecs:index`` rule in Nova's policy
with the plain member token

.. code-block:: bash

   tox -e venv -- oslopolicy-checker \
     --policy  /opt/stack/nova/etc/nova/policy.json \
     --access sample_data/auth_v3_token_member.json \
     --rule compute_extension:flavorextraspecs:index

oslopolicy-sample-generator
===========================

The ``oslopolicy-sample-generator`` command can be used to generate a sample
policy file based on the default policies in a given namespace. This tool
requires a namespace to query for policies and supports output in JSON or YAML.

Examples
--------

To generate sample policies for a namespace called ``keystone``:

.. code-block:: bash

   oslopolicy-sample-generator --namespace keystone


To generate sample policies in JSON use:

.. code-block:: bash

   oslopolicy-sample-generator --namespace nova --format json

To generate a sample policy file and output directly to a file:

.. code-block:: bash

   oslopolicy-sample-generator --namespace keystone \
     --format yaml \
     --output-file keystone-policy.yaml

Use the following to generate help text for additional options and arguments
supported by ``oslopolicy-sample-generator``:

.. code-block:: bash

   oslopolicy-sample-generator --help

oslopolicy-list-redundant
=========================

The ``oslopolicy-list-redundant`` tool is useful for detecting policies that
are specified in policy files that are the same as the defaults provided by the
service. Operators can use this tool to find policies that they can remove from
their policy files, making maintenance easier.

This tool assumes a policy file containing overrides exists and is specified
through configuration.

Examples
--------

To list redundant default policies:

.. code-block:: bash

   oslopolicy-list-redundant --namespace keystone --config-dir /etc/keystone

For more information regarding the options supported by this tool:

.. code-block:: bash

   oslopolicy-list-redundant --help

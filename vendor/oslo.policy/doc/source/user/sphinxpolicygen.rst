====================================
Sphinx Oslo Sample Policy Generation
====================================

.. note::
  This extension relies on ``oslopolicy-sample-generator``, which requires
  configuration of policies in code to function. Refer to the :doc:`usage`
  guide for more information.

oslo.policy includes a sphinx extension to generate a sample policy file at the
beginning of each sphinx build. This sample policy file can then be included in
your documents as a raw file, for example, via the ``literalinclude`` directive.

To activate the extension add ``oslo_policy.sphinxpolicygen`` to the list of
extensions in your sphinx ``conf.py``. Once enabled, you need to define two
options: ``policy_generator_config_file`` and ``sample_policy_basename``. For
example::

  policy_generator_config_file = '../../etc/nova/nova-policy-generator.conf'
  sample_policy_basename = '_static/nova'

where:

``policy_generator_config_file``
  Path to an configuration file used with the ``oslopolicy-sample-generator``
  utility. This can be an full path or a value relative to the documentation
  source directory (``app.srcdir``). If this option is not specified or is
  invalid then the sample policy file generation will be skipped.

  To handle cases where multiple files need to be generated, this
  value can be a list of two-part tuples containing the path to the
  configuration file and the base name for the output file (in this
  case, ``sample_policy_basename`` should not be set).

``sample_policy_basename``
  Base name of the output file. This name will be appended with a
  ``.policy.yaml.sample`` extension to generate the final output file and the
  path is relative to documentation source directory (``app.srcdir``). As such,
  using the above example, the policy file will be output to
  ``_static/nova.policy.yaml.sample``. If this option is not specified, the
  file will be output to ``sample.policy.yaml``.

Once configured, you can include this configuration file in your source:

.. code:: reST

  =============
  Sample Policy
  =============

  Here is a sample policy file.

  .. literalinclude:: _static/nova.policy.yaml.sample

==========================
Writing custom check rules
==========================

oslo.policy has supported the following syntax for a while::

    http:<target URL>, which delegates the check to a remote server


Starting with 1.29, oslo.policy will also support https url(s) as well::

    https:<target URL>, which delegates the check to a remote server


Both ``http`` and ``https`` support are implemented as custom check rules.
If you see the setup.cfg for oslo.policy, you can see the following
entry points::

    oslo.policy.rule_checks =
        http = oslo_policy._external:HttpCheck
        https = oslo_policy._external:HttpsCheck

When a policy is evaluated, when the engine encounters ``https`` like in
a snippet below::

    {
           ...
           "target 1" : "https://foo.bar/baz",
           ...
    }

The engine will look for a plugin named ``https`` in the ``rule_checks``
entry point and will try to invoke that stevedore plugin.

This mechanism allows anyone to write their own code, in their own library
with their own custom stevedore based rule check plugins and can enhance
their policies with custom checks. This would be useful for example to
integrate with a in-house policy server.


Example code - HttpCheck
========================

.. note::

    Full source located at :example:`_external.py`

.. literalinclude:: ../../../oslo_policy/_external.py
    :language: python
    :linenos:
    :lines: 28-64
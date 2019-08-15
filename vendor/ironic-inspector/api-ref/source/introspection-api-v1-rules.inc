.. -*- rst -*-

===================
Introspection Rules
===================

Simple JSON-based DSL to define rules, which run during introspection.
See `<https://docs.openstack.org/ironic-inspector/latest/user/usage.html#introspection-rules>`_
for more information on rules.

Create Introspection Rule
=========================

.. rest_method::  POST /v1/rules

Create a new introspection rule.

Normal response codes:

* 200 - OK for API version < 1.6
* 201 - OK for API version 1.6 and higher

Error codes:

* 400 - wrong rule format

Request
-------

.. rest_parameters:: parameters.yaml

    - uuid: uuid
    - conditions: conditions
    - actions: actions
    - description: description


**Example creating rule request:**

.. literalinclude:: samples/api-v1-create-rule-request.json
   :language: javascript

Response
--------

The response will contain full rule object, also ``condition``
section may contain additional default fields, like ``invert``,
``multiple`` and ``field``, see ` Conditions https://docs.openstack.org/ironic-inspector/latest/user/usage.html#conditions>`_


.. rest_parameters:: parameters.yaml

    - uuid: uuid
    - conditions: conditions
    - actions: actions
    - description: description

**Example JSON representation:**

.. literalinclude:: samples/api-v1-create-rule-response.json
   :language: javascript


Get Introspection Rules
=======================

.. rest_method::  GET /v1/rules

List all introspection rules

Normal response codes: 200

Response
--------

.. rest_parameters:: parameters.yaml

    - uuid: uuid
    - description: description
    - links: links

**Example JSON representation:**

.. literalinclude:: samples/api-v1-get-rules-response.json
   :language: javascript


Get Introspection Rule
======================

.. rest_method::  GET /v1/rules/{uuid}

Get one introspection rule by its ``uuid``

Normal response codes: 200

Error codes:

* 404 - rule not found

Request
-------

.. rest_parameters:: parameters.yaml

    - uuid: uuid


Response
--------

The response will contain full rule object:

.. rest_parameters:: parameters.yaml

    - uuid: uuid
    - conditions: conditions
    - actions: actions
    - description: description

**Example JSON representation:**

.. literalinclude:: samples/api-v1-get-rule-response.json
   :language: javascript


Delete Introspection Rules
==========================

.. rest_method::  DELETE /v1/rules

Delete all introspection rules

Normal response codes: 204


Delete Introspection Rule
=========================

.. rest_method::  DELETE /v1/rules/{uuid}

Delete introspection rule by ``uuid``.

Normal response codes: 204

Error codes:

* 404 - rule not found

Request
-------

.. rest_parameters:: parameters.yaml

    - uuid: uuid

.. -*- rst -*-

==================================
Node Introspection (introspection)
==================================

Start introspection, get introspection status are done through the
``/v1/introspection`` resource. There are also several sub-resources, which
allow further actions to be performed on introspection.

Start Introspection
===================

.. rest_method::  POST /v1/introspection/{node_id}

Initiate hardware introspection for node {node_id} . All power management
configuration for this node needs to be done prior to calling the endpoint.

In the case of missing or invalid authentication, the response code will be
401 and 403 respectively.
If Inspector doesn't find node {node_id}, it will return 404.

Normal response codes: 202

Error codes: 400, 401, 403, 404


Request
-------

.. rest_parameters:: parameters.yaml

   - node_id: node_id
   - manage_boot: manage_boot


List All Introspection statuses
===============================

.. rest_method::  GET /v1/introspection/

Returned status list is sorted by the ``started_at, uuid`` attribute pair,
newer items first.

In case missing or invalid authentication response code will be 401 and 403.

Normal response codes: 200

Error codes: 400, 401, 403

Request
-------

Status list may be paginated with these query string fields:

.. rest_parameters:: parameters.yaml

   - marker: marker
   - limit: limit


Response
--------

The response will contain a list of status objects:

.. rest_parameters:: parameters.yaml

   - error: error
   - finished: finished
   - finished_at: finished_at
   - links:  links
   - started_at: started_at
   - state: state
   - uuid: node_id


**Example JSON representation of an introspection:**

.. literalinclude:: samples/api-v1-get-introspections-response.json
   :language: javascript


Show Introspection status
=========================

.. rest_method::  GET /v1/introspection/{node_id}

Show node introspection status.

In case missing or invalid authentication response code will be 401 and 403.
If Inspector don't find node {node_id}, it will return 404.

Normal response codes: 200

Error codes: 400, 401, 403, 404

Request
-------

.. rest_parameters:: parameters.yaml

   - node_id: node_id


Response
--------

The response will contain the complete introspection info, like
start, finish time, introspection state, errors if any.

.. rest_parameters:: parameters.yaml

   - error: error
   - finished: finished
   - finished_at: finished_at
   - links: links
   - started_at: started_at
   - state: state
   - uuid: node_id

**Example JSON representation of an introspection:**

.. literalinclude:: samples/api-v1-get-introspection-response.json
   :language: javascript



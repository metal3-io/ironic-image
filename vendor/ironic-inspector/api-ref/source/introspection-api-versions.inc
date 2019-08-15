.. -*- rst -*-

============
API versions
============

Concepts
========

In order to bring new features to users over time, the Ironic
Inspector API supports versioning. There are two kinds of versions:

- ``major versions``, which have dedicated urls.
- ``microversions``, which can be requested through the use of the
  ``X-OpenStack-Ironic-Inspector-API-Version`` header.

The Version APIs work differently from other APIs as they *do not* require authentication.

All API requests support the ``X-OpenStack-Ironic-Inspector-API-Version`` header.
This header SHOULD be supplied with every request; in the absence of this header,
server will default to current supported version in all responses.

List API versions
=================

.. rest_method::  GET /

This fetches all the information about all known major API versions in the
deployment. Links to more specific information will be provided for each major
API version, as well as information about supported min and max microversions.

Normal response codes: 200

Request
-------

Response Example
----------------

.. rest_parameters::  parameters.yaml

    - versions: versions
    - id: id
    - links: links
    - status: status

    - x-openstack-ironic-api-min-version: x-openstack-ironic-inspector-api-minimum-version
    - x-openstack-ironic-api-max-version: x-openstack-ironic-inspector-api-maximum-version

.. literalinclude:: samples/api-root-response.json
   :language: javascript


Show v1 API
===========

.. rest_method::  GET /v1/

Show all the resources within the Ironic Inspector v1 API.

Normal response codes: 200

Request
-------

Response Example
----------------

.. rest_parameters::  parameters.yaml

    - resources: resources
    - links: links
    - href: href
    - rel: rel
    - name: name

    - x-openstack-ironic-api-min-version: x-openstack-ironic-inspector-api-minimum-version
    - x-openstack-ironic-api-max-version: x-openstack-ironic-inspector-api-maximum-version

.. literalinclude:: samples/api-v1-root-response.json
   :language: javascript

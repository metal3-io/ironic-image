..
      Copyright 2014 IBM Corp

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _middleware:

================
Audit middleware
================

The Keystone middleware library provides an optional WSGI middleware filter
which allows the ability to audit API requests for each component of OpenStack.

The audit middleware filter utilises environment variables to build the CADF
event.

.. figure:: ./images/audit.png
   :width: 100%
   :align: center
   :alt: Figure 1: Audit middleware in Nova pipeline

The figure above shows the middleware in Nova's pipeline.

Enabling audit middleware
=========================
To enable auditing, oslo.messaging_ should be installed. If not, the middleware
will log the audit event instead. Auditing can be enabled for a specific
project by editing the project's api-paste.ini file to include the following
filter definition:

::

   [filter:audit]
   paste.filter_factory = keystonemiddleware.audit:filter_factory
   audit_map_file = /etc/nova/api_audit_map.conf

The filter should be included after Keystone middleware's auth_token middleware
so it can utilise environment variables set by auth_token. Below is an example
using Nova's WSGI pipeline::

   [composite:openstack_compute_api_v2]
   use = call:nova.api.auth:pipeline_factory
   noauth = faultwrap sizelimit noauth ratelimit osapi_compute_app_v2
   keystone = faultwrap sizelimit authtoken keystonecontext ratelimit audit osapi_compute_app_v2
   keystone_nolimit = faultwrap sizelimit authtoken keystonecontext audit osapi_compute_app_v2

.. _oslo.messaging: http://www.github.com/openstack/oslo.messaging

Configure audit middleware
==========================
To properly audit api requests, the audit middleware requires an
api_audit_map.conf to be defined. The project's corresponding
api_audit_map.conf file is included in the `pyCADF library`_.

The location of the mapping file should be specified explicitly by adding the
path to the 'audit_map_file' option of the filter definition::

   [filter:audit]
   paste.filter_factory = keystonemiddleware.audit:filter_factory
   audit_map_file = /etc/nova/api_audit_map.conf

Additional options can be set::

   [filter:audit]
   paste.filter_factory = pycadf.middleware.audit:filter_factory
   audit_map_file = /etc/nova/api_audit_map.conf
   service_name = test # opt to set HTTP_X_SERVICE_NAME environ variable
   ignore_req_list = GET,POST # opt to ignore specific requests

Audit middleware can be configured to use its own exclusive notification driver
and topic(s) value. This can be useful when the service is already using oslo
messaging notifications and wants to use a different driver for auditing e.g.
service has existing notifications sent to queue via 'messagingv2' and wants to
send audit notifications to a log file via 'log' driver. Example shown below::

   [audit_middleware_notifications]
   driver = log

When audit events are sent via 'messagingv2' or 'messaging', middleware can
specify a transport URL if its transport URL needs to be different from the
service's own messaging transport setting. Other Transport related settings are
read from oslo messaging sections defined in service configuration e.g.
'oslo_messaging_rabbit'. Example shown below::

   [audit_middleware_notifications]
   driver = messaging
   transport_url = rabbit://user2:passwd@host:5672/another_virtual_host

.. _pyCADF library: https://github.com/openstack/pycadf/tree/master/etc/pycadf

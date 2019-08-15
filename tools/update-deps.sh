#!/bin/bash

set -xe

source $(dirname $0)/common.sh

update_dep_from_pypi alembic 1.0.11
update_dep_from_pypi automaton 1.16.0
update_dep_from_pypi eventlet 0.25.0
update_dep_from_pypi futurist 1.8.1
update_dep_from_pypi ironic-lib 2.19.0
update_dep_from_pypi Jinja2 2.10.1
update_dep_from_pypi jsonpatch 1.24
update_dep_from_pypi jsonschema 2.6.0
update_dep_from_pypi keystoneauth1 3.16.0
update_dep_from_pypi keystonemiddleware 7.0.0
update_dep_from_pypi openstacksdk 0.33.0
update_dep_from_pypi os-traits 0.16.0
update_dep_from_pypi oslo.concurrency 3.29.1
update_dep_from_pypi oslo.config 6.11.0
update_dep_from_pypi oslo.context 2.22.1
update_dep_from_pypi oslo.db 5.0.1
update_dep_from_pypi oslo.i18n 3.23.1
update_dep_from_pypi oslo.log 3.44.0
update_dep_from_pypi oslo.messaging 10.0.0
update_dep_from_pypi oslo.middleware 3.38.1
update_dep_from_pypi oslo.policy 2.3.0
update_dep_from_pypi oslo.reports 1.29.2
update_dep_from_pypi oslo.rootwrap 5.16.0
update_dep_from_pypi oslo.serialization 2.29.1
update_dep_from_pypi oslo.service 1.40.0
update_dep_from_pypi oslo.upgradecheck 0.3.1
update_dep_from_pypi oslo.utils 3.41.0
update_dep_from_pypi oslo.versionedobjects 1.36.0
update_dep_from_pypi osprofiler 2.8.1
update_dep_from_pypi pbr 5.4.2
update_dep_from_pypi pecan 1.3.3
update_dep_from_pypi psutil 5.6.3
update_dep_from_pypi pysendfile 2.0.1
update_dep_from_pypi python-cinderclient 4.2.1
update_dep_from_pypi python-glanceclient 2.16.0
update_dep_from_pypi python-neutronclient 6.12.0
update_dep_from_pypi python-swiftclient 3.8.0
update_dep_from_pypi pytz 2019.2
update_dep_from_pypi requests 2.22.0
update_dep_from_pypi retrying 1.3.3
update_dep_from_pypi rfc3986 1.3.2
update_dep_from_pypi six 1.12.0
update_dep_from_pypi SQLAlchemy 1.3.6
update_dep_from_pypi stevedore 1.30.1
update_dep_from_pypi tooz 1.66.1
update_dep_from_pypi WebOb 1.8.5
update_dep_from_pypi WSME 0.9.3

update_dep_from_git ironic https://opendev.org/openstack/ironic 33acfa2d1b6b73e45b457e2664b8d808427bcb49
update_dep_from_git ironic-inspector https://opendev.org/openstack/ironic-inspector master

#!/usr/bin/env python
#
# Copyright (c) 2015 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""A usage example of Oslo Context with user_identity

This example requires the following modules to be installed.

$ pip install oslo.context oslo.log

More information can be found at:

  https://docs.openstack.org/oslo.context/latest/user/index.html
"""

from oslo_config import cfg
from oslo_context import context
from oslo_log import log as logging

CONF = cfg.CONF
DOMAIN = "demo"

logging.register_options(CONF)
CONF.logging_user_identity_format = "%(user)s/%(tenant)s@%(project_domain)s"
logging.setup(CONF, DOMAIN)

LOG = logging.getLogger(__name__)

LOG.info("Message without context")
# ids in Openstack are 32 characters long
# For readability a shorter id value is used
context.RequestContext(request_id='req-abc',
                       user='6ce90b4d',
                       tenant='d6134462',
                       project_domain='a6b9360e')
LOG.info("Message with context")

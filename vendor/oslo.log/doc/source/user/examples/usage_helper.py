# Copyright (c) 2016 OpenStack Foundation
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

"""A usage example with helper debugging of minimum Oslo Logging

This example requires the following package to be installed.

$ pip install oslo.log

Additional Oslo packages installed include oslo.config, oslo.context,
oslo.i18n, oslo.serialization and oslo.utils.

More information about Oslo Logging can be found at:

  https://docs.openstack.org/oslo.log/latest/user/index.html
"""

# Use default Python logging to display running output
import logging as py_logging
from oslo_config import cfg
from oslo_log import log as logging


LOG = py_logging.getLogger(__name__)
CONF = cfg.CONF
DOMAIN = "demo"


def prepare():
    """Prepare Oslo Logging (2 or 3 steps)

    Use of Oslo Logging involves the following:

    * logging.register_options
    * logging.set_defaults (optional)
    * logging.setup
    """

    LOG.debug("Prepare Oslo Logging")

    LOG.info("Size of configuration options before %d", len(CONF))

    # Required step to register common, logging and generic configuration
    # variables
    logging.register_options(CONF)

    LOG.info("Size of configuration options after %d", len(CONF))

    # Optional step to set new defaults if necessary for
    # * logging_context_format_string
    # * default_log_levels
    #
    # These variables default to respectively:
    #
    #  import oslo_log
    #  oslo_log._options.DEFAULT_LOG_LEVELS
    #  oslo_log._options.log_opts[0].default
    #

    custom_log_level_defaults = logging.get_default_log_levels() + [
        'dogpile=INFO',
        'routes=INFO'
        ]

    logging.set_defaults(default_log_levels=custom_log_level_defaults)

    # NOTE: We cannot show the contents of the CONF object
    # after register_options() because accessing this caches
    # the default_log_levels subsequently modified with set_defaults()
    LOG.info("List of Oslo Logging configuration options and current values")
    LOG.info("=" * 80)
    for c in CONF:
        LOG.info("%s = %s" % (c, CONF[c]))
    LOG.info("=" * 80)

    # Required setup based on configuration and domain
    logging.setup(CONF, DOMAIN)


if __name__ == '__main__':
    py_logging.basicConfig(level=py_logging.DEBUG)

    prepare()
    # NOTE: These examples do not demonstration Oslo i18n messages
    LOG.info("Welcome to Oslo Logging")
    LOG.debug("A debugging message")
    LOG.warning("A warning occurred")
    LOG.error("An error occurred")
    try:
        raise Exception("This is exceptional")
    except Exception:
        LOG.exception("An Exception occurred")

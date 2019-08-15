# Copyright 2015 Hewlett-Packard Development Company, L.P.
# Copyright 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Generate a sample policy file."""

import os

from sphinx.util import logging

from oslo_policy import generator

LOG = logging.getLogger(__name__)


def generate_sample(app):
    """Generate a sample policy file."""

    if not app.config.policy_generator_config_file:
        LOG.warning("No policy_generator_config_file is specified, "
                    "skipping sample policy generation")
        return

    if isinstance(app.config.policy_generator_config_file, list):
        for config_file, base_name in app.config.policy_generator_config_file:
            if base_name is None:
                base_name = _get_default_basename(config_file)
            _generate_sample(app, config_file, base_name)
    else:
        _generate_sample(app,
                         app.config.policy_generator_config_file,
                         app.config.sample_policy_basename)


def _get_default_basename(config_file):
    return os.path.splitext(os.path.basename(config_file))[0]


def _generate_sample(app, policy_file, base_name):

    def info(msg):
        LOG.info('[%s] %s' % (__name__, msg))

    # If we are given a file that isn't an absolute path, look for it
    # in the source directory if it doesn't exist.
    candidates = [
        policy_file,
        os.path.join(app.srcdir, policy_file,),
    ]
    for c in candidates:
        if os.path.isfile(c):
            info('reading config generator instructions from %s' % c)
            config_path = c
            break
    else:
        raise ValueError(
            "Could not find policy_generator_config_file %r" %
            app.config.policy_generator_config_file)

    if base_name:
        out_file = os.path.join(app.srcdir, base_name) + '.policy.yaml.sample'
        if not os.path.isdir(os.path.dirname(os.path.abspath(out_file))):
            os.mkdir(os.path.dirname(os.path.abspath(out_file)))
    else:
        file_name = 'sample.policy.yaml'
        out_file = os.path.join(app.srcdir, file_name)

    info('writing sample policy to %s' % out_file)
    generator.generate_sample(args=['--config-file', config_path,
                                    '--output-file', out_file])


def setup(app):
    app.add_config_value('policy_generator_config_file', None, 'env')
    app.add_config_value('sample_policy_basename', None, 'env')
    app.connect('builder-inited', generate_sample)

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

import uuid

import mock
from oslo_config import cfg
from oslotest import createfile

from keystonemiddleware.auth_token import _auth
from keystonemiddleware.auth_token import _opts
from keystonemiddleware.tests.unit.auth_token import base


def conf_get(app, *args, **kwargs):
    return app._conf.get(*args, **kwargs)


class TestAuthPluginLocalOsloConfig(base.BaseAuthTokenTestCase):

    def setUp(self):
        super(TestAuthPluginLocalOsloConfig, self).setUp()
        self.project = uuid.uuid4().hex

        # NOTE(cdent): The options below are selected from those
        # which are statically registered by auth_token middleware
        # in the 'keystone_authtoken' group. Additional options, from
        # plugins, are registered dynamically so must not be used here.
        self.oslo_options = {
            'www_authenticate_uri': uuid.uuid4().hex,
            'identity_uri': uuid.uuid4().hex,
        }

        self.local_oslo_config = cfg.ConfigOpts()
        self.local_oslo_config.register_group(
            cfg.OptGroup(name='keystone_authtoken'))

        self.local_oslo_config.register_opts(_opts._OPTS,
                                             group='keystone_authtoken')
        self.local_oslo_config.register_opts(_auth.OPTS,
                                             group='keystone_authtoken')

        for option, value in self.oslo_options.items():
            self.local_oslo_config.set_override(option, value,
                                                'keystone_authtoken')
        self.local_oslo_config(args=[], project=self.project)

        self.file_options = {
            'auth_type': 'password',
            'www_authenticate_uri': uuid.uuid4().hex,
            'password': uuid.uuid4().hex,
        }

        content = ("[DEFAULT]\n"
                   "test_opt=15\n"
                   "[keystone_authtoken]\n"
                   "auth_type=%(auth_type)s\n"
                   "www_authenticate_uri=%(www_authenticate_uri)s\n"
                   "auth_url=%(www_authenticate_uri)s\n"
                   "password=%(password)s\n" % self.file_options)

        self.conf_file_fixture = self.useFixture(
            createfile.CreateFileWithContent(self.project, content))

    def _create_app(self, conf, project_version=None):
        if not project_version:
            project_version = uuid.uuid4().hex

        fake_pkg_resources = mock.Mock()
        fake_pkg_resources.get_distribution().version = project_version

        body = uuid.uuid4().hex
        with mock.patch('keystonemiddleware._common.config.pkg_resources',
                        new=fake_pkg_resources):
            # use_global_conf is poorly named. What it means is
            # don't use the config created in test setUp.
            return self.create_simple_middleware(body=body, conf=conf,
                                                 use_global_conf=True)

    def test_project_in_local_oslo_configuration(self):
        conf = {'oslo_config_project': self.project,
                'oslo_config_file': self.conf_file_fixture.path}
        app = self._create_app(conf)
        for option in self.file_options:
            self.assertEqual(self.file_options[option],
                             conf_get(app, option), option)

    def test_passed_oslo_configuration(self):
        conf = {'oslo_config_config': self.local_oslo_config}
        app = self._create_app(conf)
        for option in self.oslo_options:
            self.assertEqual(self.oslo_options[option],
                             conf_get(app, option))

    def test_passed_oslo_configuration_with_deprecated_ones(self):
        deprecated_opt = cfg.IntOpt('test_opt', deprecated_for_removal=True)
        cfg.CONF.register_opt(deprecated_opt)
        cfg.CONF(args=[],
                 default_config_files=[self.conf_file_fixture.path])
        conf = {'oslo_config_config': cfg.CONF}

        # success to init AuthProtocol
        self._create_app(conf)

    def test_passed_oslo_configuration_wins(self):
        """oslo_config_config has precedence over oslo_config_project."""
        conf = {'oslo_config_project': self.project,
                'oslo_config_config': self.local_oslo_config,
                'oslo_config_file': self.conf_file_fixture.path}
        app = self._create_app(conf)
        for option in self.oslo_options:
            self.assertEqual(self.oslo_options[option],
                             conf_get(app, option))
        self.assertNotEqual(self.file_options['www_authenticate_uri'],
                            conf_get(app, 'www_authenticate_uri'))

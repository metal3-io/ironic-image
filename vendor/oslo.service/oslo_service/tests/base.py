# Copyright 2015 Mirantis Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import fixtures
from oslo_config import fixture as config
from oslotest import base as test_base

from oslo_service import _options
from oslo_service import sslutils


class ServiceBaseTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(ServiceBaseTestCase, self).setUp()
        self.conf_fixture = self.useFixture(config.Config())
        self.conf_fixture.register_opts(_options.eventlet_backdoor_opts)
        self.conf_fixture.register_opts(_options.service_opts)
        self.conf_fixture.register_opts(_options.ssl_opts,
                                        sslutils.config_section)
        self.conf_fixture.register_opts(_options.periodic_opts)
        self.conf_fixture.register_opts(_options.wsgi_opts)

        self.conf = self.conf_fixture.conf
        self.config = self.conf_fixture.config
        self.conf(args=[], default_config_files=[])

    def get_new_temp_dir(self):
        """Create a new temporary directory.

        :returns: fixtures.TempDir
        """
        return self.useFixture(fixtures.TempDir())

    def get_default_temp_dir(self):
        """Create a default temporary directory.

        Returns the same directory during the whole test case.

        :returns: fixtures.TempDir
        """
        if not hasattr(self, '_temp_dir'):
            self._temp_dir = self.get_new_temp_dir()
        return self._temp_dir

    def get_temp_file_path(self, filename, root=None):
        """Returns an absolute path for a temporary file.

        If root is None, the file is created in default temporary directory. It
        also creates the directory if it's not initialized yet.

        If root is not None, the file is created inside the directory passed as
        root= argument.

        :param filename: filename
        :type filename: string
        :param root: temporary directory to create a new file in
        :type root: fixtures.TempDir
        :returns: absolute file path string
        """
        root = root or self.get_default_temp_dir()
        return root.join(filename)

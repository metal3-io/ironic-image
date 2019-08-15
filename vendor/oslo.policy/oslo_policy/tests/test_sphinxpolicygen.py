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

import mock
from oslotest import base

from oslo_policy import sphinxpolicygen


class SingleSampleGenerationTest(base.BaseTestCase):

    @mock.patch('os.path.isdir')
    @mock.patch('os.path.isfile')
    @mock.patch('oslo_policy.generator.generate_sample')
    def test_sample_gen_with_single_config_file(self, sample, isfile, isdir):
        isfile.side_effect = [False, True]
        isdir.return_value = True

        config = mock.Mock(policy_generator_config_file='nova.conf',
                           sample_policy_basename='nova')
        app = mock.Mock(srcdir='/opt/nova', config=config)
        sphinxpolicygen.generate_sample(app)

        sample.assert_called_once_with(args=[
            '--config-file', '/opt/nova/nova.conf',
            '--output-file', '/opt/nova/nova.policy.yaml.sample'])

    @mock.patch('os.path.isdir')
    @mock.patch('os.path.isfile')
    @mock.patch('oslo_policy.generator.generate_sample')
    def test_sample_gen_with_single_config_file_no_base(self, sample, isfile,
                                                        isdir):
        isfile.side_effect = [False, True]
        isdir.return_value = True

        config = mock.Mock(policy_generator_config_file='nova.conf',
                           sample_policy_basename=None)
        app = mock.Mock(srcdir='/opt/nova', config=config)
        sphinxpolicygen.generate_sample(app)

        sample.assert_called_once_with(args=[
            '--config-file', '/opt/nova/nova.conf',
            '--output-file', '/opt/nova/sample.policy.yaml'])

    @mock.patch('os.path.isdir')
    @mock.patch('os.path.isfile')
    @mock.patch('oslo_policy.generator.generate_sample')
    def test_sample_gen_with_multiple_config_files(self, sample, isfile,
                                                   isdir):
        # Tests the scenario that policy_generator_config_file is a list
        # of two-item tuples of the config file name and policy basename.
        isfile.side_effect = [False, True] * 2
        isdir.return_value = True

        config = mock.Mock(policy_generator_config_file=[
            ('nova.conf', 'nova'),
            ('placement.conf', 'placement')])
        app = mock.Mock(srcdir='/opt/nova', config=config)
        sphinxpolicygen.generate_sample(app)

        sample.assert_has_calls([
            mock.call(args=[
                '--config-file', '/opt/nova/nova.conf',
                '--output-file', '/opt/nova/nova.policy.yaml.sample']),
            mock.call(args=[
                '--config-file', '/opt/nova/placement.conf',
                '--output-file', '/opt/nova/placement.policy.yaml.sample'])])

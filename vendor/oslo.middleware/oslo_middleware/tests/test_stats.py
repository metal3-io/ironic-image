# Copyright (c) 2016 Cisco Systems
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

import uuid

import mock
from oslotest import base as test_base
import statsd
import webob.dec
import webob.exc

from oslo_middleware import stats


class TestStaticMethods(test_base.BaseTestCase):

    def test_removes_uuid(self):
        # Generate a long-format UUID (standard form).
        id = str(uuid.uuid4())
        path = "foo.{uuid}.bar".format(uuid=id)
        stat = stats.StatsMiddleware.strip_uuid(path)
        self.assertEqual("foo.bar", stat)

    def test_removes_short_uuid(self):
        id = uuid.uuid4().hex
        path = "foo.{uuid}.bar".format(uuid=id)
        stat = stats.StatsMiddleware.strip_short_uuid(path)
        self.assertEqual("foo.bar", stat)

    def test_strips_dots_from_version(self):
        path = "/v1.2/foo.bar/bar.foo"
        stat = stats.StatsMiddleware.strip_dot_from_version(path)
        self.assertEqual("/v12/foo.bar/bar.foo", stat)


class TestStatsMiddleware(test_base.BaseTestCase):

    def setUp(self):
        super(TestStatsMiddleware, self).setUp()
        self.patch(statsd, 'StatsClient', mock.MagicMock())

    def make_stats_middleware(self, stat_name=None, stats_host=None,
                              remove_uuid=False, remove_short_uuid=False):
        if stat_name is None:
            stat_name = uuid.uuid4().hex
        if stats_host is None:
            stats_host = uuid.uuid4().hex

        conf = dict(
            name=stat_name,
            stats_host=stats_host,
            remove_uuid=remove_uuid,
            remove_short_uuid=remove_short_uuid,
        )

        @webob.dec.wsgify
        def fake_application(req):
            return 'Hello, World'

        return stats.StatsMiddleware(fake_application, conf)

    def perform_request(self, app, path, method):
        req = webob.Request.blank(path, method=method)
        return req.get_response(app)

    def test_sends_counter_to_statsd(self):
        app = self.make_stats_middleware()
        path = '/test/foo/bar'

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}.{path}".format(
            name=app.stat_name, method='GET',
            path=path.lstrip('/').replace('/', '.'))
        app.statsd.timer.assert_called_once_with(expected_stat)

    def test_strips_uuid_if_configured(self):
        app = self.make_stats_middleware(remove_uuid=True)
        random_uuid = str(uuid.uuid4())
        path = '/foo/{uuid}/bar'.format(uuid=random_uuid)

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}.foo.bar".format(
            name=app.stat_name, method='GET')
        app.statsd.timer.assert_called_once_with(expected_stat)

    def test_strips_short_uuid_if_configured(self):
        app = self.make_stats_middleware(remove_short_uuid=True)
        random_uuid = uuid.uuid4().hex
        path = '/foo/{uuid}/bar'.format(uuid=random_uuid)

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}.foo.bar".format(
            name=app.stat_name, method='GET')
        app.statsd.timer.assert_called_once_with(expected_stat)

    def test_strips_both_uuid_types_if_configured(self):
        app = self.make_stats_middleware(
            remove_uuid=True, remove_short_uuid=True)
        random_short_uuid = uuid.uuid4().hex
        random_uuid = str(uuid.uuid4())
        path = '/foo/{uuid}/bar/{short_uuid}'.format(
            uuid=random_uuid, short_uuid=random_short_uuid)

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}.foo.bar".format(
            name=app.stat_name, method='GET')
        app.statsd.timer.assert_called_once_with(expected_stat)

    def test_always_mutates_version_id(self):
        app = self.make_stats_middleware()
        path = '/v2.1/foo/bar'

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}.v21.foo.bar".format(
            name=app.stat_name, method='GET')
        app.statsd.timer.assert_called_once_with(expected_stat)

    def test_empty_path_has_sane_stat_name(self):
        app = self.make_stats_middleware()
        path = '/'

        self.perform_request(app, path, 'GET')

        expected_stat = "{name}.{method}".format(
            name=app.stat_name, method='GET')
        app.statsd.timer.assert_called_once_with(expected_stat)

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

import mock

from keystonemiddleware import audit
from keystonemiddleware.tests.unit.audit import base


class AuditNotifierConfigTest(base.BaseAuditMiddlewareTest):

    def test_conf_middleware_log_and_default_as_messaging(self):
        self.cfg.config(driver='log',
                        group='audit_middleware_notifications')
        app = self.create_simple_app()
        with mock.patch('oslo_messaging.notify._impl_log.LogDriver.notify',
                        side_effect=Exception('error')) as driver:
            app.get('/foo/bar', extra_environ=self.get_environ_header())
            # audit middleware conf has 'log' make sure that driver is invoked
            # and not the one specified in DEFAULT section
            self.assertTrue(driver.called)

    def test_conf_middleware_log_and_oslo_msg_as_messaging(self):
        self.cfg.config(driver=['messaging'],
                        group='oslo_messaging_notifications')
        self.cfg.config(driver='log',
                        group='audit_middleware_notifications')

        app = self.create_simple_app()
        with mock.patch('oslo_messaging.notify._impl_log.LogDriver.notify',
                        side_effect=Exception('error')) as driver:
            app.get('/foo/bar', extra_environ=self.get_environ_header())
            # audit middleware conf has 'log' make sure that driver is invoked
            # and not the one specified in oslo_messaging_notifications section
            self.assertTrue(driver.called)

    def test_conf_middleware_messaging_and_oslo_msg_as_log(self):
        self.cfg.config(driver=['log'], group='oslo_messaging_notifications')
        self.cfg.config(driver='messaging',
                        group='audit_middleware_notifications')
        app = self.create_simple_app()
        with mock.patch('oslo_messaging.notify.messaging.MessagingDriver'
                        '.notify',
                        side_effect=Exception('error')) as driver:
            # audit middleware has 'messaging' make sure that driver is invoked
            # and not the one specified in oslo_messaging_notifications section
            app.get('/foo/bar', extra_environ=self.get_environ_header())
            self.assertTrue(driver.called)

    def test_with_no_middleware_notification_conf(self):
        self.cfg.config(driver=['messaging'],
                        group='oslo_messaging_notifications')
        self.cfg.config(driver=None, group='audit_middleware_notifications')

        app = self.create_simple_app()
        with mock.patch('oslo_messaging.notify.messaging.MessagingDriver'
                        '.notify',
                        side_effect=Exception('error')) as driver:
            # audit middleware section is not set. So driver needs to be
            # invoked from oslo_messaging_notifications section.
            app.get('/foo/bar', extra_environ=self.get_environ_header())
            self.assertTrue(driver.called)

    @mock.patch('oslo_messaging.get_notification_transport')
    def test_conf_middleware_messaging_and_transport_set(self, m):
        transport_url = 'rabbit://me:passwd@host:5672/virtual_host'
        self.cfg.config(driver='messaging',
                        transport_url=transport_url,
                        group='audit_middleware_notifications')

        self.create_simple_middleware()
        self.assertTrue(m.called)
        # make sure first call kwarg 'url' is same as provided transport_url
        self.assertEqual(transport_url, m.call_args_list[0][1]['url'])

    def test_do_not_use_oslo_messaging(self):
        self.cfg.config(use_oslo_messaging=False,
                        group='audit_middleware_notifications')
        audit_middleware = self.create_simple_middleware()

        # make sure it is using a local notifier instead of oslo_messaging
        self.assertTrue(
            isinstance(audit_middleware._notifier,
                       audit._notifier._LogNotifier))

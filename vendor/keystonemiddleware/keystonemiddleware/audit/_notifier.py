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

import os
import sys

try:
    import oslo_messaging
except ImportError:
    oslo_messaging = None


class _LogNotifier(object):

    def __init__(self, log):
        self._log = log

    def notify(self, context, event_type, payload):
        self._log.info('Event type: %(event_type)s, Context: %(context)s, '
                       'Payload: %(payload)s', {'context': context,
                                                'event_type': event_type,
                                                'payload': payload})


class _MessagingNotifier(object):

    def __init__(self, notifier):
        self._notifier = notifier

    def notify(self, context, event_type, payload):
        self._notifier.info(context, event_type, payload)


def create_notifier(conf, log):
    if oslo_messaging and conf.get('use_oslo_messaging'):
        transport = oslo_messaging.get_notification_transport(
            conf.oslo_conf_obj,
            url=conf.get('transport_url'))

        notifier = oslo_messaging.Notifier(
            transport,
            os.path.basename(sys.argv[0]),
            driver=conf.get('driver'),
            topics=conf.get('topics'))

        return _MessagingNotifier(notifier)

    else:
        return _LogNotifier(log)

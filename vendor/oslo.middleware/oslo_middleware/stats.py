# Copyright (c) 2016 Cisco Systems
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

import logging
import re

import statsd
import webob.dec

from oslo_middleware import base

LOG = logging.getLogger(__name__)
VERSION_REGEX = re.compile(r"/(v[0-9]{1}\.[0-9]{1})")
UUID_REGEX = re.compile(
    r'.*(\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}).*a',
    re.IGNORECASE)
# UUIDs without the - char, used in some places in Nova URLs.
SHORT_UUID_REGEX = re.compile(r'.*(\.[0-9a-fA-F]{32}).*')


class StatsMiddleware(base.ConfigurableMiddleware):
    """Send stats to statsd based on API requests.

    Examines the URL path and request method, and sends a stat count and timer
    to a statsd host based on the path/method.

    If your statsd is configured to send stats to Graphite, you'll end up with
    stat names of the form::

        timer.<appname>.<METHOD>.<path>.<from>.<url>

    Note that URLs with versions in them (pretty much all of Openstack)
    are always processed to replace the dot with _, so for example v2.0
    becomes v2_0, and v1.1 becomes v1_1, since a dot '.' has special
    meaning in Graphite.

    The original StatsD is written in nodejs. If you want a Python
    implementation, install Bucky instead as it's a drop-in replacement
    (and much nicer IMO).

    The Paste config must contain some parameters. Configure a filter like
    this::

        [filter:stats]
        paste.filter_factory = oslo_middleware.stats:StatsMiddleware.factory
        name = my_application_name  # e.g. 'glance'
        stats_host = my_statsd_host.example.com
        # Optional args to further process the stat name that's generated:
        remove_uuid = True
        remove_short_uuid = True
        # The above uuid processing is required in, e.g. Nova, if you want to
        # collect generic stats rather than one per server instance.
    """

    def __init__(self, application, conf):
        super(StatsMiddleware, self).__init__(application, conf)
        self.application = application
        self.stat_name = conf.get('name')
        if self.stat_name is None:
            raise AttributeError('name must be specified')
        self.stats_host = conf.get('stats_host')
        if self.stats_host is None:
            raise AttributeError('stats_host must be specified')
        self.remove_uuid = conf.get('remove_uuid', False)
        self.remove_short_uuid = conf.get('remove_short_uuid', False)
        self.statsd = statsd.StatsClient(self.stats_host)

    @staticmethod
    def strip_short_uuid(path):
        """Remove short-form UUID from supplied path.

        Only call after replacing slashes with dots in path.
        """
        match = SHORT_UUID_REGEX.match(path)
        if match is None:
            return path
        return path.replace(match.group(1), '')

    @staticmethod
    def strip_uuid(path):
        """Remove normal-form UUID from supplied path.

        Only call after replacing slashes with dots in path.
        """
        match = UUID_REGEX.match(path)
        if match is None:
            return path
        return path.replace(match.group(1), '')

    @staticmethod
    def strip_dot_from_version(path):
        # Replace vN.N with vNN.
        match = VERSION_REGEX.match(path)
        if match is None:
            return path
        return path.replace(match.group(1), match.group(1).replace('.', ''))

    @webob.dec.wsgify
    def __call__(self, request):
        path = request.path
        path = self.strip_dot_from_version(path)

        # Remove leading slash, if any, so we can be sure of the number
        # of dots just below.
        path = path.lstrip('/')

        stat = "{name}.{method}".format(
            name=self.stat_name, method=request.method)
        if path != '':
            stat += '.' + path.replace('/', '.')

        if self.remove_short_uuid:
            stat = self.strip_short_uuid(stat)

        if self.remove_uuid:
            stat = self.strip_uuid(stat)

        LOG.debug("Incrementing stat count %s", stat)
        with self.statsd.timer(stat):
            return request.get_response(self.application)

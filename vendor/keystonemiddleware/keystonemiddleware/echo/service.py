# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Run the echo service.

The echo service can be run on port 8000 by executing the following::

 $ python -m keystonemiddleware.echo

When the ``auth_token`` module authenticates a request, the echo service
will respond with all the environment variables presented to it by this
module.
"""

from wsgiref import simple_server

from oslo_serialization import jsonutils

from keystonemiddleware import auth_token


def echo_app(environ, start_response):
    """A WSGI application that echoes the CGI environment back to the user."""
    start_response('200 OK', [('Content-Type', 'application/json')])
    environment = dict((k, v) for k, v in environ.items()
                       if k.startswith('HTTP_X_'))
    yield jsonutils.dumps(environment)


class EchoService(object):
    """Runs an instance of the echo app on init."""

    def __init__(self):
        # hardcode any non-default configuration here
        conf = {'auth_protocol': 'http', 'admin_token': 'ADMIN'}
        app = auth_token.AuthProtocol(echo_app, conf)
        server = simple_server.make_server('', 8000, app)
        print('Serving on port 8000 (Ctrl+C to end)...')
        server.serve_forever()

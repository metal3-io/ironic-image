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

import argparse

from six.moves import SimpleHTTPServer  # noqa
from six.moves import socketserver
import webob

from oslo_middleware import healthcheck


class HttpHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        @webob.dec.wsgify
        def dummy_application(req):
            return 'test'
        app = healthcheck.Healthcheck(dummy_application, {'detailed': True})
        req = webob.Request.blank("/healthcheck", accept='text/html',
                                  method='GET')
        res = req.get_response(app)
        self.send_response(res.status_code)
        for header_name, header_value in res.headerlist:
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(res.body)
        self.wfile.close()


def positive_int(blob):
    value = int(blob)
    if value < 0:
        msg = "%r is not a positive integer" % blob
        raise argparse.ArgumentTypeError(msg)
    return value


def create_server(port=0):
    handler = HttpHandler
    server = socketserver.TCPServer(("", port), handler)
    return server


def main(args=None):
    """Runs a basic http server to show healthcheck functionality."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port",
                        help="Unused port to run the tiny"
                             " http server on (or zero to select a"
                             " random unused port)",
                        type=positive_int, required=True)
    args = parser.parse_args(args=args)
    server = create_server(args.port)
    print("Serving at port: %s" % server.server_address[1])
    server.serve_forever()


if __name__ == '__main__':
    main()

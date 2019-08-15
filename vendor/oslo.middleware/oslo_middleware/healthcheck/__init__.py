# Copyright 2011 OpenStack Foundation.
# All Rights Reserved.
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

import collections
import gc
import json
import platform
import socket
import sys
import traceback

from debtcollector import removals
import jinja2
from oslo_utils import reflection
from oslo_utils import strutils
from oslo_utils import timeutils
import six
import stevedore
import webob.dec
import webob.exc
import webob.response

try:
    import greenlet
except ImportError:
    greenlet = None

from oslo_middleware import base
from oslo_middleware.healthcheck import opts


def _find_objects(t):
    return [o for o in gc.get_objects() if isinstance(o, t)]


def _expand_template(contents, params):
    tpl = jinja2.Template(source=contents,
                          undefined=jinja2.StrictUndefined)
    return tpl.render(**params)


class Healthcheck(base.ConfigurableMiddleware):
    """Healthcheck application used for monitoring.

    It will respond 200 with "OK" as the body. Or a 503 with the reason as the
    body if one of the backends reports an application issue.

    This is useful for the following reasons:

    * Load balancers can 'ping' this url to determine service availability.
    * Provides an endpoint that is similar to 'mod_status' in apache which
      can provide details (or no details, depending on if configured) about
      the activity of the server.
    * *(and more)*

    Example requests/responses (**not** detailed mode)::

      $ curl -i -X HEAD "http://0.0.0.0:8775/healthcheck"
      HTTP/1.1 204 No Content
      Content-Type: text/plain; charset=UTF-8
      Content-Length: 0
      Date: Fri, 11 Sep 2015 18:55:08 GMT

      $ curl -i -X GET "http://0.0.0.0:8775/healthcheck"
      HTTP/1.1 200 OK
      Content-Type: text/plain; charset=UTF-8
      Content-Length: 2
      Date: Fri, 11 Sep 2015 18:55:43 GMT

      OK

      $ curl -X GET -i -H "Accept: application/json" "http://0.0.0.0:8775/healthcheck"
      HTTP/1.0 200 OK
      Date: Wed, 24 Aug 2016 06:09:58 GMT
      Content-Type: application/json
      Content-Length: 63

      {
          "detailed": false,
          "reasons": [
              "OK"
          ]
      }

      $ curl -X GET -i -H "Accept: text/html" "http://0.0.0.0:8775/healthcheck"
      HTTP/1.0 200 OK
      Date: Wed, 24 Aug 2016 06:10:42 GMT
      Content-Type: text/html; charset=UTF-8
      Content-Length: 239

      <HTML>
      <HEAD><TITLE>Healthcheck Status</TITLE></HEAD>
      <BODY>

      <H2>Result of 1 checks:</H2>
      <TABLE bgcolor="#ffffff" border="1">
      <TBODY>
      <TR>

      <TH>
      Reason
      </TH>
      </TR>
      <TR>
          <TD>OK</TD>
      </TR>
      </TBODY>
      </TABLE>
      <HR></HR>

      </BODY>

    Example requests/responses (**detailed** mode)::

       $ curl -X GET -i -H "Accept: application/json" "http://0.0.0.0:8775/healthcheck"
       HTTP/1.0 200 OK
       Date: Wed, 24 Aug 2016 06:11:59 GMT
       Content-Type: application/json
       Content-Length: 3480

       {
           "detailed": true,
           "gc": {
               "counts": [
                   293,
                   10,
                   5
               ],
               "threshold": [
                   700,
                   10,
                   10
               ]
           },
           "greenthreads": [
              ...
           ],
           "now": "2016-08-24 06:11:59.419267",
           "platform": "Linux-4.2.0-27-generic-x86_64-with-Ubuntu-14.04-trusty",
           "python_version": "2.7.6 (default, Jun 22 2015, 17:58:13) \\n[GCC 4.8.2]",
           "reasons": [
               {
                   "class": "HealthcheckResult",
                   "details": "Path '/tmp/dead' was not found",
                   "reason": "OK"
               }
           ],
           "threads": [
               ...
           ]
       }

       $ curl -X GET -i -H "Accept: text/html" "http://0.0.0.0:8775/healthcheck"
       HTTP/1.0 200 OK
       Date: Wed, 24 Aug 2016 06:36:07 GMT
       Content-Type: text/html; charset=UTF-8
       Content-Length: 6838

       <HTML>
       <HEAD><TITLE>Healthcheck Status</TITLE></HEAD>
       <BODY>
       <H1>Server status</H1>
       <B>Server hostname:</B><PRE>...</PRE>
       <B>Current time:</B><PRE>2016-08-24 06:36:07.302559</PRE>
       <B>Python version:</B><PRE>2.7.6 (default, Jun 22 2015, 17:58:13)
       [GCC 4.8.2]</PRE>
       <B>Platform:</B><PRE>Linux-4.2.0-27-generic-x86_64-with-Ubuntu-14.04-trusty</PRE>
       <HR></HR>
       <H2>Garbage collector:</H2>
       <B>Counts:</B><PRE>(77, 1, 6)</PRE>
       <B>Thresholds:</B><PRE>(700, 10, 10)</PRE>

       <HR></HR>
       <H2>Result of 1 checks:</H2>
       <TABLE bgcolor="#ffffff" border="1">
       <TBODY>
       <TR>
       <TH>
       Kind
       </TH>
       <TH>
       Reason
       </TH>
       <TH>
       Details
       </TH>

       </TR>
       <TR>
       <TD>HealthcheckResult</TD>
           <TD>OK</TD>
       <TD>Path &#39;/tmp/dead&#39; was not found</TD>
       </TR>
       </TBODY>
       </TABLE>
       <HR></HR>
       <H2>1 greenthread(s) active:</H2>
       <TABLE bgcolor="#ffffff" border="1">
       <TBODY>
       <TR>
           <TD><PRE>  File &#34;oslo_middleware/healthcheck/__main__.py&#34;, line 94, in &lt;module&gt;
           main()
         File &#34;oslo_middleware/healthcheck/__main__.py&#34;, line 90, in main
           server.serve_forever()
         ...
       </PRE></TD>
       </TR>
       </TBODY>
       </TABLE>
       <HR></HR>
       <H2>1 thread(s) active:</H2>
       <TABLE bgcolor="#ffffff" border="1">
       <TBODY>
       <TR>
           <TD><PRE>  File &#34;oslo_middleware/healthcheck/__main__.py&#34;, line 94, in &lt;module&gt;
           main()
         File &#34;oslo_middleware/healthcheck/__main__.py&#34;, line 90, in main
           server.serve_forever()
         ....
       </TR>
       </TBODY>
       </TABLE>
       </BODY>
       </HTML>

    Example of paste configuration:

    .. code-block:: ini

        [app:healthcheck]
        use = egg:oslo.middleware:healthcheck
        backends = disable_by_file
        disable_by_file_path = /var/run/nova/healthcheck_disable

        [pipeline:public_api]
        pipeline = healthcheck sizelimit [...] public_service

    Multiple filter sections can be defined if it desired to have
    pipelines with different healthcheck configuration, example:

    .. code-block:: ini

        [composite:public_api]
        use = egg:Paste#urlmap
        / = public_api_pipeline
        /healthcheck = healthcheck_public

        [composite:admin_api]
        use = egg:Paste#urlmap
        / = admin_api_pipeline
        /healthcheck = healthcheck_admin

        [pipeline:public_api_pipeline]
        pipeline = sizelimit [...] public_service

        [pipeline:admin_api_pipeline]
        pipeline = sizelimit [...] admin_service

        [app:healthcheck_public]
        use = egg:oslo.middleware:healthcheck
        backends = disable_by_file
        disable_by_file_path = /var/run/nova/healthcheck_public_disable

        [filter:healthcheck_admin]
        use = egg:oslo.middleware:healthcheck
        backends = disable_by_file
        disable_by_file_path = /var/run/nova/healthcheck_admin_disable
    """

    NAMESPACE = "oslo.middleware.healthcheck"
    HEALTHY_TO_STATUS_CODES = {
        True: webob.exc.HTTPOk.code,
        False: webob.exc.HTTPServiceUnavailable.code,
    }
    HEAD_HEALTHY_TO_STATUS_CODES = {
        True: webob.exc.HTTPNoContent.code,
        False: webob.exc.HTTPServiceUnavailable.code,
    }
    PLAIN_RESPONSE_TEMPLATE = """
{% for reason in reasons %}
{% if reason %}{{reason}}{% endif -%}
{% endfor %}
"""

    HTML_RESPONSE_TEMPLATE = """
<HTML>
<HEAD><TITLE>Healthcheck Status</TITLE></HEAD>
<BODY>
{% if detailed -%}
<H1>Server status</H1>
{% if hostname -%}
<B>Server hostname:</B><PRE>{{hostname|e}}</PRE>
{%- endif %}
<B>Current time:</B><PRE>{{now|e}}</PRE>
<B>Python version:</B><PRE>{{python_version|e}}</PRE>
<B>Platform:</B><PRE>{{platform|e}}</PRE>
<HR></HR>
<H2>Garbage collector:</H2>
<B>Counts:</B><PRE>{{gc.counts|e}}</PRE>
<B>Thresholds:</B><PRE>{{gc.threshold|e}}</PRE>
<HR></HR>
{%- endif %}
<H2>Result of {{results|length}} checks:</H2>
<TABLE bgcolor="#ffffff" border="1">
<TBODY>
<TR>
{% if detailed -%}
<TH>
Kind
</TH>
<TH>
Reason
</TH>
<TH>
Details
</TH>
{% else %}
<TH>
Reason
</TH>
{%- endif %}
</TR>
{% for result in results -%}
{% if result.reason -%}
<TR>
{% if detailed -%}
    <TD>{{result.class|e}}</TD>
{%- endif %}
    <TD>{{result.reason|e}}</TD>
{% if detailed -%}
    <TD>{{result.details|e}}</TD>
{%- endif %}
</TR>
{%- endif %}
{%- endfor %}
</TBODY>
</TABLE>
<HR></HR>
{% if detailed -%}
{% if greenthreads -%}
<H2>{{greenthreads|length}} greenthread(s) active:</H2>
<TABLE bgcolor="#ffffff" border="1">
<TBODY>
{% for stack in greenthreads -%}
<TR>
    <TD><PRE>{{stack|e}}</PRE></TD>
</TR>
{%- endfor %}
</TBODY>
</TABLE>
<HR></HR>
{%- endif %}
{% if threads -%}
<H2>{{threads|length}} thread(s) active:</H2>
<TABLE bgcolor="#ffffff" border="1">
<TBODY>
{% for stack in threads -%}
<TR>
    <TD><PRE>{{stack|e}}</PRE></TD>
</TR>
{%- endfor %}
</TBODY>
</TABLE>
{%- endif %}
{%- endif %}
</BODY>
</HTML>
"""

    def __init__(self, *args, **kwargs):
        super(Healthcheck, self).__init__(*args, **kwargs)
        self.oslo_conf.register_opts(opts.HEALTHCHECK_OPTS,
                                     group='healthcheck')
        self._path = self._conf_get('path')
        self._show_details = self._conf_get('detailed')
        self._backends = stevedore.NamedExtensionManager(
            self.NAMESPACE, self._conf_get('backends'),
            name_order=True, invoke_on_load=True,
            invoke_args=(self.oslo_conf, self.conf))
        self._accept_to_functor = collections.OrderedDict([
            # Order here matters...
            ('text/plain', self._make_text_response),
            ('text/html', self._make_html_response),
            ('application/json', self._make_json_response),
        ])
        self._accept_order = tuple(six.iterkeys(self._accept_to_functor))
        # When no accept type matches instead of returning 406 we will
        # always return text/plain (because sending an error from this
        # middleware actually can cause issues).
        self._default_accept = 'text/plain'
        self._ignore_path = False

    def _conf_get(self, key, group='healthcheck'):
        return super(Healthcheck, self)._conf_get(key, group=group)

    @removals.remove(
        message="The healthcheck middleware must now be configured as "
        "an application, not as a filter")
    @classmethod
    def factory(cls, global_conf, **local_conf):
        return super(Healthcheck, cls).factory(global_conf, **local_conf)

    @classmethod
    def app_factory(cls, global_conf, **local_conf):
        """Factory method for paste.deploy.

        :param global_conf: dict of options for all middlewares
                            (usually the [DEFAULT] section of the paste deploy
                            configuration file)
        :param local_conf: options dedicated to this middleware
                           (usually the option defined in the middleware
                           section of the paste deploy configuration file)
        """
        conf = global_conf.copy() if global_conf else {}
        conf.update(local_conf)
        o = cls(application=None, conf=conf)
        o._ignore_path = True
        return o

    @staticmethod
    def _get_threadstacks():
        threadstacks = []
        try:
            active_frames = sys._current_frames()
        except AttributeError:
            pass
        else:
            buf = six.StringIO()
            for stack in six.itervalues(active_frames):
                traceback.print_stack(stack, file=buf)
                threadstacks.append(buf.getvalue())
                buf.seek(0)
                buf.truncate()
        return threadstacks

    @staticmethod
    def _get_greenstacks():
        greenstacks = []
        if greenlet is not None:
            buf = six.StringIO()
            for gt in _find_objects(greenlet.greenlet):
                traceback.print_stack(gt.gr_frame, file=buf)
                greenstacks.append(buf.getvalue())
                buf.seek(0)
                buf.truncate()
        return greenstacks

    @staticmethod
    def _pretty_json_dumps(contents):
        return json.dumps(contents, indent=4, sort_keys=True)

    @staticmethod
    def _are_results_healthy(results):
        for result in results:
            if not result.available:
                return False
        return True

    def _make_text_response(self, results, healthy):
        params = {
            'reasons': [result.reason for result in results],
            'detailed': self._show_details,
        }
        body = _expand_template(self.PLAIN_RESPONSE_TEMPLATE, params)
        return (body.strip(), 'text/plain')

    def _make_json_response(self, results, healthy):
        if self._show_details:
            body = {
                'detailed': True,
                'python_version': sys.version,
                'now': str(timeutils.utcnow()),
                'platform': platform.platform(),
                'gc': {
                    'counts': gc.get_count(),
                    'threshold': gc.get_threshold(),
                },
            }
            reasons = []
            for result in results:
                reasons.append({
                    'reason': result.reason,
                    'details': result.details or '',
                    'class': reflection.get_class_name(result,
                                                       fully_qualified=False),
                })
            body['reasons'] = reasons
            body['greenthreads'] = self._get_greenstacks()
            body['threads'] = self._get_threadstacks()
        else:
            body = {
                'reasons': [result.reason for result in results],
                'detailed': False,
            }
        return (self._pretty_json_dumps(body), 'application/json')

    def _make_head_response(self, results, healthy):
        return ( "", "text/plain")

    def _make_html_response(self, results, healthy):
        try:
            hostname = socket.gethostname()
        except socket.error:
            hostname = None
        translated_results = []
        for result in results:
            translated_results.append({
                'details': result.details or '',
                'reason': result.reason,
                'class': reflection.get_class_name(result,
                                                   fully_qualified=False),
            })
        params = {
            'healthy': healthy,
            'hostname': hostname,
            'results': translated_results,
            'detailed': self._show_details,
            'now': str(timeutils.utcnow()),
            'python_version': sys.version,
            'platform': platform.platform(),
            'gc': {
                'counts': gc.get_count(),
                'threshold': gc.get_threshold(),
             },
             'threads': self._get_threadstacks(),
             'greenthreads': self._get_threadstacks(),
        }
        body = _expand_template(self.HTML_RESPONSE_TEMPLATE, params)
        return (body.strip(), 'text/html')

    @webob.dec.wsgify
    def process_request(self, req):
        if not self._ignore_path and req.path != self._path:
            return None
        results = [ext.obj.healthcheck(req.server_port)
                   for ext in self._backends]
        healthy = self._are_results_healthy(results)
        if req.method == "HEAD":
            functor = self._make_head_response
            status = self.HEAD_HEALTHY_TO_STATUS_CODES[healthy]
        else:
            status = self.HEALTHY_TO_STATUS_CODES[healthy]
            try:
                offers = req.accept.acceptable_offers(self._accept_order)
                accept_type = offers[0][0]
            except IndexError:
                accept_type = self._default_accept
            functor = self._accept_to_functor[accept_type]
        body, content_type = functor(results, healthy)
        return webob.response.Response(status=status, body=body,
                                       charset='UTF-8',
                                       content_type=content_type)

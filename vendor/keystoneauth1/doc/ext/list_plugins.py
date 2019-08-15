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

import inspect

from docutils import nodes
from docutils.parsers import rst
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList
from sphinx.util import logging
from sphinx.util.nodes import nested_parse_with_titles
from stevedore import extension

LOG = logging.getLogger(__name__)


class ListAuthPluginsDirective(rst.Directive):
    """Present a simple list of the plugins in a namespace."""

    option_spec = {
        'class': directives.class_option,
        'overline-style': directives.single_char_or_unicode,
        'underline-style': directives.single_char_or_unicode,
    }

    has_content = True

    def report_load_failure(mgr, ep, err):
        LOG.warning(u'Failed to load %s: %s' % (ep.module_name, err))

    def display_plugin(self, ext):
        overline_style = self.options.get('overline-style', '')
        underline_style = self.options.get('underline-style', '=')

        if overline_style:
            yield overline_style * len(ext.name)

        yield ext.name

        if underline_style:
            yield underline_style * len(ext.name)

        yield "\n"

        doc = inspect.getdoc(ext.obj)
        if doc:
            yield doc
            yield "\n"
            yield "------"

        yield "\n"

        for opt in ext.obj.get_options():
            yield ":%s: %s" % (opt.name, opt.help)

        yield "\n"

    def run(self):
        mgr = extension.ExtensionManager(
            'keystoneauth1.plugin',
            on_load_failure_callback=self.report_load_failure,
	    invoke_on_load=True,
        )

        result = ViewList()

        for name in sorted(mgr.names()):
            for line in self.display_plugin(mgr[name]):
                for l in line.splitlines():
                    result.append(l, mgr[name].entry_point.module_name)

        # Parse what we have into a new section.
        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, result, node)

        return node.children


def setup(app):
    LOG.info('loading keystoneauth1 plugins')
    app.add_directive('list-auth-plugins', ListAuthPluginsDirective)

#!/usr/bin/env python
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

import optparse

from automaton.converters import pydot

from ironic_inspector import introspection_state as states


def print_header(text):
    print("*" * len(text))
    print(text)
    print("*" * len(text))


def main():
    parser = optparse.OptionParser()
    parser.add_option("-f", "--file", dest="filename",
                      help="write output to FILE", metavar="FILE")
    parser.add_option("-T", "--format", dest="format",
                      help="output in given format (default: png)",
                      default='png')
    parser.add_option("--no-labels", dest="labels",
                      help="do not include labels",
                      action='store_false', default=True)
    (options, args) = parser.parse_args()
    if options.filename is None:
        options.filename = 'states.%s' % options.format

    def node_attrs(state):
        """Attributes used for drawing the nodes (states).

        The user can perform actions on introspection states, we distinguish
        the error states from the other states by highlighting the node.
        Error stable states are labelled with red.

        This is a callback method used by pydot.convert().

        :param state: name of state
        :returns: A dictionary with graphic attributes used for displaying
                  the state.
        # """
        attrs = {}
        attrs['fontcolor'] = 'red' if 'error' in state else 'gray'
        return attrs

    def edge_attrs(start_state, event, end_state):
        """Attributes used for drawing the edges (transitions).

        This is a callback method used by pydot.convert().

        :param start_state: name of the start state
        :param event: the event, a string
        :param end_state: name of the end state (unused)
        :returns: A dictionary with graphic attributes used for displaying
                  the transition.
        """
        if not options.labels:
            return {}

        attrs = {}
        attrs['fontsize'] = 10
        attrs['label'] = event
        if end_state is 'error':
            attrs['fontcolor'] = 'red'
        return attrs

    source = states.FSM
    graph_name = '"Ironic Inspector states"'
    graph_attrs = {'size': 0}
    dot_graph = pydot.convert(
        source, graph_name, graph_attrs=graph_attrs,
        node_attrs_cb=node_attrs, edge_attrs_cb=edge_attrs,
        add_start_state=False)

    dot_graph.write(options.filename, format=options.format)

    print(dot_graph.to_string())
    print_header("Created %s at '%s'" % (options.format, options.filename))


if __name__ == '__main__':
    main()

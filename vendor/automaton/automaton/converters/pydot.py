#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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

from __future__ import absolute_import

try:
    import pydot
    PYDOT_AVAILABLE = True
except ImportError:
    PYDOT_AVAILABLE = False


def convert(machine, graph_name,
            graph_attrs=None, node_attrs_cb=None, edge_attrs_cb=None,
            add_start_state=True, name_translations=None):
    """Translates the state machine into a pydot graph.

    :param machine: state machine to convert
    :type machine: FiniteMachine
    :param graph_name: name of the graph to be created
    :type graph_name: string
    :param graph_attrs: any initial graph attributes to set
                        (see http://www.graphviz.org/doc/info/attrs.html for
                        what these can be)
    :type graph_attrs: dict
    :param node_attrs_cb: a callback that takes one argument ``state``
                          and is expected to return a dict of node attributes
                          (see http://www.graphviz.org/doc/info/attrs.html for
                          what these can be)
    :type node_attrs_cb: callback
    :param edge_attrs_cb: a callback that takes three arguments ``start_state,
                          event, end_state`` and is expected to return a dict
                          of edge attributes (see
                          http://www.graphviz.org/doc/info/attrs.html for
                          what these can be)
    :type edge_attrs_cb: callback
    :param add_start_state: when enabled this creates a *private* start state
                            with the name ``__start__`` that will be a point
                            node that will have a dotted edge to the
                            ``default_start_state`` that your machine may have
                            defined (if your machine has no actively defined
                            ``default_start_state`` then this does nothing,
                            even if enabled)
    :type add_start_state: bool
    :param name_translations: a dict that provides alternative ``state``
                              string names for each state
    :type name_translations: dict
    """
    if not PYDOT_AVAILABLE:
        raise RuntimeError("pydot (or pydot2 or equivalent) is required"
                           " to convert a state machine into a pydot"
                           " graph")
    if not name_translations:
        name_translations = {}
    graph_kwargs = {
        'rankdir': 'LR',
        'nodesep': '0.25',
        'overlap': 'false',
        'ranksep': '0.5',
        'size': "11x8.5",
        'splines': 'true',
        'ordering': 'in',
    }
    if graph_attrs is not None:
        graph_kwargs.update(graph_attrs)
    graph_kwargs['graph_name'] = graph_name
    g = pydot.Dot(**graph_kwargs)
    node_attrs = {
        'fontsize': '11',
    }
    nodes = {}
    for (start_state, event, end_state) in machine:
        if start_state not in nodes:
            start_node_attrs = node_attrs.copy()
            if node_attrs_cb is not None:
                start_node_attrs.update(node_attrs_cb(start_state))
            pretty_start_state = name_translations.get(start_state,
                                                       start_state)
            nodes[start_state] = pydot.Node(pretty_start_state,
                                            **start_node_attrs)
            g.add_node(nodes[start_state])
        if end_state not in nodes:
            end_node_attrs = node_attrs.copy()
            if node_attrs_cb is not None:
                end_node_attrs.update(node_attrs_cb(end_state))
            pretty_end_state = name_translations.get(end_state, end_state)
            nodes[end_state] = pydot.Node(pretty_end_state, **end_node_attrs)
            g.add_node(nodes[end_state])
        edge_attrs = {}
        if edge_attrs_cb is not None:
            edge_attrs.update(edge_attrs_cb(start_state, event, end_state))
        g.add_edge(pydot.Edge(nodes[start_state], nodes[end_state],
                              **edge_attrs))
    if add_start_state and machine.default_start_state:
        start = pydot.Node("__start__", shape="point", width="0.1",
                           xlabel='start', fontcolor='green', **node_attrs)
        g.add_node(start)
        g.add_edge(pydot.Edge(start, nodes[machine.default_start_state],
                              style='dotted'))
    return g

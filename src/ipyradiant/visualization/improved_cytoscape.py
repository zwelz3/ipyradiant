# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.
import ipycytoscape as cyto
import ipywidgets as W
import networkx as nx
import rdflib
import traitlets as T
from ipycytoscape.cytoscape import Graph as CytoscapeGraph, MutableList, MutableDict

from ipyradiant.rdf2nx import RDF2NX
from ipyradiant.visualization.cytoscape import style

MAX_NODES = 300
MAX_EDGES = MAX_NODES * 3


class CytoscapeViewer(W.VBox):
    """A simple Cytoscape graph visualizer that can render RDF and networkx graphs.

    :param animate: flag for turning cytoscape animations on/off
    :param node_labels: flag for turning node labels on/off
    :param edge_labels: flag for turning edge labels on/off
    :param layouts: list of optional layouts for the ipycytoscape.CytoscapeWidget
    :param layout_selector: ipywidgets Dropdown for storing cytoscape layouts
    :param cytoscape_widget: ipycytoscape.CytoscapeWidget for rendering the graph
    :param graph: a networkx or rdflib Graph to render
    :param cyto_layout: the selected cytoscape graph layout
    :param cyto_style: the style used when rendering the cytoscape graph
    :param _render_large_graphs: flag to prevent long expensive layout computations for large graphs
    :param _rdf_label: attribute to use when discovering labels for RDF nodes (post-LPG conversion)
    :param _nx_label: attribute to use when discovering labels for networkx nodes
    :param _rdf_converter: converter class that transforms the input RDF graph to networkx
    :param _rdf_converter_graph: a separate rdflib.Graph used to collect additional node data
      (i.e. the object node data of a relationship)
    """

    animate = T.Bool(default_value=True)
    node_labels = T.Bool(default_value=True)
    edge_labels = T.Bool(default_value=True)
    layouts = T.List()
    layout_selector = T.Instance(W.Dropdown)
    cytoscape_widget = T.Instance(cyto.CytoscapeWidget)
    graph = T.Union(
        (
            T.Instance(rdflib.Graph),
            T.Instance(nx.Graph),
        ),
        allow_none=True,
        default_value=None,
    )
    cyto_layout = T.Unicode(default_value="random")
    cyto_style = T.List()
    include_missing_nodes = False
    _log = W.Output()
    _render_large_graphs = False
    _rdf_label = "rdfs:label"
    _nx_label = "label"
    _rdf_converter: RDF2NX = RDF2NX
    _rdf_converter_graph = T.Instance(rdflib.Graph, allow_none=True, default_value=None)

    def update_style(self):
        """Update style based on class attributes.

        TODO this is not maintainable
        """
        style_list = [style.DIRECTED_EDGE, style.MULTIPLE_EDGES]
        if self.node_labels and self.edge_labels:
            style_list = style.LABELLED_DIRECTED_GRAPH
        elif not self.node_labels and not self.edge_labels:
            style_list = style.DIRECTED_GRAPH
        else:
            if self.node_labels:
                style_list.append(style.LABELLED_NODE)
            else:
                style_list.append(style.NODE)
            if self.edge_labels:
                style_list.append(style.LABELLED_EDGE)
            else:
                style_list.append(style.EDGE)

        self.cyto_style = style_list

    def update_cytoscape_frontend(self):
        """A temporary workaround to trigger a frontend refresh"""
        self.cytoscape_widget.graph.add_node(cyto.Node(data={"id": "random node"}))
        self.cytoscape_widget.graph.remove_node_by_id("random node")

    @T.default("cyto_style")
    def _make_cyto_style(self):
        self.update_style()
        return self.cyto_style

    @T.validate("graph")
    def _valid_graph(self, proposal):
        """Validate graph by throwing error when # nodes/edges is at the limits of ipycytoscape

        TODO is there a better way to determine the limits than arbitrary numbers?
        """

        graph = proposal["value"]
        if (
            isinstance(graph, nx.Graph)
            and not self._render_large_graphs
            and (len(graph.nodes) > MAX_NODES or len(graph.edges) > MAX_EDGES)
        ):
            raise T.TraitError(
                f"unable to render networkx graphs with more than {MAX_NODES} nodes or {MAX_EDGES} edges."
            )
        elif (
            isinstance(graph, rdflib.Graph)
            and not self._render_large_graphs
            and (len(graph) > MAX_EDGES + MAX_NODES)
        ):
            raise T.TraitError(
                f"unable to render RDF graphs with more than {MAX_EDGES+MAX_NODES} triples."
            )
        return graph

    @T.observe("graph")
    def _update_graph(self, change):
        # TODO Clear graph so that data isn't duplicated 
        #   (blocked by https://github.com/QuantStack/ipycytoscape/issues/61)
        # Temporary workaround to clear graph by making a completely new widget
        self.cytoscape_widget = self._make_cytoscape_widget()        

        if isinstance(self.graph, nx.Graph):
            self.cytoscape_widget.graph.add_graph_from_networkx(self.graph)
            # TODO def add_label_from_nx
            for node in self.cytoscape_widget.graph.nodes:
                node.data["_label"] = node.data.get(self._nx_label, None)
        elif isinstance(self.graph, rdflib.Graph):
            # Note: rdflib_to_networkx_multidigraph does not store the predicate AT ALL,
            #  so it is basically unrecoverable (e.g. for labelling); using _rdf_converter
            # use external_graph of converter to return connected node data
            nx_graph = self._rdf_converter.convert(
                self.graph, external_graph=self._rdf_converter_graph
            )
            self.cytoscape_widget.graph.add_graph_from_networkx(nx_graph)
            for node in self.cytoscape_widget.graph.nodes:
                node.data["_label"] = node.data.get(
                    self._rdf_label, node.data.get("id", None)
                )
        # TODO remove when ipycytoscape issue #61 gets resolved
        self.update_cytoscape_frontend()

    @T.default("cytoscape_widget")
    def _make_cytoscape_widget(self):
        widget = cyto.CytoscapeWidget()
        widget.set_layout(
            animate=self.animate,
            randomize=True,
            # Fast animation time for initial graph
            maxSimulationTime=1000,
        )
        widget.set_style(self.cyto_style)
        return widget

    @T.observe("node_labels", "edge_labels")
    def _update_labels(self, change):
        self.update_style()

    @T.default("layouts")
    def _make_layouts(self):
        # TODO increase spacing on the layout?
        # https://stackoverflow.com/questions/54015729
        return ["circle", "cola", "concentric", "cose", "dagre", "grid", "random"]

    @T.default("layout_selector")
    def _make_layout_selector(self):
        widget = W.Dropdown(description="Layout:", options=self.layouts)
        T.link((self, "cyto_layout"), (widget, "value"))
        return widget

    @T.observe("layouts")
    def _update_layout_selector(self, change):
        self.layout_selector = self._make_layout_selector()

    @T.observe("cyto_layout")
    def _update_layout(self, change):
        # TODO move to .cytoscape.layout
        # note: animate=False goes through the full simulation to compute layout, which is SLOW
        self.cytoscape_widget.set_layout(
            name=self.cyto_layout,
            animate=self.animate,
            randomize=True,
            maxSimulationTime=2000,
        )

    @T.observe("cyto_style")
    def _update_style(self, change):
        self.cytoscape_widget.set_style(self.cyto_style)

    @T.observe("cytoscape_widget")
    def _update_children(self, change):
        if change.old == change.new:
            return
        self.children = (self.layout_selector, change.new)

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (
                self.layout_selector,
                self.cytoscape_widget,
            )
        return children

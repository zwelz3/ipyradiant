# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

from typing import Union

import ipycytoscape as cyto
import ipywidgets as W
import rdflib
import traitlets as trt

from ipyradiant.query.api import SPARQLQueryFramer
from ipyradiant.rdf2nx.uri_converter import URItoID

DEFAULT_CYTO_STYLE = [
    {
        "selector": "node",
        "css": {
            "label": "data(_label)",
            "text-wrap": "wrap",
            "text-max-width": "150px",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "10",
            "font-family": '"Gill Sans", sans-serif',
            "color": "black",
            "background-color": "grey",
        },
    },
    {
        "selector": "edge[classes='temp-edge']",
        "css": {
            "label": "data(_label)",
            "line-color": "#a8eae5",
        },
    },
    {
        "selector": "node.clicked",
        "css": {
            "background-color": "grey",
            "line-color": "black",
            "target-arrow-color": "black",
            "source-arrow-color": "black",
        },
    },
    {
        "selector": "node.temp",
        "css": {
            "background-color": "#FFB6C1",
            "line-color": "black",
            "target-arrow-color": "black",
            "source-arrow-color": "black",
        },
    },
    {
        "selector": "edge.directed",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "line-color": "grey",
            # "label": "data(iri)",
            "font-size": "5",
        },
    },
    {
        "selector": "edge.temp",
        "style": {
            "curve-style": "bezier",
            "line-color": "#a8eae5",
            # "label": "data(iri)",
            "font-size": "5",
        },
    },
    {"selector": "edge.multiple_edges", "style": {"curve-style": "bezier"}},
]


def add_cyto_class(element: Union[cyto.Node, cyto.Edge], class_addition: str) -> str:
    """Update the classes string for a cytoscape element with an addition

    TODO support multiple class additions

    :param element: the cytoscape Node/Edge to update classes for
    :param class_addition: the class string to add
    :return: the class string
    """
    try:
        classes = set(element.classes.split(" "))
    except AttributeError:
        classes = set()
    classes.add(class_addition)
    return " ".join(classes)


def remove_cyto_class(element: Union[cyto.Node, cyto.Edge], class_removal: str) -> str:
    """Update the classes string for a cytoscape element with a removal

    TODO support multiple class additions

    :param element: the cytoscape Node/Edge to update classes for
    :param class_removal: the class string to remove
    :return: the class string
    """
    try:
        classes = set(element.classes.split(" "))
        classes.discard(class_removal)
        return " ".join(classes)
    except AttributeError:
        return ""


class GetOutgoingPredicateObjects(SPARQLQueryFramer):
    """
    Return all triples for non-Literal objects (and the optional object labels).
    """

    sparql = """
    SELECT DISTINCT ?s ?p ?o ?label

    WHERE {
        ?s ?p ?o .
        FILTER (!isLiteral(?o))
        OPTIONAL {?o rdfs:label ?label}
    }

    """


# Throughout we assign the layout to self.cytoscape_widget_layout multiple times.
# This is so that the graph refreshes the layout every time nodes are added or removed,
# which provides an optimal viewing experience.


class InteractiveViewer(W.VBox):
    expand_button = trt.Instance(W.Button)
    undo_button = trt.Instance(W.Button)
    remove_temp_nodes_button = trt.Instance(W.Button)
    cytoscape_widget = trt.Instance(cyto.CytoscapeWidget)
    selected_node = trt.Instance(cyto.Node, allow_none=True)
    rdf_graph = trt.Instance(rdflib.graph.Graph, allow_none=True)
    cyto_style = trt.List(allow_none=True)
    cytoscape_widget_layout = trt.Unicode(default_value="cola")
    #
    existing_node_ids = []
    new_nodes = {}
    new_edges = {}

    @trt.default("expand_button")
    def _create_expand_button(self):
        button = W.Button(
            description="Expand Upon Selected Node",
            layout=W.Layout(width="50%", height="40px"),
        )
        button.on_click(self.expand_button_clicked)
        return button

    @trt.default("undo_button")
    def _create_undo_button(self):
        button = W.Button(
            description="Undo Last Expansion",
            layout=W.Layout(width="25%", height="40px"),
            disabled=True,
        )
        button.on_click(self.undo_expansion)
        return button

    @trt.default("remove_temp_nodes_button")
    def _create_remove_temp_nodes_button(self):
        button = W.Button(
            description="Remove Temporary Nodes",
            layout=W.Layout(width="25%", height="40px"),
            disabled=False,
        )
        button.on_click(self.remove_temp_nodes)
        return button

    @trt.default("selected_node")
    def _create_default_selected_node(self):
        return None

    @trt.default("cyto_style")
    def _create_cyto_style(self):
        return DEFAULT_CYTO_STYLE

    @trt.default("rdf_graph")
    def _create_rdf_graph(self):
        return rdflib.Graph()

    @trt.default("cytoscape_widget")
    def _create_cytoscape_widget(self):
        return cyto.CytoscapeWidget()

    @trt.default("layout")
    def _create_layout(self):
        return W.Layout(width="80%")

    @trt.observe("cytoscape_widget")
    def update_cytoscape_widget(self, change):
        """Apply settings to cytoscape graph when updating"""
        
        if change.old == change.new:
            return

        self.cytoscape_widget.set_layout(name=self.cytoscape_widget_layout)
        self.cytoscape_widget.set_style(self.cyto_style)
        # on is a callback for cytoscape_widget instance (must be set on each instance)
        self.cytoscape_widget.on("node", "click", self.log_node_clicks)
        # Must set children again so that the changes propagate to the front end
        # Ideally, would be done automatically with traits
        # https://github.com/jupyrdf/ipyradiant/issues/79
        self.children = (
            self.cytoscape_widget,
            W.HBox(
                children=[
                    self.expand_button,
                    self.undo_button,
                    self.remove_temp_nodes_button,
                ]
            ),
        )

    @trt.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (
                self.cytoscape_widget,
                W.HBox(
                    children=[
                        self.expand_button,
                        self.undo_button,
                        self.remove_temp_nodes_button,
                    ]
                ),
            )
        return children

    def get_node(self, node: dict) -> cyto.Node:
        """This function is used to find a node given the id of a node copy"""

        for cyto_node in self.cytoscape_widget.graph.nodes:
            if cyto_node.data["id"] == node["data"]["id"]:
                return cyto_node
        # TODO: Make this function return None and log a warning if not node not found.
        raise ValueError("Node not found in cytoscape.graph.nodes.")

    def log_node_clicks(self, node: dict):
        """
        This function works with registering a click on a node.
        This will mark the node as selected and change the color of the selected node.
        """

        cyto_node = self.get_node(node)

        if self.selected_node == cyto_node:
            cyto_node.classes = remove_cyto_class(cyto_node, "temp")
            cyto_node.classes = add_cyto_class(cyto_node, "clicked")

            # NOTE: changes won't propagate to frontend until graph is updated
            self.update_cytoscape_frontend()

        self.selected_node = cyto_node

    def expand_button_clicked(self, button):
        """
        This function expands a node by loading in its predicates and subjects when
        a node is selected and the expand button is clicked.
        """

        self.undo_button.disabled = False
        if self.selected_node is None:
            return None
        new_data = GetOutgoingPredicateObjects.run_query(
            graph=self.rdf_graph, s=self.selected_node.data["iri"]
        )
        objs = new_data["o"].tolist()
        preds = new_data["p"].tolist()
        labels = new_data["label"].tolist()
        self.existing_node_ids = [
            node.data["id"] for node in self.cytoscape_widget.graph.nodes
        ]
        self.new_nodes = {
            idx: cyto.Node(
                data={
                    "id": str(iri),
                    "iri": iri,
                    "_label": labels[idx] or str(iri),
                },
                classes="temp",
            )
            for idx, iri in enumerate(objs)
            if str(iri) not in self.existing_node_ids
        }
        self.new_edges = {
            idx: cyto.Edge(
                data={
                    "source": self.selected_node.data["id"],
                    "target": str(iri),
                    "iri": URItoID(preds[idx]),
                },
                classes="temp",
            )
            for idx, iri in enumerate(objs)
        }

        self.cytoscape_widget.graph.add_nodes(self.new_nodes.values())
        self.cytoscape_widget.graph.add_edges(self.new_edges.values())
        self.cytoscape_widget.set_layout(name=self.cytoscape_widget_layout)

    def undo_expansion(self, button):
        """
        Preliminary function for undoing expansions upon a node.
        As of right now, a user can only undo the most recent expansion.
        Afterwards, the button will be disabled until a new expansion is made.
        """

        self.undo_button.disabled = True
        for node in self.new_nodes:
            self.cytoscape_widget.graph.remove_node_by_id(
                self.new_nodes[node].data["id"]
            )
        for edge in self.new_edges:
            try:
                self.cytoscape_widget.graph.remove_edge(self.new_edges[edge])
            except ValueError:
                # edge already removed from graph because the node was removed earlier.
                pass

        self.cytoscape_widget.set_layout(name=self.cytoscape_widget_layout)

    def remove_temp_nodes(self, button):
        """Remove all nodes that have the 'temp' style"""

        nodes_to_remove = {
            node for node in self.cytoscape_widget.graph.nodes if "temp" in node.classes
        }
        for node in nodes_to_remove:
            self.cytoscape_widget.graph.remove_node(node)

        # change edge color
        for edge in self.cytoscape_widget.graph.edges:
            edge.classes = remove_cyto_class(edge, "temp")
            edge.classes = add_cyto_class(edge, "directed")

        # NOTE: changes won't propagate to frontend until graph is updated
        self.update_cytoscape_frontend()

        self.cytoscape_widget.set_layout(name=self.cytoscape_widget_layout)
        self.undo_button.disabled = True

    def update_cytoscape_frontend(self):
        """A temporary workaround to trigger a frontend refresh"""
        self.cytoscape_widget.graph.add_node(cyto.Node(data={"id": "random node"}))
        self.cytoscape_widget.graph.remove_node_by_id("random node")

# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import ipywidgets as W
import traitlets as T
from IPython.display import JSON, display
from networkx import Graph as NXGraph
from pandas import DataFrame
from rdflib.graph import Graph as RDFGraph
from rdflib.term import URIRef

from ipyradiant.basic_tools.custom_uri_ref import CustomURIRef
from ipyradiant.rdf2nx.converter import RDF2NX
from ipyradiant.visualization.cytoscape import style
from ipyradiant.visualization.cytoscape.viewer import CytoscapeViewer

# Ranked by pairwise distance (generated by https://mokole.com/palette.html)
COLOR_LIST = [
    (47, 79, 79),
    (85, 107, 47),
    (139, 69, 19),
    (34, 139, 34),
    (72, 61, 139),
    (184, 134, 11),
    (70, 130, 180),
    (0, 0, 128),
    (127, 0, 127),
    (143, 188, 143),
    (176, 48, 96),
    (255, 69, 0),
    (255, 255, 0),
    (0, 255, 0),
    (138, 43, 226),
    (0, 255, 127),
    (220, 20, 60),
    (0, 255, 255),
    (0, 0, 255),
    (173, 255, 47),
    (218, 112, 214),
    (255, 127, 80),
    (255, 0, 255),
    (30, 144, 255),
    (144, 238, 144),
    (173, 216, 230),
    (255, 20, 147),
    (123, 104, 238),
    (255, 222, 173),
    (255, 192, 203),
]


def get_color_list_css(color_list):
    """Convert color list to ipycytoscape css format."""
    return [f"rgb({r},{g},{b})" for r, g, b in color_list]


def get_desc(uri, namespaces, count=None):
    """Get a shorthand way to describe a URI and its counts."""

    shorthand = str(CustomURIRef(uri, namespaces=namespaces))
    if count:
        return f"{shorthand}  [{count}]"


def get_type_counts(klass, graph: NXGraph) -> DataFrame:
    """Function to return the types and their counts in a networkx graph."""
    type_dict = {}
    for node, data in graph.nodes(data=True):
        # node_type can be a list (make all list)
        type_attr = data.get("rdf:type")
        if not type_attr:
            raise ValueError(f"Node has no 'rdf:type': {data.keys()}")

        if not isinstance(type_attr, (list, tuple)):
            node_types = [
                type_attr,
            ]
        else:
            node_types = type_attr

        for node_type in node_types:
            if node_type not in type_dict:
                type_dict[node_type] = 0
            type_dict[node_type] = type_dict[node_type] + 1

    return DataFrame(type_dict.items(), columns=["type_", "count"]).sort_values(
        by=["count"], ascending=False
    )


def get_predicate_counts(klass, graph: NXGraph) -> DataFrame:
    """Function to return the predicates and their counts in a networkx graph."""
    predicate_dict = {}
    for source, target, data in graph.edges(data=True):
        predicate = data.get("predicate")
        if not predicate:
            raise ValueError(f"Edge ({source}, {target}) has no predicate attribute.")
        elif predicate and predicate not in predicate_dict:
            predicate_dict[predicate] = 0
        predicate_dict[predicate] = predicate_dict[predicate] + 1

    return DataFrame(
        predicate_dict.items(), columns=["predicate", "count"]
    ).sort_values(by=["count"], ascending=False)


class InteractiveViewer(W.GridspecLayout):
    """Graph visualization for viewing RDF graphs as LPGs. The InteractiveViewer
      provides a method for reducing the amount of displayed information through a
      multi-select widget for `rdf:type` and all predicates in the graph. Users
      can choose which types/edges they want to see, and the visualization will
      update the corresponding nodes/edges.

    Note: we use a separate RDF2NX converter to avoid issues with larger graphs

    TODO document how users can extend the count functions

    :param rdf_graph: the rdflib.graph.Graph to display
    :param allow_large_graphs: boolean flag to allow graphs over the allowed size
    :param type_count_callable: the function used to collect valid rdf:types
    :param predicate_count_query: the function used used to collect valid predicates
    """

    allow_large_graphs = T.Bool(default_value=False)
    rdf_graph = T.Instance(RDFGraph, kw={})
    type_selector = T.Instance(W.SelectMultiple)
    predicate_selector = T.Instance(W.SelectMultiple)
    viewer = T.Instance(CytoscapeViewer)
    json_output = T.Instance(W.Output)

    type_count_callable = get_type_counts
    predicate_count_callable = get_predicate_counts
    uri_to_string_type = {}  # map
    iri_to_node = {}  # map
    _rdf_converter: RDF2NX = RDF2NX()
    _nx_graph: NXGraph = NXGraph()

    def __init__(self, n_rows=4, n_columns=5, **kwargs):
        super().__init__(n_rows=n_rows, n_columns=n_columns, **kwargs)

    def load_json(self, node):
        data = node["data"]
        data.pop("_label", None)
        data.pop("_attrs", None)
        with self.json_output:
            self.json_output.clear_output()
            display(JSON(data))

    def _ipython_display_(self, **kwargs):
        super()._ipython_display_(**kwargs)
        self._set_layout()

    def _set_layout(self):
        layout = self.layout
        layout.height = "80vh"
        layout.width = "auto"

        self[0:3, :1] = W.VBox(
            [
                W.VBox(
                    [
                        W.Label("Types:"),
                        self.type_selector,
                        W.Label("Edges:"),
                        self.predicate_selector,
                    ]
                ),
            ]
        )
        self[0:3, 1:] = self.viewer
        self[3, 1:] = self.json_output

        for widget in (
            self.type_selector,
            self.predicate_selector,
            self.viewer,
        ):
            widget.layout.height = "auto"
            widget.layout.width = "auto"
            widget.layout.min_height = None
            widget.layout.max_height = None
            widget.layout.max_width = None
            widget.layout.min_width = None

        self.layout = layout

    def assign_css_classes(self):
        # assign colors to css classes
        color_list = COLOR_LIST.copy()
        n_to_add = len(self.uri_to_string_type.keys()) - len(color_list)
        if n_to_add > 0 and self.allow_large_graphs:
            color_list.extend([(255, 255, 255)] * n_to_add)
        elif n_to_add > 0:
            raise ValueError(
                f"Cannot render more than {len(COLOR_LIST)} visually distinct colors."
            )

        color_type_map = list(
            zip(
                [*self.uri_to_string_type.values(), "multi-type"],
                get_color_list_css(color_list),
            )
        )

        # use css data attribute style to color based on type
        color_classes = []
        for class_name, rgb_code in color_type_map:
            color_classes.append(
                {
                    "selector": f"node[type_ = '{class_name}']",
                    "style": {
                        "background-color": f"{rgb_code}",
                    },
                }
            )

        return color_classes

    def update_iri_map(self):
        """Updates the internal mapping from IRI to cytoscape node instances."""
        # node_iri to node (for mapping to edges)
        # TODO is there a way to enhance/use the adjacency matrix?
        self.iri_to_node = {
            str(node.data["iri"]): node
            for node in self.viewer.cytoscape_widget.graph.nodes
        }

    def update_classes(self, change):
        """Updates the CSS classes for nodes/edges.

        TODO optimize so that we don't have to iterate through every node/edge
        """
        self.update_iri_map()

        # use selectors to determine visible nodes/edges
        visible_node_types = set(self.type_selector.value)
        visible_edge_types = set(self.predicate_selector.value)

        # set visibility for all nodes (only needed for node changes)
        try:
            change_type = getattr(change.owner, "type_", "both")
        except AttributeError:
            change_type = "both"

        if change_type in {"node_type", "both"}:
            for node in self.viewer.cytoscape_widget.graph.nodes:
                raw_types = node.data["rdf:type"]
                types = raw_types if type(raw_types) is tuple else (raw_types,)
                if not any([_type in visible_node_types for _type in types]):
                    node.classes = "invisible"
                else:
                    node.classes = ""

        # set visibility for all edges (needed for node and edge changes)
        for edge in self.viewer.cytoscape_widget.graph.edges:
            source_node = self.iri_to_node[edge.data["source"]]
            target_node = self.iri_to_node[edge.data["target"]]

            if edge.data["predicate"] not in visible_edge_types:
                edge.classes = "invisible"
            elif (
                "invisible" in source_node.classes or "invisible" in target_node.classes
            ):
                edge.classes = "invisible"
            else:
                edge.classes = "directed"

        # update front-end (set_style must receive a copy)
        self.viewer.cytoscape_widget.set_style(
            list(self.viewer.cytoscape_widget.get_style())
        )

    def apply_node_styling(self, change):
        """Iterates through cytoscape nodes and sets the node data 'type_'
        based on the 'rdf:type'.
        """
        self.update_classes(change=None)

        # assign CSS classes to nodes based on their rdf:type
        # TODO add types instead of replacing once we figure out how to make partial matches of css classes in ipycytoscape
        for node in self.viewer.cytoscape_widget.graph.nodes:
            node_types = node.data.get("rdf:type", [])
            if type(node_types) == URIRef:
                node_types = (node_types,)

            if len(node_types) == 1:
                # assign specific class to node
                assert node_types[0] in self.uri_to_string_type
                css_class = self.uri_to_string_type[node_types[0]]
                node.data["type_"] = css_class
            else:
                node.data["type_"] = "multi-type"

    @T.default("json_output")
    def _make_default_json_output(self):
        widget = W.Output()
        # Prevent resizing the JSON output from changing other widgets
        widget.layout.overflow_y = "auto"
        widget.layout.width = "auto"
        return widget

    @T.default("viewer")
    def _make_default_viewer(self):
        widget = CytoscapeViewer()
        widget.allow_disconnected = True
        # Change networkx graph label (because we are converting from RDF)
        widget._nx_label = "rdfs:label"
        widget._render_large_graphs = self.allow_large_graphs
        widget.cytoscape_widget.on("node", "click", self.load_json)
        widget.allow_disc_check.disabled = True
        # When the cytoscape widget is updated, have to re-apply node/edge style
        widget.observe(self.apply_node_styling, "cytoscape_widget")
        return widget

    @T.default("type_selector")
    def _make_default_type_selector(self):
        widget = W.SelectMultiple()
        # set a type for the observer to read
        widget.type_ = "node_type"
        widget.observe(self.update_classes, "value")
        return widget

    @T.default("predicate_selector")
    def _make_default_predicate_selector(self):
        widget = W.SelectMultiple()
        # set a type for the observer to read
        widget.type_ = "predicate"
        widget.observe(self.update_classes, "value")
        return widget

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (
                W.HBox(
                    [
                        W.VBox(
                            [
                                W.Label("Types:"),
                                self.type_selector,
                                W.Label("Edges:"),
                                self.predicate_selector,
                            ]
                        ),
                        self.viewer,
                    ]
                ),
                self.json_output,
            )

        return children

    @T.observe("rdf_graph")
    def update_rdf_graph(self, change):
        """When the graph is changed, updates the corresponding widget elements.

        TODO break up method into smaller parts?
        TODO is it possible to only add types/predicates for the converted graph (e.g. post RDF2NX)
        """
        rdf_graph = change.new

        # Run the converter (let viewer do the post-processing)
        self._nx_graph = self._rdf_converter.convert(rdf_graph)

        # force update now  TODO remove?
        self.viewer.graph = self._nx_graph

        # needed for type/predicate count methods
        self.update_iri_map()

        # run type and predicate counter functions
        type_count = self.type_count_callable(self._nx_graph)
        predicate_count = self.predicate_count_callable(self._nx_graph)

        # map type URIs to their css class name for ipycytoscape
        self.uri_to_string_type = {
            uri: str(CustomURIRef(uri, namespaces=rdf_graph.namespace_manager)).replace(
                ":", "-"
            )
            for uri in type_count.type_
        }
        self.uri_to_string_type["multi-type"] = "multi-type"

        # build options for the type MultiSelect
        select_options = []
        for uri, count in type_count.values:
            description = get_desc(uri, rdf_graph.namespace_manager, count)
            select_options.append((description, uri))

        # set options, value, and row counts
        self.type_selector.options = select_options
        self.type_selector.value = tuple(uri for _, uri in select_options)
        self.type_selector.rows = len(select_options)

        # build options for the predicate MultiSelect
        select_options = []
        for uri, count in predicate_count.values:
            description = get_desc(uri, rdf_graph.namespace_manager, count)
            select_options.append((description, uri))

        # set options, value, and row counts
        self.predicate_selector.options = select_options
        self.predicate_selector.value = tuple(uri for _, uri in select_options)
        self.predicate_selector.rows = len(select_options)

        color_classes = self.assign_css_classes()
        self.apply_node_styling(change=None)

        # change the cytoscape widget style
        old_style = list(self.viewer.cytoscape_widget.get_style())  # must be a copy!
        old_style.extend([*color_classes, style.INVISIBLE_NODE, style.INVISIBLE_EDGE])
        self.viewer.cytoscape_widget.set_style(old_style)

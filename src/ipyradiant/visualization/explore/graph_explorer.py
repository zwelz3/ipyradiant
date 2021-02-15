# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import ipywidgets as W
import traitlets as T
from ipycytoscape import CytoscapeWidget
from IPython.display import JSON, display
from networkx import Graph as NXGraph
from rdflib import Graph as RDFGraph, URIRef

from ...basic_tools.custom_uri_ref import CustomURI
from ...basic_tools.uri_widgets import SelectURI, SelectMultipleURI
from ...query.api import SPARQLQueryFramer, build_values
from ...rdf2nx import RDF2NX
from .interactive_exploration import InteractiveViewer


def make_directed_graph(nx_graph: NXGraph) -> CytoscapeWidget:
    """Converts a networkx graph to a cytoscape graph widget"""
    directed = CytoscapeWidget()
    directed.graph.add_graph_from_networkx(nx_graph, multiple_edges=True, directed=True)

    for node in directed.graph.nodes:
        # deal with cytoscape's inability to handle `:` e.g. thing:data
        node.data["_label"] = node.data.get("rdfs:label", None)

    return directed


class AllTypes(SPARQLQueryFramer):
    """Simple query for returning type objects"""

    sparql = """
    SELECT DISTINCT ?o
    WHERE {
        ?s a ?o .
    }
    """


class CustomItem:
    """Class used to build list items with custom repr"""

    def __init__(self, _repr: callable, **kwargs):
        self._repr = _repr
        for attr, value in kwargs.items():
            self.__setattr__(attr, value)

    def __repr__(self):
        return self._repr(self)


class MetaSubjectsOfType(type):
    """Metaclass to query for type and label for specific VALUES."""

    _sparql = """
        SELECT DISTINCT ?s ?label
        WHERE {{
            ?s a ?type .
            OPTIONAL {{ ?s rdfs:label ?label . }}

            VALUES ({}) {{
                {}
            }}
        }}
    """
    values = None

    @property
    def sparql(cls):
        return build_values(cls._sparql, cls.values)


class RDFTypeSelect(W.VBox):
    """Widget that contains node types present in the graph.
    Uses a library query, and the graph object's namespace.
    """

    graph = T.Instance(RDFGraph, allow_none=True)
    label = T.Instance(W.HTML)
    select_widget = T.Instance(SelectURI)

    @T.default("label")
    def make_default_label(self):
        return W.HTML("<b>Available types:</b>")

    @T.default("select_widget")
    def make_default_select_widget(self):
        return SelectURI(rows=10)

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (self.label, self.select_widget)
        return children

    @T.observe("graph")
    def update_graph(self, change):
        self.make_available_types()

    def make_available_types(self):
        if self.graph is None:
            return

        ns = dict(self.graph.namespaces())
        types = AllTypes.run_query(self.graph)
        # TODO how to allow user specification of custom CustomURI class
        self.select_widget.pithy_uris = tuple(
            map(lambda x: CustomURI(x, namespaces=ns), types["o"].to_list())
        )


class RDFTypeSelectMultiple(RDFTypeSelect):
    select_widget = T.Instance(SelectMultipleURI)

    @T.default("select_widget")
    def make_default_select_widget(self):
        return SelectMultipleURI(rows=10)


class RDFSubjectSelect(W.VBox):
    """Widget that contains subjects in the graph based on type _values."""

    # Define the query class
    class SubjectsOfType(SPARQLQueryFramer, metaclass=MetaSubjectsOfType):
        values = None  # note: query will not run without values

    graph = T.Instance(RDFGraph, allow_none=True).tag(default=None)
    label = T.Instance(W.HTML)
    query = SubjectsOfType
    select_widget = T.Instance(SelectURI)
    _values = T.Instance(dict, allow_none=True).tag(default=None)

    @T.default("label")
    def make_default_label(self):
        return W.HTML("<b>Available subjects:</b>")

    @T.default("select_widget")
    def make_default_select_widget(self):
        return SelectURI(rows=10)

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (self.label, self.select_widget)
        return children

    @T.observe("graph")
    def update_graph(self, change):
        self.update_select()

    @T.observe("_values")
    def update_values(self, change):
        if change.old != change.new:
            self.query.values = change.new
            self.update_select()

    def run_query(self):
        assert self.query.values is not None
        return self.query.run_query(self.graph)

    def update_select(self):
        if None in (self.graph, self._values):
            return

        self.select_widget.pithy_uris = tuple(
            CustomItem(
                _repr=lambda x: f"{x.label}:   ->   {x.uri}",
                uri=uri,
                label=label,
            )
            for uri, label in self.run_query().values
        )


class RDFSubjectSelectMultiple(RDFSubjectSelect):
    select_widget = T.Instance(SelectMultipleURI)

    @T.default("select_widget")
    def make_default_select_widget(self):
        return SelectMultipleURI(rows=10)


class GraphExploreSelect(W.VBox):
    """Widget that allows users to select a subject in the graph using a type filter."""

    graph = T.Instance(RDFGraph, kw={})
    subject_select = T.Instance(RDFSubjectSelect)
    type_select = T.Instance(RDFTypeSelect)

    @property
    def selected_types(self):
        return self.type_select.select_widget.value

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (self.type_select, self.subject_select)
        return children

    @T.default("type_select")
    def make_default_type_select(self):
        type_selector = RDFTypeSelect()
        type_selector.graph = self.graph
        type_selector.select_widget.observe(self.update_subject_select_value, "value")
        return type_selector

    @T.default("subject_select")
    def make_default_subject_select(self):
        subject_selector = RDFSubjectSelect()
        subject_selector.graph = self.graph
        return subject_selector

    @T.observe("graph")
    def update_subwidget_graphs(self, change):
        # reset the subject select options and value
        self.subject_select.select_widget.options = ()
        self.subject_select.select_widget.value = None
        self.subject_select._values = None

        self.type_select.graph = self.graph
        self.subject_select.graph = self.graph

    def update_subject_select_value(self, change):
        if change.old != change.new and change.new:
            # Note: change.new == self.type_select.select_widget.value
            self.subject_select._values = {"type": [change.new]}


class GraphExploreSelectMultiple(GraphExploreSelect):
    """Widget that allows users to select multiple subjects in the graph using a type filter."""

    subject_select = T.Instance(RDFSubjectSelectMultiple)
    type_select = T.Instance(RDFTypeSelectMultiple)

    @T.default("type_select")
    def make_default_type_select(self):
        type_selector = RDFTypeSelectMultiple()
        type_selector.graph = self.graph
        type_selector.select_widget.observe(self.update_subject_select_values, "value")
        return type_selector

    @T.default("subject_select")
    def make_default_subject_select(self):
        subject_selector = RDFSubjectSelectMultiple()
        subject_selector.graph = self.graph
        return subject_selector

    @T.observe("graph")
    def update_subwidget_graphs(self, change):
        # reset the subject select options and value
        self.subject_select.select_widget.options = ()
        self.subject_select.select_widget.value = ()
        self.subject_select._values = None

        self.type_select.graph = self.graph
        self.subject_select.graph = self.graph

    def update_subject_select_values(self, change):
        if change.old != change.new and change.new:
            # Note: change.new == self.type_select.select_widget.value
            self.subject_select._values = {"type": list(change.new)}


class GraphExplorer(W.VBox):
    """Widget that allows users to populate and explore a graph based on RDF data."""

    rdf_graph = T.Instance(RDFGraph, kw={})
    nx_graph = T.Instance(NXGraph, kw={})
    # collapse_button = T.Instance(W.Button)
    node_select = T.Union(
        (
            T.Instance(GraphExploreSelect),
            T.Instance(GraphExploreSelectMultiple)
        )
    )
    interactive_viewer = T.Instance(InteractiveViewer)
    default_children = T.Tuple()
    json_output = W.Output()
    # class attr to support multi-select TODO better way to do this?
    _multiple = True   

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (
                W.HBox([self.node_select, self.interactive_viewer]),
                # self.collapse_button
                self.json_output,
            )
        return children

    #     @T.default("collapse_button")
    #     def make_default_collapse_button(self):
    #         button = W.Button(
    #             icon="fa-exchange",
    #             layout=W.Layout(width='45px'),
    #             tooltip="Expand/collapse node selector."
    #         )
    #         button.on_click(self.expand_collapse)
    #         return button

    @T.default("node_select")
    def make_default_node_select(self):
        if self._multiple:
            node_selector = GraphExploreSelectMultiple()
        else:
            node_selector = GraphExploreSelect()
        node_selector.subject_select.select_widget.observe(self.make_nx_graph, "value")
        return node_selector

    @T.default("interactive_viewer")
    def make_default_interactive_viewer(self):
        return InteractiveViewer()

    @T.default("default_children")
    def make_default_children(self):
        return (
            W.HBox([self.collapse_button, self.node_select, self.interactive_viewer]),
            self.json_output,
        )

    # TODO expand/collapse breaks the "expand upon selected node" button
    #     def expand_collapse(self, button):
    #         if len(self.children[0].children) > len(self.default_children[0].children)-1:
    #             self.children = (
    #                 W.HBox([self.collapse_button, self.interactive_viewer]),
    #                 self.json_output
    #             )
    #         else:
    #             self.children = self.default_children

    @T.observe("rdf_graph")
    def update_subwidget_graphs(self, change):
        self.json_output.clear_output()
        self.node_select.graph = self.rdf_graph
        self.interactive_viewer.rdf_graph = self.rdf_graph

    @T.observe("nx_graph")
    def update_cytoscape_widget(self, change):
        self.json_output.clear_output()
        self.interactive_viewer.cytoscape_widget = make_directed_graph(self.nx_graph)
        self.interactive_viewer.observe(self.load_json, "selected_node")
        # self.children = [self.collapse_button, self.node_select, self.interactive_viewer]

    def make_nx_graph(self, change):
        sssw_value = self.node_select.subject_select.select_widget.value
        # For single-select, this will not be a list
        if isinstance(sssw_value, URIRef):
            sssw_value = [sssw_value]
        # TODO do we want the convert_nodes to add edges between the nodes?
        self.nx_graph = RDF2NX.convert_nodes(
            node_uris=sssw_value, rdf_graph=self.rdf_graph
        )

    def load_json(self, change):
        if change.new == change.old:
            return None

        # must be copy to prevent changing the object
        data = dict(change.new.data)
        data.pop("_label", None)  # TODO just remove private and non-serializable
        with self.json_output:
            self.json_output.clear_output()
            display(JSON(data))

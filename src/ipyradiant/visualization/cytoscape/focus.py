import ipywidgets as W
import traitlets as T
from rdflib import Graph as RDFGraph
from rdflib import URIRef

from ipyradiant.query.api import SPARQLQueryFramer, build_values
from ipyradiant.visualization.improved_cytoscape import CytoscapeViewer


class MetaFocusQuery(type):
    """Metaclass to construct triples for a specified set of triple values."""

    _sparql = """
        CONSTRUCT {{
            ?s ?p ?o .
        }} WHERE {{
            ?s ?p ?o .

            VALUES ({}) {{
                {}
            }}
        }}
    """
    values = None

    @property
    def sparql(cls):
        return build_values(cls._sparql, cls.values)


class FocusQuery(SPARQLQueryFramer, metaclass=MetaFocusQuery):
    values = None
    columns = ["s", "p", "o"]


class FocusView(W.Box):
    """A widget for visualizing a single RDF node and its connections (as a property graph).

    :param subject_uri: the rdflib.URIRef of the node of interest
    :param rdf_graph: the rdflib.Graph to use when creating the cytoscape visualization
    :param cytoscape_viewer: the base visualization widget

    TODO validate subject_uri to make sure it is in the graph
    TODO lighten opactiy of the target nodes
    TODO increase size of focus node
    """

    subject_uri = T.Instance(URIRef, allow_none=True, default_value=None)
    rdf_graph = T.Instance(
        RDFGraph, kw={}
    )  # Graph containing the subject_uri node AND all connected nodes (source AND target)
    cytoscape_viewer = T.Instance(CytoscapeViewer)

    def _run_query(self, subject_uri: URIRef) -> RDFGraph:
        """Runs FocusQuery, and returns the results in a rdflib.Graph

        :param subject_uri: the rdflib.URIRef of the subject node
        :returns: a rdflib.Graph containing all triples connected to the subject node

        TODO replace with rdflib builtin predicate_object method?
        """

        FocusQuery.values = {"s": [subject_uri]}
        qres_df = FocusQuery.run_query(self.rdf_graph)
        # Dump to graph
        qres_graph = RDFGraph()
        for triple in qres_df.values:
            qres_graph.add(triple)
        return qres_graph

    @T.default("cytoscape_viewer")
    def make_default_cytoscape_viewer(self):
        widget = CytoscapeViewer()
        widget.layout.width = "100%"
        # we use the converter graph attribute to specify that we want to use a separate graph
        #  than the cytoscape viewer uses for rendering (e.g. to get the missing connected nodes)
        T.link((self, "rdf_graph"), (widget, "_rdf_converter_graph"))
        return widget

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (self.cytoscape_viewer,)
        return children

    @T.observe("subject_uri")
    def update_cytoscape_viewer(self, change):
        # TODO update to handle case where subject is not in graph
        if change.new is None:
            raise ValueError("Unhandled condition")
            # TODO reset the graph
            pass
        if change.old == change.new:
            return
        self.cytoscape_viewer.graph = self._run_query(change.new)

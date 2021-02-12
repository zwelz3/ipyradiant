# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.
import logging
from typing import Callable, Dict, List, Union
from warnings import warn

from networkx import MultiDiGraph
from pandas import DataFrame
from rdflib import Graph as RDFGraph
from rdflib import Literal, URIRef
from rdflib.namespace import Namespace, NamespaceManager

from ..query.api import SPARQLQueryFramer
from .edges import ReifiedRelations, RelationProperties, RelationTypes
from .literal_converter import cast_literal
from .nodes import NodeIRIs, NodeProperties, NodeTypes
from .uri_converter import URItoShortID

logger = logging.getLogger(__name__)


# TODO subclass from RDF2LPG and add adapters for NX/neo4j/etc.
class RDF2NX:
    """A class for converting RDF graphs to Networkx property graphs."""

    # Track converted predicates over classmethod calls
    converted_predicates: dict = {}
    initNs: dict = None

    # Converters
    uri_to_short_id: Callable = URItoShortID

    # Queries
    node_iris: SPARQLQueryFramer = NodeIRIs
    node_properties: SPARQLQueryFramer = NodeProperties
    node_types: SPARQLQueryFramer = NodeTypes
    reified_relations: SPARQLQueryFramer = ReifiedRelations
    relation_properties: SPARQLQueryFramer = RelationProperties
    relation_types: SPARQLQueryFramer = RelationTypes

    @classmethod
    def process_properties(
        cls, iri: URIRef, properties: DataFrame, strict: bool = False
    ) -> Dict:
        """Use a DataFrame of properties to create a dictionary of data for the
          networkx object.

        :param iri: the rdflib.term.URIRef of the node/edge
        :param properties: a DataFrame of properties
        :param strict: boolean for Literal conversion (True = supported types only)
        :return: a dictionary of the processed properties
        """
        nx_properties = {"iri": iri}
        # Groups are based on common predicates and processed individually
        for group_predicate, group_df in properties.groupby(["predicate"]):
            group_values = group_df["value"].values

            # Get simplified representation and add to class attribute
            if group_predicate not in cls.converted_predicates:
                cls.converted_predicates[group_predicate] = cls.uri_to_short_id(
                    group_predicate, ns=cls.initNs
                )

            # If a predicate is connected to multiple objects (turn into tuple)
            if len(group_df) > 1:
                # Currently does not support mix of Literal/Bnode/URIRef objects
                if len(set(map(type, group_values))) > 1:
                    raise ValueError(
                        "All objects of a predicate must be of the same type."
                    )

                if type(group_values[0]) == Literal:
                    # Convert multiple Literals based on datatype
                    cast_value = tuple(
                        map(cast_literal, group_values, (strict,) * len(group_values))
                    )
                else:
                    # Do not convert multiple URIRef/BNode
                    cast_value = tuple(group_values)

            else:
                # Process a single value
                value = group_values[0]
                if isinstance(value, Literal):
                    cast_value = cast_literal(value, strict=strict)
                else:
                    cast_value = value

            nx_properties[cls.converted_predicates[group_predicate]] = cast_value
        return nx_properties

    @classmethod
    def transform_nodes(
        cls, rdf_graph: RDFGraph, node_iris: List[URIRef] = None, strict: bool = False
    ) -> Dict[URIRef, dict]:
        """Returns node data for all nodes.

        TODO #59 & #60

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :param node_iris: an optional list of IRIs/URIs to use in place of cls.node_iris
        :param strict: boolean for Literal conversion (True = supported types only)
        :return: dictionary (indexed by node IRI) containing the node data for networkx
        """
        node_data = {}

        if node_iris is None:
            # TODO paginate (LIMIT+OFFSET) for batch processing?
            node_iris = list(cls.node_iris.run_query(rdf_graph)["iri"])

        for node_iri in node_iris:
            # TODO this isn't actually used (should it be?)
            # TODO use URItoShortID?
            # Get the types for the node (must bind iri)
            # types = cls.node_types.run_query(rdf_graph, iri=node_iri)
            # type_list = tuple(map(cls.uri_to_id, types["type_"].values))

            # Get the properties for the node (must bind iri)
            properties = cls.node_properties.run_query(rdf_graph, iri=node_iri)
            nx_node_properties = cls.process_properties(
                node_iri, properties, strict=strict
            )
            node_data[node_iri] = nx_node_properties

        return node_data

    @classmethod
    def transform_edges(
        cls, rdf_graph: RDFGraph, strict: bool = False
    ) -> Dict[URIRef, dict]:
        """Returns edge data for all edges.

        TODO #59 & #60

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :param strict: boolean for Literal conversion (True = supported types only)
        :return: dictionary (indexed by node IRI) containing the edge data for networkx
        """
        edge_data = {}

        # Get properties for basic relationships
        # Overwrite namespace for fictitious IRI (uses base)
        cls.relation_types.initNs = cls.initNs
        basic_relations = cls.relation_types.run_query(rdf_graph)
        for iri, predicate, source, target in basic_relations.values:
            # Get simplified representation and add to class attribute
            if predicate not in cls.converted_predicates:
                cls.converted_predicates[predicate] = URItoShortID(
                    predicate, ns=cls.initNs
                )

            edge_data[iri] = {
                "source": source,
                "target": target,
                "attrs": {"_label": cls.converted_predicates[predicate]},
            }

        # Get properties for reified relations
        reified_relations = cls.reified_relations.run_query(rdf_graph)
        for iri, predicate, source, target in reified_relations.values:
            properties = cls.relation_properties.run_query(rdf_graph, iri=iri)
            nx_edge_properties = cls.process_properties(iri, properties, strict=strict)
            # TODO add _label to edge_data?
            edge_data[iri] = {
                "source": source,
                "target": target,
                "attrs": nx_edge_properties,
            }

        return edge_data

    @classmethod
    def convert_nodes(
        cls,
        node_uris: List[URIRef],
        rdf_graph: RDFGraph,
        namespaces: Union[
            NamespaceManager, Dict[str, Union[str, Namespace, URIRef]]
        ] = None,
        strict: bool = False,
    ) -> MultiDiGraph:
        """Converts a set of RDF nodes into a set of LPG nodes (networkx).

        :param node_uris: a list of node URIs to be converted
        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :param namespaces: the collection of namespaces used to simplify URIs
        :param strict: boolean for Literal conversion (True = supported types only)
        :return: the networkx MultiDiGraph containing all collected node/edge data
        """
        if cls.initNs is None:
            if namespaces is None:
                namespaces = dict(rdf_graph.namespaces())
            cls.initNs = dict(namespaces)

        nx_graph = MultiDiGraph()

        # TODO pass list of nodes to this function
        # TODO add edges for these nodes
        nodes = cls.transform_nodes(rdf_graph, node_iris=node_uris, strict=strict)
        for node_iri, node_attrs in nodes.items():
            nx_graph.add_node(node_iri, **node_attrs)

        return nx_graph

    @classmethod
    def convert(
        cls,
        rdf_graph: RDFGraph,
        namespaces: Union[
            NamespaceManager, Dict[str, Union[str, Namespace, URIRef]]
        ] = None,
        strict: bool = False,
        external_graph: RDFGraph = None,
    ) -> MultiDiGraph:
        """The main method for converting an RDF graph to a networkx representation.

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :param namespaces: the collection of namespaces used to simplify URIs
        :param strict: boolean for Literal conversion (True = supported types only)
        :param external_graph: if provided, the converter will also return connected nodes
           (e.g. triple targets) as LPG nodes using the external_graph to collect their data
        :return: the networkx MultiDiGraph containing all collected node/edge data
        """
        if cls.initNs is None:
            if namespaces is None:
                namespaces = dict(rdf_graph.namespaces())
            cls.initNs = dict(namespaces)
            if "base" not in cls.initNs:
                warn("No base namespace specified. Defaulting to example namespace")
                cls.initNs["base"] = URIRef("https://www.example.com/RDF2NX/")

        nx_graph = MultiDiGraph()

        nodes = cls.transform_nodes(rdf_graph, strict=strict)
        edges = cls.transform_edges(rdf_graph, strict=strict)

        for node_iri, node_attrs in nodes.items():
            nx_graph.add_node(node_iri, **node_attrs)

        for edge_iri, edge_data in edges.items():
            try:
                edge_source = edge_data.get("source")
                edge_target = edge_data.get("target")
                edge_attrs = edge_data.get("attrs")
            except AttributeError as err:
                logger.warning("Unable to get expected edge attributes.")
                raise err

            if edge_source in nx_graph.nodes and edge_target in nx_graph.nodes:
                edge_attrs["iri"] = edge_iri
                nx_graph.add_edge(edge_source, edge_target, **edge_attrs)
            elif external_graph is not None:
                if edge_source not in nx_graph.nodes:
                    node_data = cls.transform_nodes(external_graph, node_iris=[edge_source], strict=strict)
                    assert edge_source in node_data
                    nx_graph.add_node(edge_source, **node_data[edge_source])
                elif edge_target not in nx_graph.nodes:
                    node_data = cls.transform_nodes(external_graph, node_iris=[edge_target], strict=strict)
                    assert edge_target in node_data
                    nx_graph.add_node(edge_target, **node_data[edge_target])
                nx_graph.add_edge(edge_source, edge_target, **edge_attrs)
            else:
                if edge_source not in nx_graph.nodes:
                    logger.info(
                        f"Edge source '{edge_source}' missing in graph. Skipping..."
                    )
                elif edge_target not in nx_graph.nodes:
                    logger.info(
                        f"Edge target '{edge_target}' missing in graph. Skipping..."
                    )

        return nx_graph

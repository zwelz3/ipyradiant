# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import logging
import re
from copy import deepcopy

from pandas import DataFrame
from rdflib import Graph, URIRef
from rdflib.plugins.sparql import prepareQuery

# pattern used to identify bindings in a sparql string
BINDING_PATTERN = re.compile(r"\?([\w]*)")


def build_values(string: str, values: dict) -> str:
    """
    :param string: the query string to format (must have two format slots)
    :param values: a dictionary of values to assign, with the following structure::
        values = {
            "var_1": [value_1, ..., value_n],
            ...
            "var_n": [value_1, ..., value_n]
        }
    Note: values can be strings, rdflib.URIRefs, or preformatted SPARQL IRIs, e.g. '<IRI>'.
    :return: the formatted string with the given values

    TODO should values be a NamedTuple with different structure to improve readability?
    """
    assert values, "Input values cannot be empty."
    values = deepcopy(values)
    assert (
        len(set([len(_) for _ in values.values()])) == 1
    ), "All values must have equal length."
    # TODO assert keys are valid for var assignment

    # Convert any values that are necessary (e.g. URIRefs)
    for var, values_list in values.items():
        for ii, value in enumerate(values_list):
            if isinstance(value, str):
                if value.startswith("<") and value.endswith(">"):
                    continue
                values[var][ii] = f"<{URIRef(value)}>"
            elif isinstance(value, URIRef):
                values[var][ii] = f"<{value}>"

    # Rotates values dict to be specified per instance as required by the VALUES block
    value_vars = " ".join([f"?{value}" for value in values.keys()])
    values_transposed = [list(i) for i in zip(*[values for values in values.values()])]
    values_block = "\n\t    ".join(
        f"({' '.join([i for i in row])})" for row in values_transposed
    )

    return string.format(
        value_vars,
        values_block,
    )


class SPARQLQueryFramer:
    """A generic Class for building and running SPARQL queries with rdflib.

    TODO possible to static property sparql and load from file or overload string?
    TODO lexer method for sparql string

    :param initNs: a dict of namespace {term: namespace} to use in rdflib prepareQuery
    :param classBindings: a dict of bindings to set at the class level
        (independent of initBindings).
    :param sparql: a SPARQL parse-able string to use during query
    :param index: an index list to use when building a query result DataFrame
    :param columns: a list of strings to use as column headers for
        the query result DataFrame
    :param query: a valid rdflib Query object
    """

    initNs = {}
    classBindings = {}
    sparql = ""
    index = []
    columns = None
    query = None

    # low cost trait (previous cls.sparql state)
    p_sparql = ""

    @classmethod
    def print_vars(cls) -> None:
        """Utility function to print variables that may be used as bindings"""
        logging.info("Only variables in the SELECT line are printed.")
        tmp_graph = Graph()
        # Run fake query to print vars
        if not cls.query:
            tmp_query = prepareQuery(cls.sparql, initNs=cls.initNs)
            tmp_res = tmp_graph.query(tmp_query)
        else:
            tmp_res = tmp_graph.query(cls.query)
        print("Vars:\n", sorted([str(var) for var in tmp_res.vars]))

    @classmethod
    def print_potential_bindings(cls) -> None:
        """Utility function to print bindings in the sparql string.
        Note, this method is regex-based, and may not be 100% accurate.
        """
        if not cls.sparql:
            print("No sparql string set in class.")
            return None

        logging.warning("Bindings are not guaranteed to be 100% accurate")
        potential_bindings = [
            str(binding) for binding in set(BINDING_PATTERN.findall(cls.sparql))
        ]
        print("Potential bindings:\n", sorted(potential_bindings))
        return None

    @classmethod
    def run_query(
        cls,
        graph: Graph,
        initBindings: dict = None,
        **initBindingsKwarg,
    ) -> DataFrame:
        """Runs a query with optional initBindings, and returns the results as a
          pandas.DataFrame.

        :param graph: the rdflib.graph.Graph to be queried
        :param initBindings: a dictionary of bindings where the key is the variable in
            the sparql string, and the value is the URI/Literal to BIND to the variable.
        :param initBindingsKwarg: kwarg version of initBindings
        :return: pandas.DataFrame containing the contents of the SPARQL query
            result from rdflib
        """
        assert (
            cls.query or cls.sparql
        ), "No rdflib Query or SPARQL string has been set for the class."

        # Check if query should be updated due to stale sparql string
        update_query = cls.p_sparql != cls.sparql
        if not cls.query or update_query:
            cls.query = prepareQuery(cls.sparql, initNs=cls.initNs)

        # note: merge method kwargs with default class bindings
        if initBindings:
            all_bindings = {**cls.classBindings, **initBindings, **initBindingsKwarg}
        else:
            all_bindings = {**cls.classBindings, **initBindingsKwarg}

        result = graph.query(cls.query, initBindings=all_bindings)

        if cls.columns is None:
            # Try to infer from query vars
            try:
                cls.columns = [str(var) for var in result.vars]
            except TypeError:
                # no columns. Probably an ASK or CONSTRUCT query
                logging.debug(
                    "No columns passed, and unable to infer. "
                    "Therefore, no columns were assigned to the DataFrame."
                )

        df = DataFrame(result, columns=cls.columns)

        # update low cost trait
        cls.p_sparql = cls.sparql

        if cls.index:
            return df.set_index(cls.index)
        return df

""" a query constructor
"""
# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import ipywidgets as W
import traitlets as T

from .query_form import QueryInput
from .visualize import QueryColorizer

# TODO improve
query_template = """{}
{}
WHERE {}
"""


class QueryConstructor(W.HBox):
    """TODO
    - way better templating and more efficient formatting
    - replace individual observers with larger observer
    - move build_query to standalone function
    """

    convert_arrow = T.Instance(W.Image)
    query_input = T.Instance(W.VBox)
    formatted_query = T.Instance(
        QueryColorizer, kw=dict(layout=W.Layout(max_height="260px"))
    )

    # traits from children
    namespaces = T.Unicode()
    query_type = T.Unicode(default_value="SELECT")
    query_line = T.Unicode(allow_none=True)
    query_body = T.Unicode()
    query = T.Unicode()

    log = W.Output()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query_input = QueryInput()

        # Inherit traits with links TODO easier way?
        T.link((self.query_input.namespaces, "namespaces"), (self, "namespaces"))
        T.link((self.query_input.header, "dropdown_value"), (self, "query_type"))
        T.link((self.query_input.header, "header_value"), (self, "query_line"))
        T.link((self.query_input.body.body, "value"), (self, "query_body"))
        T.dlink((self, "query"), (self.formatted_query, "query"))

        self.children = tuple([self.query_input, self.formatted_query])

    @log.capture()
    def build_query(self):
        # get values TODO improve
        namespaces = self.namespaces
        query_type = self.query_type
        query_line = self.query_line
        query_body = self.query_body or self.query_input.body.body.placeholder

        # update query_body
        query_body = "\t\n".join(
            query_body.split("\n")
        )  # TODO this isn't actually formatting properly

        header_str = ""
        # TODO move these to module vars
        if query_type in {"SELECT", "SELECT DISTINCT"}:
            if query_line == "":
                query_line = "*"
            header_str = f"{query_type} {query_line}"
        elif query_type == "ASK":
            header_str = query_type
        elif query_type == "CONSTRUCT":
            if query_line == "":
                query_line = "{?s ?p ?o}"
            header_str = f"{query_type} {query_line}"
        else:
            with self.log:
                raise ValueError(f"Unexpected query type: {query_type}")

        return query_template.format(
            namespaces,
            header_str,
            query_body,
        )

    @T.observe(
        "namespaces",
        "query_type",
        "query_line",
        "query_body",
    )
    def update_query(self, change):
        self.query = self.build_query()

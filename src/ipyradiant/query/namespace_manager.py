""" a namespace manager
"""
# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import re

import ipywidgets as W
import traitlets as T
from rdflib.namespace import RDF, RDFS, XSD

default_ns = {
    "rdfs": RDFS,
    "rdf": RDF,
    "xsd": XSD,
}


def collapse_namespace(namespaces, cell):
    """
    TODO prevent from collapsing a partial namespace
    e.g.
    PREFIX ex: <https://example.org/>
    URI = https://example.org/thing/stuff

    current behavior: ex:thing/stuff
    expected behavior: no collapsing
    """
    uf_link = """<a href=\"{}" target=\"_blank\">{}</a>"""

    if isinstance(namespaces, dict):
        namespaces = tuple(namespaces.items())

    or_statement = "|".join([uri for _, uri in namespaces])
    pattern = f"({or_statement}).*"
    quick_check = re.match(pattern, str(cell))
    if quick_check:
        for term, uri in namespaces:
            if cell.startswith(uri):
                return uf_link.format(cell, str(cell).replace(uri, term + ":"))
    else:
        return uf_link.format(cell, cell)


class NamespaceManager(W.VBox):
    """
    TODO perform validation on the user_namespaces_value to ensure valid prefixes exist?
    TODO better default namespaces? (maybe module import?)
    """

    default_namespaces = T.Instance(W.HTML)
    included_namespaces_value = T.Unicode()
    user_namespaces = T.Instance(W.Textarea)
    user_namespaces_value = T.Unicode()
    namespaces = T.Unicode()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.children = tuple([self.default_namespaces, self.user_namespaces])
        self.namespaces = str(self.included_namespaces_value)

    @T.default("default_namespaces")
    def make_default_namespaces(self):
        default_namespaces = W.HTML(
            """
            <p style="color:blue;font-size:12px;">PREFIX xsd:
                <i>&#60;http://www.w3.org/2001/XMLSchema#&#62;</i></p>
            <p style="color:blue;font-size:12px;">PREFIX rdfs:
                <i>&#60;http://www.w3.org/2000/01/rdf-schema#&#62;</i></p>
            <p style="color:blue;font-size:12px;">PREFIX rdf:
                <i>&#60;http://www.w3.org/1999/02/22-rdf-syntax-ns#&#62;</i></p>
            """
        )
        return default_namespaces

    @T.default("user_namespaces")
    def make_default_user_namespaces(self):
        user_namespaces = W.Textarea(
            placeholder="PREFIX ex: <https://www.example.org/>",
            layout=W.Layout(width="80%"),
        )
        T.link((user_namespaces, "value"), (self, "user_namespaces_value"))
        return user_namespaces

    @T.default("included_namespaces_value")
    def make_included_namespaces_value(self):
        return "\n".join([f"PREFIX {ns}: <{uri}>" for ns, uri in default_ns.items()])

    @T.observe("user_namespaces_value")
    def update_namespaces(self, changes):
        self.namespaces = "\n".join([self.included_namespaces_value, changes.new])

""" loading widgets
"""
# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import ipywidgets as W
import traitlets as T
from rdflib import BNode, Graph

from .base import BaseLoader
from .upload import UpLoader


class FileManager(W.HBox):
    """Wraps a file selector with graph info."""

    loader = T.Instance(BaseLoader, default_value=UpLoader())
    graph = T.Instance(Graph, kw={})
    graph_id = T.Instance(BNode)
    msg = T.Instance(W.HTML)

    def build_html(self):
        """Basic HTML string with graph length."""
        if len(self.graph) == 0:
            return "<i>No graph loaded.</i>"
        else:
            return f"<i>Loaded graph with {len(self.loader.graph)} triples.</i>"

    @T.validate("children")
    def validate_children(self, proposal):
        """
        Validate method for default children.
        This is necessary because @trt.default does not work on children.
        """
        children = proposal.value
        if not children:
            children = (self.loader, self.msg)
        return children

    @T.default("msg")
    def make_default_msg(self):
        return W.HTML(self.build_html())

    @T.observe("graph_id")
    def update_msg(self, change):
        self.msg.value = self.build_html()

    @T.observe("loader")
    def update_loader(self, change):
        T.link((self.loader, "graph"), (self, "graph"))
        T.link((self.loader, "graph_id"), (self, "graph_id"))

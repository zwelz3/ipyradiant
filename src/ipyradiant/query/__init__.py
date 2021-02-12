""" query widgets
"""
# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

__all__ = ["BasicQueryWidget", "QueryWidget", "service_patch_rdflib"]

from .app import QueryWidget as BasicQueryWidget
from .query_widget import QueryWidget
from .utils import service_patch_rdflib

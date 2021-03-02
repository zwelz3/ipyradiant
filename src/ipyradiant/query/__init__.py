""" query widgets
"""
# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

__all__ = ["LegacyQueryWidget", "QueryWidget", "service_patch_rdflib"]

from .app import QueryWidget
from .query_widget import QueryWidget as LegacyQueryWidget
from .utils import service_patch_rdflib

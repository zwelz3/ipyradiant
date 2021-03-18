# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.
import ipywidgets as W
import traitlets as T
from rdflib import URIRef


class SelectURI(W.Select):
    """Widget for selecting URIs that have custom representations

    TODO can this be combined with SelectMultipleURI?
    """

    pithy_uris = T.List()  # tuple of uri class instances (e.g. CustomURI)
    uri_map = T.List()  # T.Tuple(T.Instance(URIRef), T.Instance(CustomURI))

    @T.observe("pithy_uris")
    def update_pithy_uris(self, change):
        if change.old == change.new:
            return

        if self.pithy_uris is None:
            raise ValueError("Value 'pithy_uris' cannot be None.")
        # TODO relax below requirement?
        assert (
            len(set(map(type, self.pithy_uris))) < 2
        ), "All URIs must be of the same type."
        assert all(
            map(lambda x: hasattr(x, "uri"), self.pithy_uris)
        ), "URI objects must have a 'uri' attr."

        # replace uri_map
        self.uri_map = list((uri.uri, uri) for uri in self.pithy_uris)

        # replace options
        self.options = list(
            sorted([tup[::-1] for tup in self.uri_map], key=lambda x: str(x[0]))
        )

    def get_pithy_uri(self, uri: URIRef):
        """Helper method to return a custom URI representation for a URIRef in the
        uri_map.

        TODO support multiple uris

        :param uri: the rdflib URIRef for a URI in the uri_map
        :return: the target in the uri_map (a custom URI class instance)
        """
        try:
            return dict(self.uri_map)[uri]
        except KeyError:
            raise KeyError(f"URIRef '<{uri}>' not in uri_map.")


class SelectMultipleURI(W.SelectMultiple):
    """Widget for selecting URIs that have custom representations"""

    pithy_uris = T.List()  # tuple of uri class instances (e.g. CustomURI)
    uri_map = T.List()  # T.Tuple(T.Instance(URIRef), T.Instance(CustomURI))

    @T.observe("pithy_uris")
    def update_pithy_uris(self, change):
        if change.old == change.new:
            return

        if self.pithy_uris is None:
            raise ValueError("Value 'pithy_uris' cannot be None.")
        # TODO relax below requirement?
        assert (
            len(set(map(type, self.pithy_uris))) < 2
        ), "All URIs must be of the same type."
        assert all(
            map(lambda x: hasattr(x, "uri"), self.pithy_uris)
        ), "URI objects must have a 'uri' attr."

        # replace uri_map
        self.uri_map = list((uri.uri, uri) for uri in self.pithy_uris)

        # replace options
        self.options = list(
            sorted([tup[::-1] for tup in self.uri_map], key=lambda x: str(x[0]))
        )

    def get_pithy_uri(self, uri: URIRef):
        """Helper method to return a custom URI representation for a URIRef in the
        uri_map.

        TODO support multiple uris

        :param uri: the rdflib URIRef for a URI in the uri_map
        :return: the target in the uri_map (a custom URI class instance)
        """
        try:
            return dict(self.uri_map)[uri]
        except KeyError:
            raise KeyError(f"URIRef '<{uri}>' not in uri_map.")

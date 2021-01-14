# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.
from pathlib import Path
from typing import Dict, Union

from rdflib import Graph, URIRef
from rdflib.namespace import Namespace, NamespaceManager

from ..rdf2nx.uri_converter import URItoShortID


class CustomItem:
    """Class used to build list items with custom repr"""

    def __init__(self, _repr: callable, **kwargs):
        self._repr = _repr
        for attr, value in kwargs.items():
            self.__setattr__(attr, value)

    def __repr__(self):
        return self._repr(self)


class PithyURIRef(URIRef):
    """
    Class used for storing uri information.

    TODO rename to PithyURI
    TODO extensive testing and demo notebook
    TODO namespaces support NamespaceManager
    TODO how to specify that this must accept a URIRef and namespace str?
    TODO cast namespace to rdflib.namespace.Namespace?
    TODO can we make this a specialization of URIRef?
    """

    uri = None
    ns = None
    pithy_uri = None

    def __init__(
        self,
        uri: Union[URIRef, str],
        namespaces: Dict[str, Union[str, Namespace, URIRef]] = None,
        converter: callable = URItoShortID,
    ):
        """
        :param uri: the base URI
        :param namespaces: a dictionary of prefix:namespace(s) used to match to the URI
        :param converter: callable that accepts a URI and namespace (ns) and returns pithy_uri
        """
        self.uri = uri
        if namespaces is not None:
            for prefix, ns in namespaces.items():
                if self.get_root(self.uri) == str(ns):
                    self.ns = ns
                    if converter is not None:
                        # Convert with namespace
                        self.id_ = converter(self.uri, ns={prefix: ns})
                    break

        if self.id_ is None and converter is not None:
            # Convert without namespace
            self.id_ = converter(self.uri)
        elif self.id_ is None:
            # Use uri as id_
            self.id_ = str(self.uri)

    def __repr__(self):
        return self.id_ if self.id_ is not None else self.uri

    @staticmethod
    def get_root(uri: URIRef) -> str:
        """Gets the root of a URI (everything but the fragmant, or name)

        TODO should this be a universal util?
        """

        pathlike_uri = Path(uri)
        if uri[-1] == "/":
            return uri

        if "#" in pathlike_uri.name:
            return "#".join(uri.split("#")[0:-1]) + "#"
        else:
            return "/".join(uri.split("/")[0:-1]) + "/"

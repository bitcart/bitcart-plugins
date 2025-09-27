from typing import cast
from urllib.parse import urlsplit, urlunsplit

from .lndhub import LNDHub

ALLOWED_CLIENTS = {"lndhub": LNDHub}


def get_client(node_url: str) -> LNDHub:
    parts = urlsplit(node_url, allow_fragments=True)
    if parts.scheme not in ALLOWED_CLIENTS:
        raise ValueError("Unsupported client")
    netloc_parts = parts.netloc.split("@")
    if len(netloc_parts) != 2:
        raise ValueError("Invalid URL")
    netloc = netloc_parts[1]
    reconstruction_parts = (
        parts.scheme,
        netloc,
        parts.path,
        parts.query,
        parts.fragment,
    )
    reconstructed_url = urlunsplit(reconstruction_parts).replace(f"{parts.scheme}://", "")
    return ALLOWED_CLIENTS[parts.scheme](reconstructed_url, cast(str, parts.username), cast(str, parts.password))

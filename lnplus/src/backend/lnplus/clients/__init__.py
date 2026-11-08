from urllib.parse import urlsplit

from .base_client import LightningClient
from .cln import CLN
from .lnd import LND
from .lndhub import LNDHub

ALLOWED_CLIENTS: dict[str, type[LightningClient]] = {"lndhub": LNDHub, "cln": CLN, "lnd": LND}


def get_client(node_url: str) -> LightningClient:
    client_cls = ALLOWED_CLIENTS.get(urlsplit(node_url).scheme)
    if client_cls is None:
        raise ValueError("Unsupported client")
    return client_cls.from_url(node_url)

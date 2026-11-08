import base64
import re
from decimal import Decimal
from typing import Any, Self

from .base_client import MSAT_PER_BTC, RequestError, RestNodeClient, btc_to_msat, split_node_url

GRPC_NOT_FOUND = 5
HEX_MACAROON = re.compile(r"(?:[0-9a-fA-F]{2})+")


class LND(RestNodeClient):
    """LND client using its REST API and macaroon authentication."""

    api_name = "LND REST"

    def __init__(self, url: str, macaroon: str) -> None:
        super().__init__(url, {"Grpc-Metadata-macaroon": macaroon})

    @classmethod
    def from_url(cls, node_url: str) -> Self:
        url, macaroon, _ = split_node_url(node_url)
        if not macaroon or not HEX_MACAROON.fullmatch(macaroon):
            raise ValueError("LND macaroon must be hex-encoded")
        return cls(url, macaroon)

    async def get_node_id(self) -> str:
        data = await self._send("GET", "v1/getinfo")
        return data["uris"][0] if data["uris"] else data["identity_pubkey"]

    async def get_balance(self) -> Decimal:
        data = await self._send("GET", "v1/balance/channels")
        return Decimal(data["local_balance"]["msat"]) / MSAT_PER_BTC

    async def create_invoice(self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None) -> tuple[str, str]:
        params: dict[str, Any] = {"value_msat": btc_to_msat(amount)}
        if memo:
            params["memo"] = memo
        if expiry is not None:
            params["expiry"] = expiry
        result = await self._send("POST", "v1/invoices", json=params)
        return result["payment_request"], base64.b64decode(result["r_hash"]).hex()

    async def check_payment(self, rhash: str) -> Decimal | None:
        try:
            invoice = await self._send("GET", f"v1/invoice/{rhash}")
        except RequestError as e:
            if e.code == GRPC_NOT_FOUND:
                return None
            raise
        if invoice["state"] != "SETTLED":
            return None
        return Decimal(invoice["amt_paid_msat"]) / MSAT_PER_BTC

from decimal import Decimal
from typing import Any, Self
from uuid import uuid4

from api.plugins import get_plugin_logger

from .base_client import MSAT_PER_BTC, RestNodeClient, btc_to_msat, split_node_url

logger = get_plugin_logger(__name__)

ACTIVE_CHANNEL_STATES = ("CHANNELD_NORMAL", "CHANNELD_AWAITING_SPLICE")


class CLN(RestNodeClient):
    """Core Lightning client using native CLNRest and rune authentication."""

    api_name = "CLNRest"

    def __init__(self, url: str, rune: str) -> None:
        super().__init__(url, {"Rune": rune})

    @classmethod
    def from_url(cls, node_url: str) -> Self:
        url, rune, _ = split_node_url(node_url)
        if not rune or not rune.strip():
            raise ValueError("CLN rune is required")
        return cls(url, rune)

    async def _request(self, method: str, **params: Any) -> dict[str, Any]:
        return await self._send("POST", f"v1/{method}", json=params)

    async def get_node_id(self) -> str:
        data = await self._request("getinfo")
        pubkey = data["id"]
        for address in data.get("address", []):
            if address["type"] not in ("dns", "ipv4", "ipv6", "torv2", "torv3"):
                continue
            host = address["address"]
            if address["type"] == "ipv6":
                host = f"[{host}]"
            return f"{pubkey}@{host}:{address['port']}"
        return pubkey

    async def get_balance(self) -> Decimal:
        result = await self._request("listfunds")
        channels = (channel for channel in result["channels"] if channel["state"] in ACTIVE_CHANNEL_STATES)
        return sum((Decimal(channel["our_amount_msat"]) for channel in channels), Decimal(0)) / MSAT_PER_BTC

    async def create_invoice(self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None) -> tuple[str, str]:
        params: dict[str, Any] = {
            "amount_msat": btc_to_msat(amount) or "any",
            "label": f"bitcart-{uuid4().hex}",
            "description": memo or "",
        }
        if expiry is not None:
            params["expiry"] = expiry
        result = await self._request("invoice", **params)
        for key, value in result.items():
            if key.startswith("warning_"):
                logger.warning(f"Core Lightning invoice {result['payment_hash']}: {key}: {value}")
        return result["bolt11"], result["payment_hash"]

    async def check_payment(self, rhash: str) -> Decimal | None:
        result = await self._request("listinvoices", payment_hash=rhash)
        for invoice in result["invoices"]:
            if invoice["status"] == "paid":
                return Decimal(invoice["amount_received_msat"]) / MSAT_PER_BTC
        return None

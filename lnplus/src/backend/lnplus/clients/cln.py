from decimal import Decimal
from typing import Any, Self
from urllib.parse import urlsplit
from uuid import uuid4

from aiohttp import ClientTimeout, ContentTypeError

from .base_client import HTTPProvider, RequestError, split_node_url

MSAT_PER_BTC = Decimal(10**11)
NODE_IDS: dict[str, str] = {}


class CLN:
    """Core Lightning client using native CLNRest and rune authentication."""

    supports_amountless = True

    def __init__(self, url: str, rune: str) -> None:
        if "://" not in url:
            url = f"https://{url}"
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.port == 0
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Invalid CLNRest URL")
        base_url = parts._replace(path=parts.path.rstrip("/").removesuffix("/v1")).geturl()
        self.client = HTTPProvider(base_url)
        self.rune = rune

    @classmethod
    def from_url(cls, node_url: str) -> Self:
        url, rune, _ = split_node_url(node_url)
        if not rune or not rune.strip():
            raise ValueError("CLN rune is required")
        return cls(url, rune)

    async def _request(self, method: str, **params: Any) -> dict[str, Any]:
        async with self.client.session.request(
            "POST",
            f"{self.client.url}/v1/{method}",
            json=params,
            headers={"Rune": self.rune},
            timeout=ClientTimeout(total=5 * 60),
            allow_redirects=False,
        ) as response:
            try:
                data = await response.json()
            except (ContentTypeError, ValueError):
                raise RequestError(f"CLNRest {method} returned invalid JSON (HTTP {response.status})") from None
            if not isinstance(data, dict):
                raise RequestError(f"CLNRest {method} returned an invalid response (HTTP {response.status})")
            if response.status >= 300 or "error" in data or ("code" in data and "message" in data):
                error = data.get("error", data)
                message = error.get("message", "Request failed") if isinstance(error, dict) else str(error)
                raise RequestError(f"CLNRest {method} failed (HTTP {response.status}): {message}")
            return data

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

    @property
    async def node_id(self) -> str:
        if self.client.url not in NODE_IDS:
            NODE_IDS[self.client.url] = await self.get_node_id()
        return NODE_IDS[self.client.url]

    async def get_balance(self) -> Decimal:
        """Return the local balance of normal Lightning channels in BTC."""
        result = await self._request("listfunds")
        balance_msat = sum(
            (Decimal(channel["our_amount_msat"]) for channel in result["channels"] if channel["state"] == "CHANNELD_NORMAL"),
            Decimal(0),
        )
        return balance_msat / MSAT_PER_BTC

    async def create_invoice(self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None) -> tuple[str, str]:
        """Create a BOLT11 invoice with an optional lifetime in seconds."""
        if not amount.is_finite() or amount < 0:
            raise ValueError("Invoice amount must be finite and not negative")
        amount_msat = amount * MSAT_PER_BTC
        if amount_msat != amount_msat.to_integral_value():
            raise ValueError("Invoice amount must be a whole number of millisatoshis")
        params: dict[str, Any] = {
            "amount_msat": int(amount_msat) or "any",
            "label": f"bitcart-{uuid4().hex}",
            "description": memo or "",
        }
        if expiry is not None:
            params["expiry"] = expiry
        result = await self._request("invoice", **params)
        return result["bolt11"], result["payment_hash"]

    async def check_payment(self, rhash: str) -> Decimal | None:
        result = await self._request("listinvoices", payment_hash=rhash)
        for invoice in result["invoices"]:
            if invoice["status"] == "paid":
                return Decimal(invoice["amount_received_msat"]) / MSAT_PER_BTC
        return None

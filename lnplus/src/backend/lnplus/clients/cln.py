from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from aiohttp import ClientTimeout, ContentTypeError

from .base_client import HTTPProvider, RequestError

MSAT_PER_BTC = Decimal(10**11)


class CLN:
    """Core Lightning client using native CLNRest and rune authentication."""

    def __init__(self, url: str, rune: str, _: any) -> None:
        if not rune or not rune.strip():
            raise ValueError("CLN rune is required")
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
        self._node_id: str | None = None

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
        if self._node_id is None:
            self._node_id = await self.get_node_id()
        return self._node_id

    async def get_balance(self) -> Decimal:
        """Return the total local Lightning channel balance in BTC."""
        result = await self._request("listfunds")
        balance_msat = sum(
            (Decimal(str(channel["our_amount_msat"]).removesuffix("msat")) for channel in result["channels"]),
            Decimal(0),
        )
        return balance_msat / MSAT_PER_BTC

    async def create_invoice(self, amount: Decimal, memo: str | None = None) -> tuple[str, str]:
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Invoice amount must be positive and finite")
        amount_msat = amount * MSAT_PER_BTC
        if amount_msat != amount_msat.to_integral_value():
            raise ValueError("Invoice amount must be a whole number of millisatoshis")
        result = await self._request(
            "invoice",
            amount_msat=int(amount_msat),
            label=f"bitcart-{uuid4().hex}",
            description=memo if memo is not None else "",
        )
        return result["bolt11"], result["payment_hash"]

    async def check_payment(self, rhash: str) -> bool:
        result = await self._request("listinvoices", payment_hash=rhash)
        return any(invoice["payment_hash"] == rhash and invoice["status"] == "paid" for invoice in result["invoices"])

    async def lndecode(self, invoice: str) -> dict[str, Any]:
        result = await self._request("decode", string=invoice)
        if not result.get("valid") or result.get("type") != "bolt11 invoice":
            raise RequestError("CLNRest decode did not return a valid BOLT11 invoice")
        return result

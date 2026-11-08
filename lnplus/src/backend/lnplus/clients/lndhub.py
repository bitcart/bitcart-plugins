import time
from decimal import Decimal
from typing import Any, Self

from .base_client import (
    AmountlessNotSupportedError,
    RequestError,
    btc_to_msat,
    get_provider,
    normalize_base_url,
    split_node_url,
)

SATS_PER_BTC = Decimal(10**8)
BAD_AUTH_CODE = 1
USER_INVOICES_LIMIT = 200
USER_INVOICES_REFRESH_SECONDS = 20
TOKENS: dict[tuple[str, str, str], str] = {}
NODE_IDS: dict[str, str] = {}
USER_INVOICES: dict[tuple[str, str, str], tuple[float, list[dict[str, Any]]]] = {}


class LNDHub:
    def __init__(self, url: str, login: str, password: str) -> None:
        self.client = get_provider(normalize_base_url(url, "LNDHub"))
        self.login = login
        self.password = password

    @classmethod
    def from_url(cls, node_url: str) -> Self:
        url, login, password = split_node_url(node_url)
        if not login or not password:
            raise ValueError("LNDHub login and password are required")
        return cls(url, login, password)

    @property
    def _token_key(self) -> tuple[str, str, str]:
        return self.client.url, self.login, self.password

    async def _authorize(self) -> str:
        data = await self.client.raw_request("POST", "auth", login=self.login, password=self.password)
        if "access_token" not in data:
            raise RequestError(f"LNDHub auth failed: {data.get('message') or data.get('detail')}", data.get("code"))
        TOKENS[self._token_key] = data["access_token"]
        return data["access_token"]

    async def _send(self, method: str, path: str, token: str, **params: Any) -> Any:
        return await self.client.raw_request(method, path, headers={"Authorization": f"Bearer {token}"}, **params)

    async def _request(self, method: str, path: str, **params: Any) -> Any:
        token = TOKENS.get(self._token_key) or await self._authorize()
        result = await self._send(method, path, token, **params)
        if isinstance(result, dict) and result.get("code") == BAD_AUTH_CODE:
            result = await self._send(method, path, await self._authorize(), **params)
        if isinstance(result, dict) and (result.get("error") or "detail" in result):
            message = result.get("message") or result.get("detail")
            raise RequestError(f"LNDHub {path} failed: {message}", result.get("code"))
        return result

    @property
    async def node_id(self) -> str:
        if self.client.url not in NODE_IDS:
            info = await self._request("GET", "getinfo")
            NODE_IDS[self.client.url] = info["uris"][0] if info.get("uris") else info["identity_pubkey"]
        return NODE_IDS[self.client.url]

    async def get_balance(self) -> Decimal:
        result = await self._request("GET", "balance")
        return Decimal(result["BTC"]["AvailableBalance"]) / SATS_PER_BTC

    async def create_invoice(self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None) -> tuple[str, str]:
        sats = btc_to_msat(amount) // 1000
        try:
            result = await self._request("POST", "addinvoice", amt=sats, memo=memo or "")
        except RequestError as e:
            if sats or e.code == BAD_AUTH_CODE:
                raise
            raise AmountlessNotSupportedError(str(e)) from e
        r_hash = result["r_hash"]
        return result["payment_request"], bytes(r_hash["data"]).hex() if isinstance(r_hash, dict) else r_hash

    async def _user_invoices(self) -> list[dict[str, Any]]:
        fetched_at, invoices = USER_INVOICES.get(self._token_key, (0.0, []))
        now = time.monotonic()
        if now - fetched_at >= USER_INVOICES_REFRESH_SECONDS:
            USER_INVOICES[self._token_key] = (now, invoices)
            invoices = await self._request("GET", f"getuserinvoices?limit={USER_INVOICES_LIMIT}")
            USER_INVOICES[self._token_key] = (now, invoices)
        return invoices

    async def check_payment(self, rhash: str) -> Decimal | None:
        invoice = next((invoice for invoice in await self._user_invoices() if invoice.get("payment_hash") == rhash), None)
        if invoice is None or not invoice["ispaid"]:
            return None
        return Decimal(invoice["amt"]) / SATS_PER_BTC

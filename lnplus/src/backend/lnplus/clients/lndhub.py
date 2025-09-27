from decimal import Decimal
from typing import Any

from .base_client import HTTPProvider

TOKENS: dict[str, str] = {}
NODE_IDS: dict[str, str | None] = {}


class LNDHub:
    def __init__(self, url: str, login: str, password: str) -> None:
        self.client = HTTPProvider(url)
        self.login = login
        self.password = password
        self._token: str | None = None
        self._node_id: str | None = None

    async def authorize(self) -> str:
        if TOKENS.get(self.login) is not None:
            return TOKENS[self.login]
        data = await self.client.raw_request("POST", "auth", login=self.login, password=self.password)
        TOKENS[self.login] = data["access_token"]
        return data["access_token"]

    @property
    async def token(self) -> str:
        if self._token is None:
            self._token = await self.authorize()
        return self._token

    async def get_node_id(self) -> str | None:
        if NODE_IDS.get(self.login) is not None:
            return NODE_IDS[self.login]
        data = await self.client.raw_request("GET", "getinfo", headers={"Authorization": await self.token})
        uris = data["uris"]
        NODE_IDS[self.login] = uris[0] if uris else None
        return uris[0] if uris else None

    @property
    async def node_id(self) -> str | None:
        if self._node_id is None:
            self._node_id = await self.get_node_id()
        return self._node_id

    async def get_balance(self) -> Decimal:
        res = await self.client.raw_request(
            "GET",
            "balance",
            headers={"Authorization": await self.token},
        )
        sats_balance = res.get("BTC", {"AvailableBalance": 0}).get("AvailableBalance", 0)
        return Decimal(sats_balance) / Decimal(10**8)

    async def create_invoice(self, amount: Decimal, memo: str | None = None) -> tuple[str, str]:
        sats_amount = int(float(amount) * 10**8)
        result = await self.client.raw_request(
            "POST",
            "addinvoice",
            amt=sats_amount,
            memo=memo,
            headers={"Authorization": await self.token},
        )
        decoded = await self.lndecode(result["payment_request"])
        return result["payment_request"], decoded["payment_hash"]

    async def check_payment(self, rhash: str) -> bool:
        result = await self.client.raw_request(
            "GET",
            f"checkpayment/{rhash}",
            headers={"Authorization": await self.token},
        )
        return result["paid"]

    async def lndecode(self, invoice: str) -> dict[str, Any]:
        return await self.client.raw_request(
            "GET",
            f"decodeinvoice?invoice={invoice}",
            headers={"Authorization": await self.token},
        )

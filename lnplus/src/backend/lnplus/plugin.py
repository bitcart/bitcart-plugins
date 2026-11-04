import asyncio
from decimal import Decimal
from typing import Any, cast

from fastapi import FastAPI, HTTPException

from api import models, utils
from api.plugins import BaseCoin, BasePlugin, CoinServer, DIContainer
from api.services.crud.invoices import InvoiceService
from api.services.payment_processor import PaymentProcessor
from modules.bitcart.lnplus import clients
from modules.bitcart.lnplus.clients.base_client import LightningClient


class LnPlusCoinServer(CoinServer):
    client: LightningClient

    def __init__(self, currency: str, xpub: str | None, **additional_data: Any) -> None:
        super().__init__(currency, xpub, **additional_data)
        self.node_url = xpub
        self.client = clients.get_client(self.node_url) if self.node_url else None  # type: ignore


class LNPlusCoin(BaseCoin):
    server: LnPlusCoinServer

    coin_name = "lnplus"
    friendly_name = "LNPlus"
    xpub_name = "Node URL"
    server_cls = LnPlusCoinServer

    rate_rules = "LNPLUS_X = BTC_X"

    async def validate_key(self, key: str, *args: Any, **kwargs: Any) -> bool:
        if not key:
            return False
        try:
            clients.get_client(key)
        except ValueError as e:
            raise HTTPException(422, f"Wallet key invalid: {e}") from None
        return True

    async def balance(self) -> dict[str, Decimal]:
        balance = await self.server.client.get_balance()
        return {
            "confirmed": balance,
            "unconfirmed": Decimal(0),
            "unmatured": Decimal(0),
            "lightning": Decimal(0),
        }

    async def get_request(self, request_id: str) -> dict[str, Any]:
        is_paid = await self.server.client.check_payment(request_id)
        return {
            "status": "complete" if is_paid else "pending",
            "tx_hashes": [],
            "tx_amounts": {},
            "sent_amount": Decimal(0),
        }

    get_invoice = get_request


class Plugin(BasePlugin):
    name = "lnplus"

    def setup_app(self, app: FastAPI) -> None:
        pass

    async def startup(self) -> None:
        self.context.register_filter("get_cryptos", self.register_method)
        self.context.register_filter("get_coin", self.get_coin)
        self.context.register_filter("create_payment_method", self.create_payment_method)
        self.context.register_filter("get_coin_explorer", self.get_explorer)
        self.context.register_filter("get_divisibility", self.get_divisibility)
        self.context.register_filter("get_wallet_symbol", self.get_wallet_symbol)

    async def shutdown(self) -> None:
        pass

    async def worker_setup(self) -> None:
        asyncio.ensure_future(utils.common.run_repeated(self.process_pending, 2, 0))

    async def register_method(self, cryptos: dict[str, BaseCoin]) -> dict[str, BaseCoin]:
        cryptos["lnplus"] = LNPlusCoin()
        return cryptos

    async def get_explorer(self, explorer: str, coin: str) -> str:
        if coin == "lnplus":
            return ""
        return explorer

    async def get_coin(self, coin: BaseCoin, currency: str, xpub: dict[str, Any]) -> BaseCoin:
        if currency == "lnplus":
            return LNPlusCoin(**xpub)
        return coin

    async def get_divisibility(self, divisibility: int, wallet: models.Wallet, coin: BaseCoin) -> int:
        if wallet.currency == "lnplus":
            return 8
        return divisibility

    async def get_wallet_symbol(self, symbol: str, wallet: models.Wallet, coin: BaseCoin) -> str:
        if wallet.currency == "lnplus":
            return "btc"
        return symbol

    async def create_payment_method(
        self,
        method: dict[str, Any] | None,
        wallet: models.Wallet,
        original_coin: BaseCoin,
        amount: Decimal,
        invoice: models.Invoice,
        product: models.Product | None,
        store: models.Store,
        lightning: bool,
    ) -> dict[str, Any] | object | None:
        if wallet.currency != "lnplus":
            return method
        client = cast(LNPlusCoin, original_coin).server.client
        node_id = await client.node_id
        ln_invoice, rhash = await client.create_invoice(amount, expiry=invoice.expiration_seconds)
        return {
            "currency": "lnplus",
            "payment_address": ln_invoice,
            "payment_url": ln_invoice,
            "lookup_field": rhash,
            "rhash": rhash,
            "lightning": True,
            "node_id": node_id,
        }

    async def process_pending(self) -> None:
        payment_processor = await self.container.get(PaymentProcessor)
        await payment_processor.check_pending("LNPLUS", process_func=self.process_payment)

    async def process_payment(
        self,
        invoice: models.Invoice,
        method: models.PaymentMethod,
        wallet: models.Wallet,
        status: str,
        tx_hashes: list[str],
        sent_amount: Decimal,
        tx_amounts: dict[str, str] | None,
        *,
        di_context: DIContainer,
    ) -> bool:
        invoice_service = await di_context.get(InvoiceService)
        sent_amount = method.amount if status == "complete" else Decimal(0)
        await invoice_service.update_status(invoice, status, method, tx_hashes, sent_amount, tx_amounts=tx_amounts)
        return True

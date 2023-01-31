import asyncio
from decimal import Decimal
from urllib.parse import urlsplit

from api import invoices, settings, utils
from api.plugins import BaseCoin, BasePlugin, CoinServer, register_filter

from . import clients


class LnPlusCoinServer(CoinServer):
    def __init__(self, currency, xpub, **additional_data):
        super().__init__(currency, xpub, **additional_data)
        self.node_url = xpub
        self.client = clients.get_client(self.node_url) if self.node_url else None


class LNPlusCoin(BaseCoin):
    coin_name = "lnplus"
    friendly_name = "LNPlus"
    xpub_name = "Node URL"
    server_cls = LnPlusCoinServer

    async def validate_key(self, key, *args, **kwargs):
        node_url = key
        if not node_url:
            return False
        parsed = urlsplit(node_url, allow_fragments=True)
        if parsed.scheme not in clients.ALLOWED_CLIENTS:
            return False
        return True

    async def balance(self):
        balance = await self.server.client.get_balance()
        return {
            "confirmed": balance,
            "unconfirmed": Decimal(0),
            "unmatured": Decimal(0),
            "lightning": Decimal(0),
        }

    async def rate(self, currency):
        return await settings.settings.cryptos["btc"].rate(currency)

    async def list_fiat(self):
        return await settings.settings.cryptos["btc"].list_fiat()

    async def get_request(self, request_id):
        is_paid = await self.server.client.check_payment(request_id)
        return {
            "status": "complete" if is_paid else "pending",
            "tx_hashes": [],
            "sent_amount": Decimal(0),
        }

    get_invoice = get_request


class Plugin(BasePlugin):
    name = "lnplus"

    def setup_app(self, app):
        pass

    async def startup(self):
        register_filter("get_cryptos", self.register_method)
        register_filter("get_coin", self.get_coin)
        register_filter("create_payment_method", self.create_payment_method)
        register_filter("get_coin_explorer", self.get_explorer)
        register_filter("get_divisibility", self.get_divisibility)
        register_filter("get_wallet_symbol", self.get_wallet_symbol)

    async def shutdown(self):
        pass

    async def worker_setup(self):
        asyncio.ensure_future(utils.common.run_repeated(self.process_pending, 2, 0))

    async def register_method(self, cryptos):
        cryptos["lnplus"] = LNPlusCoin()
        return cryptos

    async def get_explorer(self, explorer, coin):
        if coin == "lnplus":
            return ""
        return explorer

    async def get_coin(self, coin, currency, xpub):
        if currency == "lnplus":
            return LNPlusCoin(**xpub)
        return coin

    async def get_divisibility(self, divisibility, wallet, coin):
        if wallet.currency == "lnplus":
            return 8
        return divisibility

    async def get_wallet_symbol(self, symbol, wallet, coin):
        if wallet.currency == "lnplus":
            return "btc"
        return symbol

    async def create_payment_method(
        self,
        method,
        currency,
        coin,
        amount,
        invoice,
        product,
        store,
        lightning,
    ):
        if currency != "lnplus":
            return method
        ln_invoice = await coin.server.client.create_invoice(amount)
        ln_invoice, rhash = ln_invoice
        return dict(
            currency="lnplus",
            payment_address=ln_invoice,
            payment_url=ln_invoice,
            lookup_field=rhash,
            rhash=rhash,
            lightning=True,
            node_id=await coin.server.client.node_id,
        )

    async def process_pending(self):
        await invoices.check_pending("LNPLUS", process_func=self.process_payment)

    async def process_payment(
        self, invoice, method, wallet, status, tx_hashes, sent_amount
    ):
        sent_amount = method.amount if status == "complete" else Decimal(0)
        await invoices.update_status(invoice, status, method, tx_hashes, sent_amount)

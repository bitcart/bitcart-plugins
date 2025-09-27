from fastapi import FastAPI

from api.plugins import BasePlugin
from modules.bitcart.rpc_plugin.views import router


class Plugin(BasePlugin):
    name = "rpc_plugin"

    def setup_app(self, app: FastAPI) -> None:
        app.include_router(router, prefix="/cryptos", tags=["cryptos"])

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def worker_setup(self) -> None:
        pass

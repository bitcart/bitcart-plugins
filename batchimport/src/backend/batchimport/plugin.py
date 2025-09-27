from fastapi import FastAPI

from api.plugins import BasePlugin
from modules.bitcart.batchimport.views import router


class Plugin(BasePlugin):
    name = "batchimport"

    def setup_app(self, app: FastAPI) -> None:
        app.include_router(router, prefix="/batchimport", tags=["batchimport"])

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def worker_setup(self) -> None:
        pass

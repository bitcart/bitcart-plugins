from decimal import Decimal

from fastapi import FastAPI

from api import models
from api.plugins import BasePlugin, update_metadata

from .views import router


class Plugin(BasePlugin):
    name = "ratings"

    def setup_app(self, app: FastAPI) -> None:
        app.include_router(router)

    async def startup(self) -> None:
        self.context.register_filter("db_create_product", self.add_rating)

    async def shutdown(self) -> None:
        pass

    async def worker_setup(self) -> None:
        pass

    async def add_rating(self, product: models.Product) -> models.Product:
        product = update_metadata(product, "rating", Decimal(0))
        return update_metadata(product, "rating_count", 0)

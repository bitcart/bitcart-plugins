from decimal import Decimal

from api import models
from api.plugins import BasePlugin, register_filter, update_metadata

from .views import router


class Plugin(BasePlugin):
    name = "ratings"

    def setup_app(self, app):
        app.include_router(router)

    async def startup(self):
        register_filter("db_create_product", self.add_rating)

    async def shutdown(self):
        pass

    async def worker_setup(self):
        pass

    async def add_rating(self, product):
        product = await update_metadata(models.Product, product.id, "rating", Decimal(0))
        product = await update_metadata(models.Product, product.id, "rating_count", 0)
        return product

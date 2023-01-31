from api.plugins import BasePlugin

from .views import router


class Plugin(BasePlugin):
    name = "rpc_plugin"

    def setup_app(self, app):
        app.include_router(router)

    async def startup(self):
        pass

    async def shutdown(self):
        pass

    async def worker_setup(self):
        pass

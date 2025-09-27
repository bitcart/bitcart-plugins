import codecs
import importlib
import traceback
from typing import Any

from aiocsv import AsyncDictReader
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.security import SecurityScopes

from api import models, utils
from api.plugins import DIContainer, DIRoute, FromDI, get_plugin_logger
from api.types import AuthServiceProtocol

router = APIRouter(route_class=DIRoute)

logger = get_plugin_logger(__name__)


class AsyncTextReaderWrapper:
    def __init__(self, obj: Any, encoding: str, errors: str = "strict") -> None:
        self.obj = obj

        decoder_factory = codecs.getincrementaldecoder(encoding)
        self.decoder = decoder_factory(errors)

    async def read(self, size: int) -> str:
        raw_data = await self.obj.read(size)

        if not raw_data:
            return self.decoder.decode(b"", final=True)

        return self.decoder.decode(raw_data, final=False)


@router.post("/{table}")
async def batchimport(
    auth_service: FromDI[AuthServiceProtocol],
    container: FromDI[DIContainer],
    request: Request,
    table: str,
    file: UploadFile = File(...),
) -> Any:
    singular = table[:-1] if len(table) > 1 and table.endswith("s") else table
    model_name = singular.capitalize()
    if model_name not in models.all_tables:
        raise HTTPException(404, f"Table {table} not found")
    auth_token = await utils.authorization.auth_dependency.parse_token(request)
    user, _ = await auth_service.find_user_and_check_permissions(
        auth_token, SecurityScopes([f"{model_name.lower()}_management"])
    )
    plural_module = f"{singular}s"
    schema_module = importlib.import_module(f"api.schemas.{plural_module}")
    schema_cls = getattr(schema_module, f"Create{model_name}")
    service_module = importlib.import_module(f"api.services.crud.{plural_module}")
    service_cls = getattr(service_module, f"{model_name}Service")
    service = await container.get(service_cls)
    total = 0
    successful = 0
    async for row in AsyncDictReader(AsyncTextReaderWrapper(file, "utf-8-sig")):
        total += 1
        try:
            await service.create(schema_cls(**row), user)
            successful += 1
        except Exception:
            logger.error(f"Error importing row {row}:\n{traceback.format_exc()}")
    return {"total": total, "successful": successful}

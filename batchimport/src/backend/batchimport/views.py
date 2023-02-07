import codecs

from aiocsv import AsyncDictReader
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.security import SecurityScopes

from api import models, schemes, utils

router = APIRouter()


class AsyncTextReaderWrapper:
    def __init__(self, obj, encoding, errors="strict"):
        self.obj = obj

        decoder_factory = codecs.getincrementaldecoder(encoding)
        self.decoder = decoder_factory(errors)

    async def read(self, size):
        raw_data = await self.obj.read(size)

        if not raw_data:
            return self.decoder.decode(b"", final=True)

        return self.decoder.decode(raw_data, final=False)


@router.post("/batchimport/{table}")
async def batchimport(request: Request, table: str, file: UploadFile = File(...)):
    if len(table) > 1:
        table = table[:-1]
    table = table.capitalize()
    if table not in models.all_tables:
        raise Exception("Table not found")
    user = await utils.authorization.auth_dependency(
        request, SecurityScopes([f"{table.lower()}_management"])
    )
    model = models.all_tables[table]
    scheme = getattr(schemes, f"Create{table}")
    total = 0
    successful = 0
    async for row in AsyncDictReader(AsyncTextReaderWrapper(file, "utf-8")):
        total += 1
        try:
            await utils.database.create_object(model, scheme(**row), user)
            successful += 1
        except Exception:
            pass
    return {"total": total, "successful": successful}

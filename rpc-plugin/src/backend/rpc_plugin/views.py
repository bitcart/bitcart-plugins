import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Security

from api import models, utils
from api.constants import AuthScopes
from api.plugins import DIRoute, FromDI
from api.services.coins import CoinService

router = APIRouter(route_class=DIRoute)


def parse_params(params: Any) -> tuple[list[Any], dict[str, Any]]:
    args = params
    kwargs = {}
    if isinstance(params, list):
        if len(params) > 0 and isinstance(params[-1], dict):
            kwargs = params.pop()
    elif isinstance(params, dict):
        kwargs = params
        args = ()
    return args, kwargs


def parse_xpub(xpub: str | dict[str, Any] | None) -> tuple[str | None, str | None, dict[str, Any]]:
    if xpub is None or isinstance(xpub, str):
        return xpub, None, {}
    if isinstance(xpub, dict):
        return xpub.pop("xpub", None), xpub.pop("contract", None), xpub


@router.post("/{coin}/rpc")
async def coin_rpc(
    coin_service: FromDI[CoinService],
    coin: str,
    request: Request,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    try:
        await coin_service.get_coin(coin)
    except HTTPException:
        raise HTTPException(404, "Coin not found") from None
    try:
        data = await request.json()
    except json.decoder.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON body") from None
    if "method" not in data or "params" not in data:
        raise HTTPException(400, "Invalid request")
    args, kwargs = parse_params(data["params"])
    xpub, contract, extra_params = parse_xpub(kwargs.pop("xpub", None))
    coin_obj = await coin_service.get_coin(coin, {"xpub": xpub, "contract": contract, **extra_params})
    try:
        return {"result": await getattr(coin_obj.server, data["method"])(*args, **kwargs)}
    except Exception as e:
        exceptions = (await coin_obj.spec)["exceptions"]
        for code, exception in exceptions.items():
            if exception["exc_name"] == e.__class__.__name__:
                return {"error": {"code": int(code), "message": str(e)}}
        return {"error": {"code": -32600, "message": str(e)}}


@router.get("/{coin}/rpc/spec")
async def coin_spec(
    coin_service: FromDI[CoinService],
    coin: str,
    request: Request,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    try:
        coin_obj = await coin_service.get_coin(coin)
    except HTTPException:
        raise HTTPException(404, "Coin not found") from None
    return await coin_obj.spec

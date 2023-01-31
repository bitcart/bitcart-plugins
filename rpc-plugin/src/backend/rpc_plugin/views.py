from fastapi import APIRouter, HTTPException, Request, Security

from api import models, settings, utils

router = APIRouter()


def parse_params(params):
    args = params
    kwargs = {}
    if isinstance(params, list):
        if len(params) > 0 and isinstance(params[-1], dict):
            kwargs = params.pop()
    elif isinstance(params, dict):
        kwargs = params
        args = ()
    return args, kwargs


def parse_xpub(xpub):
    if xpub is None or isinstance(xpub, str):
        return xpub, None, {}
    if isinstance(xpub, dict):
        return xpub.pop("xpub", None), xpub.pop("contract", None), xpub


@router.post("/cryptos/{coin}/rpc")
async def coin_rpc(
    coin: str,
    request: Request,
    user: models.User = Security(
        utils.authorization.AuthDependency(), scopes=["server_management"]
    ),
):
    try:
        await settings.settings.get_coin(coin)
    except HTTPException:
        raise HTTPException(404, "Coin not found")
    data = await request.json()
    if "method" not in data or "params" not in data:
        raise HTTPException(400, "Invalid request")
    args, kwargs = parse_params(data["params"])
    xpub, contract, extra_params = parse_xpub(kwargs.pop("xpub", None))
    coin_obj = await settings.settings.get_coin(
        coin, {"xpub": xpub, "contract": contract, **extra_params}
    )
    try:
        return {
            "result": await getattr(coin_obj.server, data["method"])(*args, **kwargs)
        }
    except Exception as e:
        exceptions = (await coin_obj.spec)["exceptions"]
        for code, exception in exceptions.items():
            if exception["exc_name"] == e.__class__.__name__:
                return {"error": {"code": int(code), "message": str(e)}}
        return {"error": {"code": -32600, "message": str(e)}}


@router.get("/cryptos/{coin}/rpc/spec")
async def coin_spec(
    coin: str,
    request: Request,
    user: models.User = Security(
        utils.authorization.AuthDependency(), scopes=["server_management"]
    ),
):
    try:
        coin_obj = await settings.settings.get_coin(coin)
    except HTTPException:
        raise HTTPException(404, "Coin not found")
    return await coin_obj.spec

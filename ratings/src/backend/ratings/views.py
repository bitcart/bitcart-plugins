from decimal import Decimal
from typing import Any

from fastapi import APIRouter

from api.ext.moneyformat import truncate
from api.plugins import DIRoute, FromDI, update_metadata
from api.schemas.products import DisplayProduct
from api.services.crud.products import ProductService
from modules.bitcart.ratings.schemas import UpdateRating

router = APIRouter(route_class=DIRoute)


@router.post("/products/{model_id}/rate", response_model=DisplayProduct)
async def add_rating(product_service: FromDI[ProductService], model_id: str, data: UpdateRating) -> Any:
    obj = await product_service.get(model_id)
    rating = Decimal(obj.meta.get("rating", 0))
    rating_count = int(obj.meta.get("rating_count", 0))
    rating = truncate((rating * rating_count + data.rating) / (rating_count + 1), 2)
    rating_count += 1
    obj = update_metadata(obj, "rating", rating)
    return update_metadata(obj, "rating_count", rating_count)

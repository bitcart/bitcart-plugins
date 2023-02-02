from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, validator

from api import models, schemes, utils
from api.ext.moneyformat import truncate
from api.plugins import update_metadata

router = APIRouter()


class UpdateRating(BaseModel):
    rating: int

    @validator("rating", always=True)
    def set_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


@router.post("/products/{model_id}/rate", response_model=schemes.Product)
async def add_rating(model_id: str, data: UpdateRating):
    obj = await utils.database.get_object(models.Product, model_id)
    rating = Decimal(obj.metadata.get("rating", 0))
    rating_count = obj.metadata.get("rating_count", 0)
    rating = truncate((rating * rating_count + data.rating) / (rating_count + 1), 2)
    rating_count += 1
    obj = await update_metadata(models.Product, model_id, "rating", rating)
    obj = await update_metadata(models.Product, model_id, "rating_count", rating_count)
    return obj

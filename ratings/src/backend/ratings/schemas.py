from pydantic import Field, field_validator

from api.schemas.base import Schema


class UpdateRating(Schema):
    rating: int = Field(..., validate_default=True)

    @field_validator("rating")
    @classmethod
    def set_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

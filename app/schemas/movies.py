from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MovieBaseSchema(BaseModel):
    uuid: str | None = None
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: float | None = None
    description: str
    price: Decimal

    model_config = {
        "from_attributes": True
    }

    @field_validator("year")
    @classmethod
    def validate_year(cls, value):
        current_year = datetime.now().year
        if value > current_year + 1:
            raise ValueError(f"The year in 'year' cannot be greater than {current_year + 1}.")
        return value


class MovieDetailSchema(MovieBaseSchema):
    id: int
    genres: list[GenreSchema]
    stars: list[StarSchema]
    directors: list[DirectorSchema]
    certification: CertificationSchema

    model_config = {
        "from_attributes": True,
    }


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    genres: List[GenreSchema]
    directors: List[DirectorSchema]
    stars: List[StarSchema]

    model_config = {
        "from_attributes": True,
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
    }


class MovieCreateSchema(BaseModel):
    uuid: str | None = None
    name: str
    year: int
    time: int
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    meta_score: float | None = None
    gross: float | None = None
    description: str
    price: float = Field(default=Decimal("0.00"), ge=0)
    genres: list[str]
    stars: list[str]
    directors: list[str]
    certification: str

    model_config = {
        "from_attributes": True,
    }

    @field_validator("genres", "stars", "directors", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: list[str]) -> list[str]:
        return [item.title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: str | None = None
    year: int | None = None
    time: int | None = None
    imdb: float | None = Field(None, ge=0, le=10)
    votes: int | None = Field(None, ge=0)
    meta_score: float | None = None
    gross: float | None = None
    description: str | None = None
    price: Decimal | None = Field(None, ge=0)

    model_config = {"from_attributes": True}

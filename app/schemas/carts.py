from typing import List
from decimal import Decimal

from pydantic import BaseModel


class CartItemBaseSchema(BaseModel):
    id: int
    title: str
    price: Decimal
    genre: List[str]
    release_year: int


class CartResponseSchema(BaseModel):
    id: int
    items: List[CartItemBaseSchema]

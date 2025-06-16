from typing import List

from pydantic import BaseModel


class CartItemResponse(BaseModel):
    id: int
    title: str
    price: float
    genre: List[str]
    release_year: int


class CartResponse(BaseModel):
    id: int
    items: List[CartItemResponse]

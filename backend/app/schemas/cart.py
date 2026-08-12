from pydantic import BaseModel
from typing import Optional


class CartLine(BaseModel):
    item_id: int
    name: str
    unit: str
    unit_price: float
    quantity: int
    subtotal: float
    image_url: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    # Set only for products sourced from outside our catalog.
    seller: Optional[str] = None
    product_url: Optional[str] = None


class CartOut(BaseModel):
    session_id: str
    items: list[CartLine]
    subtotal: float = 0.0   # goods only, before tax
    tax: float = 0.0
    total: float            # subtotal + tax — what the customer pays
    count: int


class AddItemRequest(BaseModel):
    session_id: Optional[str] = None
    item_id: int
    quantity: int = 1


class SetQuantityRequest(BaseModel):
    quantity: int

from datetime import date
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional


class CustomerIn(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class OrderItemIn(BaseModel):
    product_id: int
    quantity: float


class PlaceOrderRequest(BaseModel):
    customer: CustomerIn
    # When session_id is given, the order is built from the server-side cart and
    # `items` may be omitted. Explicit items are still honoured for back-compat.
    session_id: Optional[str] = None
    items: Optional[list[OrderItemIn]] = None
    notes: Optional[str] = None
    # Delivery slot chosen at checkout. The date is next-day-or-later (enforced in
    # the UI); the time is stored as its label ("5:00 PM EST") so the timezone is
    # never ambiguous downstream.
    delivery_date: Optional[date] = None
    delivery_time: Optional[str] = None
    # Free-text instructions for the driver ("gate code 4412"). Optional.
    delivery_notes: Optional[str] = None
    # Sent by the browser so a double-clicked Confirm, a retry or a replayed
    # request returns the original order instead of placing a second one.
    idempotency_key: Optional[str] = None
    # How they are paying. "cod" takes no money now and confirms the order
    # immediately; the others put it in "pending" until the provider's webhook
    # says the money arrived. Defaults to cod so an older client that does not
    # send the field cannot accidentally create an order nobody ever pays for
    # AND nobody knows to collect on: cash is at least visible to the shop.
    payment_method: Literal["cod", "stripe", "paypal"] = "cod"


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: float
    unit: str
    unit_price: float
    subtotal: float

    class Config:
        from_attributes = True


class PlaceOrderResponse(BaseModel):
    order_id: int
    customer_id: int
    total_amount: float          # what the customer pays (subtotal + tax)
    subtotal: float = 0.0        # goods only, before tax
    tax: float = 0.0
    status: str
    items: list[OrderItemOut]
    delivery_date: Optional[date] = None
    delivery_time: Optional[str] = None
    delivery_notes: Optional[str] = None
    # So the confirmation screen can say "have $X ready for the driver" rather
    # than "Paid" for a cash order.
    payment_method: Optional[str] = None

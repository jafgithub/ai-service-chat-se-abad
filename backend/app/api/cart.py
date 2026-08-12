import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.cart import CartOut, AddItemRequest, SetQuantityRequest
from app.services import cart_service

logger = logging.getLogger("cart")

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartOut)
def get_cart(session_id: str = Query(...), db: Session = Depends(get_db)):
    session = cart_service.get_or_create_session(db, session_id)
    payload = cart_service.serialize_cart(db, session)
    db.commit()
    return payload


@router.post("/items", response_model=CartOut)
def add_to_cart(payload: AddItemRequest, db: Session = Depends(get_db)):
    session = cart_service.get_or_create_session(db, payload.session_id)
    try:
        cart_service.add_item(db, session, payload.item_id, payload.quantity)
    except cart_service.CartError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = cart_service.serialize_cart(db, session)
    db.commit()
    return result


@router.patch("/items/{item_id}", response_model=CartOut)
def update_cart_item(item_id: int, payload: SetQuantityRequest, session_id: str = Query(...), db: Session = Depends(get_db)):
    session = cart_service.get_or_create_session(db, session_id)
    try:
        cart_service.set_quantity(db, session, item_id, payload.quantity)
    except cart_service.CartError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = cart_service.serialize_cart(db, session)
    db.commit()
    return result


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_cart_item(item_id: int, session_id: str = Query(...), db: Session = Depends(get_db)):
    session = cart_service.get_or_create_session(db, session_id)
    cart_service.remove_item(db, session, item_id)
    result = cart_service.serialize_cart(db, session)
    db.commit()
    return result


@router.delete("", response_model=CartOut)
def clear_cart(session_id: str = Query(...), db: Session = Depends(get_db)):
    session = cart_service.get_or_create_session(db, session_id)
    cart_service.clear(db, session)
    result = cart_service.serialize_cart(db, session)
    db.commit()
    return result

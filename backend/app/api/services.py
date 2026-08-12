from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.models.service import Service
from app.services import rag
from app.services.media import serialized_image

router = APIRouter(prefix="/services", tags=["services"])


class ProductOut(BaseModel):
    id: int
    name: Optional[str]
    category: str
    description: Optional[str]
    unit: str
    price_per_unit: float
    stock: float
    image_url: Optional[str]
    duration_minutes: Optional[int] = None
    emergency: bool = False
    is_active: bool

    class Config:
        from_attributes = True


def _enrich_and_serialize(products: list[Service], db: Session) -> list[dict]:
    rag._enrich_products(products, db)
    result = []
    for p in products:
        result.append({
            "id":             p.id,
            "name":           p.name,
            "category":       getattr(p, "_category_name", None) or str(p.category_id or ""),
            "description":    p.description or "",
            "unit":           "unit",
            "price_per_unit": float(p.price),
            "stock":          float(p.stock or 0),
            "image_url":      serialized_image(p),
            # The guide figures. A provider registering picks from this list and
            # sets their own price and duration against each one, so they need
            # to see what the service usually is before they differ from it.
            "duration_minutes": p.duration_minutes,
            "emergency":      bool(p.emergency),
            "is_active":      bool(p.status),
        })
    return result


@router.get("")
def list_products(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Service).filter(Service.status == True)
    products = q.order_by(Service.name).all()

    result = _enrich_and_serialize(products, db)

    if category:
        result = [p for p in result if category.lower() in p["category"].lower()]

    return result


@router.post("/index", summary="Embed all unindexed products")
def index_products(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    def _run():
        count = rag.index_all_products(db)
        print(f"[rag] Indexed {count} products.")

    background_tasks.add_task(_run)
    return {"message": "Indexing started in background"}

"""
Service image resolver.

One stable URL per product — ``GET /api/v1/media/{item_id}`` — that 302-redirects
to wherever the real photo is hosted. Putting the resolution behind a single
endpoint means the frontend (and the browser cache) never has to change when the
upstream host or the per-store folder layout does; all the mapping lives in
``services.media``. Items with no resolvable photo (no filename, legacy JSON-id
format, or image hosting not yet configured) get a neutral placeholder instead of
a broken image or a 500.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.service import Service
from app.services.media import resolve_media_url

router = APIRouter(prefix="/media", tags=["media"])

# Neutral light-grey square served when a product has no resolvable photo, so an
# <img> that pointed here never shows a broken-image icon.
_PLACEHOLDER_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
    b'<rect width="100%" height="100%" fill="#f1f1f1"/></svg>'
)


@router.get("/{item_id}")
def product_image(item_id: int, db: Session = Depends(get_db)):
    product = db.query(Service).filter(Service.id == item_id).first()
    url = resolve_media_url(product) if product else None
    if url:
        return RedirectResponse(url, status_code=302)
    return Response(content=_PLACEHOLDER_SVG, media_type="image/svg+xml")

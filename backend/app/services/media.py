"""
Service image URL helper.

The catalog stores the image *filename* (e.g. "20260726135225217509_4592.jpg").
To display a photo the browser needs a full URL, so we call the client's image API
(`IMAGE_BASE_URL`, from config/.env) as `?folder=jjimages&image=<filename>`.

If the base isn't set, the value is already a full URL, or the field holds the
legacy JSON gallery format (some bulk-imported items store `[{"id":..}]` instead
of a filename — those ids don't resolve to a file yet), we return None and the
frontend shows a category-icon fallback.
"""

from urllib.parse import quote

from app.core.config import settings

# Fixed folder param the client's image API expects for every product.
_IMAGE_API_FOLDER = "jjimages"


def image_url(filename: str | None, store_id: int | None = None) -> str | None:
    if not filename:
        return None
    val = filename.strip()
    if val.startswith("http://") or val.startswith("https://"):
        return val
    # Legacy JSON gallery format (bulk store_id=0 items): "[{\"id\":..}]" / "{..}".
    # These reference image records by id and don't map to a filename → no URL yet.
    if val.startswith("[") or val.startswith("{"):
        return None
    base = settings.IMAGE_BASE_URL.strip()
    if not base:
        return None  # not configured → frontend falls back to a category icon
    return f"{base.rstrip('/')}?folder={_IMAGE_API_FOLDER}&image={quote(val)}"


def resolve_media_url(product) -> str | None:
    """Absolute URL of a product's real photo, or None if it can't be resolved.

    Thin adapter over image_url() that takes a Service so the media endpoint and
    the API serializers share one resolution path.
    """
    return image_url(getattr(product, "image", None), getattr(product, "store_id", None))


def serialized_image_for(item_id, filename: str | None, store_id: int | None) -> str | None:
    """The value the API advertises as a product's ``image_url``.

    Resolvable photos are routed through our stable media endpoint
    (``<PUBLIC_BASE_URL>/api/v1/media/{id}``) so the advertised URL never changes
    when the upstream host or per-store folder layout does. With no PUBLIC_BASE_URL
    configured we serialize the resolved photo URL directly. Products with no
    resolvable photo return None → the frontend keeps its category-icon fallback
    (so we never spam placeholders while image hosting is being sorted out).

    Takes plain fields rather than a Service so the in-memory catalog index, which
    holds no ORM objects, resolves images through this exact same path.
    """
    direct = image_url(filename, store_id)
    if direct is None:
        return None
    base = settings.PUBLIC_BASE_URL.strip()
    if not base:
        return direct
    return f"{base.rstrip('/')}/api/v1/media/{item_id}"


def serialized_image(product) -> str | None:
    """``serialized_image_for`` for a Service instance."""
    return serialized_image_for(
        product.id,
        getattr(product, "image", None),
        getattr(product, "store_id", None),
    )

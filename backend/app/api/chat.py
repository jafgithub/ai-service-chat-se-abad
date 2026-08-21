import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ServiceResult
from app.services import cart_service, conversation

logger = logging.getLogger("chat")

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    t_start = time.perf_counter()
    logger.info(f"[CHAT] session={payload.session_id} message=\"{payload.message}\"")

    session = cart_service.get_or_create_session(db, payload.session_id, payload.latitude, payload.longitude)

    try:
        result = conversation.process(payload.message, session, db,
                                      category_filter=payload.category_filter,
                                      community=payload.community)
        db.commit()
    except Exception:
        # Keep the chat usable: log the traceback, roll back, and reply gracefully
        # (a valid ChatResponse) instead of surfacing a raw 500 to the shopper.
        logger.exception("[CHAT] pipeline failed")
        db.rollback()
        try:
            cart = cart_service.serialize_cart(db, session)
        except Exception:
            cart = {"session_id": session.id, "items": [], "total": 0.0, "count": 0}
        msg = "Sorry, something went wrong on our end. Please try again."
        return ChatResponse(
            session_id=session.id, reply=msg, speech=msg,
            services=[], cart=cart, action=None,
        )

    logger.info(f"[CHAT] done in {(time.perf_counter() - t_start) * 1000:.0f}ms")

    return ChatResponse(
        session_id=session.id,
        reply=result["reply"],
        speech=result["speech"],
        services=[ServiceResult(**p) for p in result["services"]],
        total_services=result.get("total_services", 0),
        cart=result["cart"],
        action=result["action"],
        intent=result.get("intent"),
        sources=result.get("sources", []),
    )

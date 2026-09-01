import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.voice import VoiceResponse
from app.schemas.chat import ServiceResult
from app.services import cart_service, conversation, voice_service

logger = logging.getLogger("voice")

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("", response_model=VoiceResponse)
async def voice_endpoint(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    category_filter: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    db: Session = Depends(get_db),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload.")

    # 1) Speech → text
    try:
        transcript = voice_service.transcribe(audio_bytes, file.filename or "audio.webm")
    except voice_service.VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    session = cart_service.get_or_create_session(db, session_id, latitude, longitude)

    # No intelligible speech: don't run the pipeline, just prompt the user again.
    if not transcript:
        reply = "Sorry, I didn't catch that. Could you say it again?"
        cart = cart_service.serialize_cart(db, session)
        db.commit()
        return VoiceResponse(
            session_id=session.id, transcript="", reply=reply, speech=reply,
            audio=voice_service.synthesize(reply), services=[], cart=cart, action=None, intent=None,
        )

    # 2) Same pipeline as text chat
    result = conversation.process(transcript, session, db, category_filter=category_filter)
    db.commit()

    # 3) Text → speech (best-effort) — speak the short version, not the whole list
    audio = voice_service.synthesize(result["speech"])

    return VoiceResponse(
        session_id=session.id,
        transcript=transcript,
        reply=result["reply"],
        speech=result["speech"],
        audio=audio,
        services=[ServiceResult(**p) for p in result["services"]],
        total_services=result.get("total_services", 0),
        cart=result["cart"],
        action=result["action"],
        intent=result.get("intent"),
    )

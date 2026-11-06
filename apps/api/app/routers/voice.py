import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies import get_current_user
from app.logger import logger
from app.models.api import TranscribeResponse
from app.models.db import UserProfile
from app.voice.transcriber import ALLOWED_AUDIO_MIMES, Transcriber, get_transcriber

router = APIRouter(prefix="/v1/voice", tags=["voice"])


@router.post("/transcribe", response_model=TranscribeResponse, status_code=status.HTTP_200_OK)
async def transcribe_audio(
    audio: UploadFile = File(...),
    user: UserProfile = Depends(get_current_user),
    transcriber: Transcriber = Depends(get_transcriber),
):
    """
    Transcribes uploaded voice audio to text.
    1. Validates audio MIME and size.
    2. Calls pluggable Transcriber.
    3. Returns {"text": transcribed_text}.
    422 on invalid MIME or untranscribable audio.
    """
    content_type = audio.content_type or ""
    filename = audio.filename or "recording.mp3"
    ext = os.path.splitext(filename)[1].lower()

    # Validate mime
    is_valid_mime = (
        content_type in ALLOWED_AUDIO_MIMES
        or ext in (".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".mp4")
    )
    if not is_valid_mime:
        logger.warning(f"Rejected unsupported audio MIME: {content_type} ({filename})")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported audio type '{content_type}'. Supported: {list(ALLOWED_AUDIO_MIMES.keys())}",
        )

    audio_bytes = await audio.read()

    # Reject empty audio
    if not audio_bytes or len(audio_bytes) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty or unreadable audio payload.",
        )

    # Size check (25MB Whisper limit)
    if len(audio_bytes) > settings.TRANSCRIPTION_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if hasattr(status, "HTTP_413_REQUEST_ENTITY_TOO_LARGE") else 413,
            detail=f"Audio file size exceeds limit of {settings.TRANSCRIPTION_MAX_BYTES} bytes.",
        )

    try:
        text = transcriber.transcribe(
            audio_bytes=audio_bytes,
            mime_type=content_type,
            filename=filename,
        )
        if not text or not text.strip():
            raise ValueError("No speech detected or empty transcription result")
        return TranscribeResponse(text=text.strip())

    except Exception as exc:
        logger.error(f"Audio transcription failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transcription failed: {str(exc)}",
        )

from abc import ABC, abstractmethod
import io
import os
from typing import Optional
from openai import OpenAI

from app.config import settings
from app.logger import logger

ALLOWED_AUDIO_MIMES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".mp4",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
}


class Transcriber(ABC):
    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        filename: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        """Transcribe audio bytes to text. Raises Exception on invalid audio or failure."""
        pass


class WhisperTranscriber(Transcriber):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.TRANSCRIPTION_API_KEY or os.environ.get("OPENAI_API_KEY") or "mock-key"
        self.base_url = base_url or settings.TRANSCRIPTION_BASE_URL
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        filename: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        if not audio_bytes or len(audio_bytes) == 0:
            raise ValueError("Empty audio payload")

        ext = ALLOWED_AUDIO_MIMES.get(mime_type, ".mp3")
        file_name = filename or f"audio{ext}"

        file_tuple = (file_name, audio_bytes, mime_type)
        create_kwargs = {
            "model": "whisper-1",
            "file": file_tuple,
            "prompt": "English, Hindi, Marathi bilingual or trilingual recruiting conversation",
        }
        if language:
            create_kwargs["language"] = language

        try:
            resp = self.client.audio.transcriptions.create(**create_kwargs)
            return resp.text if hasattr(resp, "text") else str(resp)
        except Exception as exc:
            logger.error(f"Whisper transcription error: {exc}")
            raise exc


_default_transcriber: Optional[Transcriber] = None


def get_transcriber(provider: Optional[str] = None) -> Transcriber:
    """Factory returning the configured Transcriber instance."""
    global _default_transcriber
    prov = (provider or settings.TRANSCRIPTION_PROVIDER or "whisper").lower()

    if _default_transcriber is None:
        if prov == "whisper":
            _default_transcriber = WhisperTranscriber()
        else:
            _default_transcriber = WhisperTranscriber()

    return _default_transcriber


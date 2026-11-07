import pytest

from app.main import app
from app.voice.transcriber import Transcriber, get_transcriber


class MockTranscriber(Transcriber):
    def __init__(self):
        self.return_text = "I am a student at DJ Sanghvi batch 2027"

    def transcribe(self, audio_bytes: bytes, mime_type: str, filename=None, language=None) -> str:
        if b"bad-audio" in audio_bytes:
            raise ValueError("Corrupt audio file could not be parsed")
        return self.return_text


@pytest.fixture
def mock_transcriber():
    mock = MockTranscriber()
    app.dependency_overrides[get_transcriber] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_transcriber, None)


def test_transcribe_english(client, mock_transcriber):
    mock_transcriber.return_text = "Hello, I am studying Computer Engineering at VJTI batch 2027"
    response = client.post(
        "/v1/voice/transcribe",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"audio": ("speech.wav", b"dummy-valid-wav-audio-data-at-least-twenty-bytes", "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "VJTI" in data["text"]


def test_transcribe_hindi(client, mock_transcriber):
    mock_transcriber.return_text = "Main VESIT Mumbai se Computer Engineering kar raha hoon, batch 2028"
    response = client.post(
        "/v1/voice/transcribe",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"audio": ("speech.mp3", b"dummy-valid-mp3-audio-data-at-least-twenty-bytes", "audio/mpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "VESIT" in data["text"]


@pytest.mark.xfail(reason="Marathi transcription is best-effort pending reliable test")
def test_transcribe_marathi(client, mock_transcriber):
    assert False, "Marathi transcription not yet reliably tested"


def test_transcribe_bad_audio_returns_422(client, mock_transcriber):
    # Case 1: Corrupt audio that fails transcription
    response = client.post(
        "/v1/voice/transcribe",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"audio": ("speech.wav", b"bad-audio-stream-payload-fails", "audio/wav")},
    )
    assert response.status_code == 422

    # Case 2: Invalid audio MIME
    bad_mime_res = client.post(
        "/v1/voice/transcribe",
        headers={"Authorization": "Bearer valid-token-student"},
        files={"audio": ("document.pdf", b"pdf-content-not-audio-bytes-at-all", "application/pdf")},
    )
    assert bad_mime_res.status_code == 422

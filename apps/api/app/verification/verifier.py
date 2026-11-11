from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class VerificationResult:
    verified_flag: bool
    document_type: str  # 'aadhaar' | 'pan' | 'other'
    masked_id_tail: Optional[str]  # 'XXXX-XXXX-1234' or last4 of PAN; null if not applicable
    verification_note: str


class DocumentVerifier(ABC):
    """Provider-neutral interface for document verification.

    Implementations MUST NOT read document file bytes from Storage.
    Implementations MUST NOT send document content to any LLM, OCR or external service.
    """

    @abstractmethod
    def verify(self, document_id: str, mime_type: str) -> VerificationResult: ...


class MockVerifier(DocumentVerifier):
    """Day 5 implementation. Sets verified_flag=True without reading the file.

    document_type is derived from MIME only. masked_id_tail is always None
    (masking from chat-stated values is handled separately by the agent).
    """

    def verify(self, document_id: str, mime_type: str) -> VerificationResult:
        doc_type = "other"
        if "pdf" in (mime_type or "").lower():
            doc_type = "other"  # MIME only; no content inspection
        return VerificationResult(
            verified_flag=True,
            document_type=doc_type,
            masked_id_tail=None,
            verification_note="Demo verification (mocked)",
        )


class DigiLockerVerifier(DocumentVerifier):
    """Future: real Aadhaar/PAN verification via DigiLocker or API Setu.

    Raises NotImplementedError — no network calls, no new dependencies.
    Requires UIDAI AUA/KUA certification and partner registration with
    API Setu (https://api.setu.co) or DigiLocker sandbox credentials
    before this stub can be implemented.
    """

    def verify(self, document_id: str, mime_type: str) -> VerificationResult:
        raise NotImplementedError("DigiLockerVerifier requires partner registration. See README#future-work.")


def get_verifier() -> DocumentVerifier:
    """Returns the configured verifier. Defaults to MockVerifier."""
    return MockVerifier()

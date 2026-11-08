from typing import List, Optional

from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import GeminiLLMProvider, LLMProvider, get_llm_provider
from app.logger import logger
from app.search.web import WEB_CONTENT_PROMPT_RULE


class CandidateContact(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    college: Optional[str] = None
    role_type: Optional[str] = "other"
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    contacts: List[CandidateContact] = Field(default_factory=list)


EXTRACTION_SYSTEM_INSTRUCTION = f"""You are a professional contact information extractor.
Extract public professional facts about individuals from the provided web content.

{WEB_CONTENT_PROMPT_RULE}

For each individual found:
- name: Full name (REQUIRED. If no clear name exists, do NOT include the entry).
- title: Current professional title or role (e.g. Lead Campus Recruiter, Training & Placement Officer).
- company: Employer / organization name (if applicable).
- college: Academic institution name (if applicable).
- role_type: one of 'campus_recruiter', 'placement_officer', 'hr', or 'other'.
- linkedin_url: Public LinkedIn profile URL (if present).
- email: Published business email (if present).
- Any unstated or ambiguous field must be null.
- NEVER extract or store phone numbers.
- Return a JSON object with key "contacts" containing the array of contacts.
"""


def extract_contacts_from_text(
    text: str,
    source_url: Optional[str] = None,
    gemini_client: Optional[genai.Client] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> List[CandidateContact]:
    """
    Extracts CandidateContact records from web text using Pydantic validation via LLMProvider.
    Drops candidates with no name. Retries once on schema failure.
    """
    if not text or not text.strip():
        return []

    # Wrap untrusted text securely inside <web_content>
    wrapped_content = f"<web_content>\n{text[:12000]}\n</web_content>"

    if llm_provider:
        provider = llm_provider
    elif gemini_client:
        provider = GeminiLLMProvider(client=gemini_client)
    else:
        provider = get_llm_provider()

    try:
        extraction_result: ExtractionResult = provider.generate_structured(
            prompt=wrapped_content,
            response_model=ExtractionResult,
            system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
            model=settings.LLM_FAST_MODEL,
        )

        valid_contacts: List[CandidateContact] = []
        for contact in extraction_result.contacts:
            # Drop nameless candidates (Open decision 5 & spec requirement)
            if not contact.name or not contact.name.strip():
                continue
            if source_url and not contact.source_url:
                contact.source_url = source_url
            valid_contacts.append(contact)

        return valid_contacts

    except Exception as exc:
        logger.warning(f"Error extracting contacts with LLM provider: {exc}")
        return []

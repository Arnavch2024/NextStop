import json
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
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
) -> List[CandidateContact]:
    """
    Extracts CandidateContact records from web text using Pydantic validation.
    Drops candidates with no name. Retries once on schema failure.
    """
    if not text or not text.strip():
        return []

    # Wrap untrusted text securely inside <web_content>
    wrapped_content = f"<web_content>\n{text[:12000]}\n</web_content>"

    client = gemini_client
    if client is None:
        try:
            client = genai.Client(api_key=settings.effective_gemini_api_key)
        except Exception as e:
            logger.warning(f"Could not initialize Gemini client for contact extraction: {e}")
            return []

    # Attempt extraction with 1 retry on schema/parsing failure
    for attempt in (1, 2):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=wrapped_content,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=ExtractionResult,
                ),
            )

            response_text = response.text or "{}"
            data = json.loads(response_text)
            contacts_list = data.get("contacts", [])

            valid_contacts: List[CandidateContact] = []
            for item in contacts_list:
                try:
                    contact = CandidateContact(**item)
                    # Drop nameless candidates (Open decision 5 & spec requirement)
                    if not contact.name or not contact.name.strip():
                        continue
                    if source_url and not contact.source_url:
                        contact.source_url = source_url
                    valid_contacts.append(contact)
                except ValidationError as ve:
                    logger.debug(f"CandidateContact validation skipped item: {ve}")

            return valid_contacts

        except Exception as exc:
            if attempt == 1:
                logger.warning(f"Contact extraction attempt 1 failed ({exc}). Retrying...")
            else:
                logger.error(f"Contact extraction failed after retry: {exc}")

    return []

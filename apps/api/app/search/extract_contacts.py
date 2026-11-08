import re
from typing import List, Optional, Tuple

from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import GeminiLLMProvider, LLMProvider, get_llm_provider
from app.logger import logger
from app.search.web import WEB_CONTENT_PROMPT_RULE

RECRUITER_PATTERN = re.compile(
    r"\b("
    r"recruit(?:er|ing|ment)?"
    r"|talent\s+(?:acquisition|attraction|partner|lead|team|operations|manager)"
    r"|campus\s+(?:hiring|recruit(?:er|ing|ment)?|lead|relations|placement)"
    r"|university\s+(?:hiring|recruit(?:er|ing|ment)?|lead|relations)"
    r"|human\s+resources"
    r"|hr(?:bp|\s+manager|\s+lead|\s+specialist|\s+associate|\s+officer)?"
    r"|placement\s+officer"
    r"|head\s+of\s+talent"
    r"|people\s+(&|and)\s+talent"
    r"|tpo"
    r")\b",
    re.IGNORECASE,
)

GENERIC_COMPANY_WORDS = {
    "india",
    "pvt",
    "ltd",
    "private",
    "limited",
    "company",
    "technologies",
    "services",
    "corporation",
    "inc",
}


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
    matched_rule: Optional[str] = None


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


def split_into_blocks(text: str) -> List[str]:
    """Splits text into sentences or discrete result blocks."""
    raw = re.split(r"(?<=[.!?\n|•;\t])\s+|\n+", text)
    return [b.strip() for b in raw if b.strip()]


def validate_recruiter_candidate(
    candidate: CandidateContact,
    text: str,
    target_company: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Tightens contact extraction precision:
    (a) The person's name and the target company appear in the same sentence or result block.
    (b) The title or surrounding text mentions recruiting, talent acquisition, campus or university hiring, or HR.
    Returns (True, matched_sentence) or (False, None).
    """
    if not candidate.name or not candidate.name.strip():
        return False, None

    name_clean = candidate.name.strip()
    name_lower = name_clean.lower()
    name_parts = [p.lower() for p in name_clean.split() if len(p) > 1]

    blocks = split_into_blocks(text)

    # Resolve company tokens to match
    comp_target = target_company or candidate.company
    comp_tokens = []
    if comp_target:
        comp_lower = comp_target.strip().lower()
        comp_tokens = [
            t for t in re.findall(r"\b[a-zA-Z0-9]+\b", comp_lower) if len(t) > 2 and t not in GENERIC_COMPANY_WORDS
        ]
        if not comp_tokens:
            comp_tokens = [comp_lower]

    matched_sentence: Optional[str] = None

    # Condition (a): Check if name and company appear in the same sentence/block
    for block in blocks:
        block_lower = block.lower()

        # Check name presence
        name_in_block = name_lower in block_lower or (
            len(name_parts) >= 2 and name_parts[0] in block_lower and name_parts[-1] in block_lower
        )
        if not name_in_block:
            continue

        # If target company is specified, company must appear in the same block
        if comp_tokens:
            comp_in_block = any(tok in block_lower for tok in comp_tokens)
            if not comp_in_block:
                continue

        matched_sentence = block
        break

    if not matched_sentence:
        return False, None

    # Condition (b): Title or surrounding text must mention recruiting, talent acquisition, campus/university hiring, or HR
    title_matches = bool(candidate.title and RECRUITER_PATTERN.search(candidate.title))
    block_matches = bool(RECRUITER_PATTERN.search(matched_sentence))

    if not (title_matches or block_matches):
        return False, None

    return True, matched_sentence


def extract_contacts_from_text(
    text: str,
    source_url: Optional[str] = None,
    gemini_client: Optional[genai.Client] = None,
    llm_provider: Optional[LLMProvider] = None,
    target_company: Optional[str] = None,
) -> List[CandidateContact]:
    """
    Extracts CandidateContact records from web text using Pydantic validation via LLMProvider.
    Enforces precision:
    - Drops candidates with no name.
    - Requires name and company in the same sentence/block.
    - Requires title or block to mention recruiting / HR / talent acquisition.
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
            if not contact.name or not contact.name.strip():
                continue

            # Validate recruiter precision rules (a) and (b)
            is_valid, matched_rule = validate_recruiter_candidate(
                candidate=contact,
                text=text,
                target_company=target_company,
            )
            if not is_valid:
                logger.info(
                    f"Dropping candidate '{contact.name}' ({contact.title}) - failed precision rules for company '{target_company}'."
                )
                continue

            contact.matched_rule = matched_rule
            if source_url and not contact.source_url:
                contact.source_url = source_url
            valid_contacts.append(contact)

        return valid_contacts

    except Exception as exc:
        logger.warning(f"Error extracting contacts with LLM provider: {exc}")
        return []

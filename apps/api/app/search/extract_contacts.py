import hashlib
import re
from typing import Any, Dict, List, Optional

from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import GeminiLLMProvider, LLMProvider, get_llm_provider
from app.logger import logger
from app.search.cache import get_cached_extraction, write_cached_extraction
from app.search.providers.extract import (
    WEB_CONTENT_PROMPT_RULE,
    compute_staleness,
    is_data_broker,
    is_name_only_empty_snippet,
    parse_title_hint,
)

RECRUITER_PATTERN = re.compile(
    r"\b("
    r"recruit(?:er|ing|ment)?"
    r"|talent\s+(?:acquisition|attraction|partner|lead|team|operations|manager)"
    r"|campus\s+(?:hiring|recruit(?:er|ing|ment)?|lead|relations|placement)"
    r"|university\s+(?:hiring|recruit(?:er|ing|ment)?|lead|relations)"
    r"|early\s+careers?"
    r"|internships?"
    r"|candidate\s+engagement"
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
    location: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    matched_rule: Optional[str] = None
    fetch_status: Optional[str] = "not_fetched"
    published_date: Optional[str] = None
    stale: Optional[bool] = None
    verified: bool = False


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
- location: Explicit city, state, or country mentioned in the text for this person (e.g. 'Mumbai', 'Bengaluru'). If the source text does not explicitly state a location for this person, location MUST be null. NEVER infer or default to any city.
- linkedin_url: Public LinkedIn profile URL (if present).
- email: Published business email (if present).
- source_url: The exact URL from the Result where this person was mentioned.
- Any unstated or ambiguous field must be null.
- NEVER extract or store phone numbers.
- Return a JSON object with key "contacts" containing the array of contacts.
"""


class ValidationResult:
    """Carries precision validation result, compatible with (is_valid, matched_rule) unpacking."""

    def __init__(
        self,
        is_valid: bool,
        matched_rule: Optional[str] = None,
        failed_rule: Optional[str] = None,
        snippet: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.matched_rule = matched_rule
        self.failed_rule = failed_rule
        self.snippet = snippet

    def __iter__(self):
        return iter((self.is_valid, self.matched_rule))


def validate_full_name(name: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Validates candidate person name:
    - Must not be empty.
    - Must have at least 2 word tokens (first and last name).
    - Surname cannot be a bare initial (e.g. 'F.', 'P.', 'D', 'T.').
    - Surname cannot be 1 or 2 uppercase letters (e.g. 'MG', 'VK', 'F', 'P').
    """
    if not name or not name.strip():
        return False, "Nameless candidate (no clear person name)"

    clean = name.strip()
    tokens = [t.strip(",.()[]") for t in clean.split() if t.strip(",.()[]")]

    if len(tokens) < 2:
        return False, "Rule failed: Name has only a single token (must have at least first and last name)"

    surname = tokens[-1]

    # Bare single-letter initial (e.g. "F.", "P.", "D")
    if len(surname) == 1 or re.match(r"^[A-Za-z]\.?$", surname):
        return False, "Rule failed: Surname is a bare initial (must have full surname)"

    # One or two uppercase letters (e.g. "MG", "VK", "AB")
    if re.match(r"^[A-Z]{1,2}$", surname):
        return False, "Rule failed: Surname is 1-2 uppercase letters or initials (must have full surname)"

    return True, None


def split_into_blocks(text: str) -> List[str]:
    """
    Splits text into discrete evaluation blocks:
    - Treats a search result's title plus snippet as one block, including pipe- or dash-delimited titles ('Name | Title | Company').
    - For multi-sentence text/articles, splits on sentence boundaries (. ! ?) or paragraph breaks.
    - Never splits on pipes '|', dashes '-', or common abbreviations (e.g. 'Co.', 'Inc.', 'Ltd.').
    """
    if not text or not text.strip():
        return []

    clean = text.strip()

    # If text is formatted with Result [N] or ---
    if "Result [" in clean or "\n---\n" in clean:
        parts = re.split(r"(?:^|\n)---\n|(?:^|\n)(?=Result \[\d+\]:)", clean)
        blocks = [p.strip() for p in parts if p.strip()]
        if len(blocks) > 1:
            return blocks

    # Protect abbreviation periods so they don't break companies like 'JPMorgan Chase & Co.' or titles
    t = clean
    for abbr in ("Co.", "Inc.", "Ltd.", "Pvt.", "Corp.", "Dr.", "Mr.", "Ms.", "vs."):
        t = t.replace(abbr, abbr.replace(".", "@DOT@"))

    # Split on sentence terminators (. ! ?) followed by whitespace or paragraph breaks
    raw_blocks = re.split(r"[.!?]\s+|\n{2,}", t)
    blocks = [b.replace("@DOT@", ".").strip() for b in raw_blocks if b.strip()]

    return blocks if blocks else [clean]


def validate_recruiter_candidate(
    candidate: CandidateContact,
    text: str,
    target_company: Optional[str] = None,
) -> ValidationResult:
    """
    Tightens contact extraction precision:
    (a) The person's name and the target company appear in the same sentence or result block.
    (b) The title or surrounding text mentions recruiting, talent acquisition, campus or university hiring, or HR.
    """
    is_name_ok, name_error = validate_full_name(candidate.name)
    if not is_name_ok:
        return ValidationResult(
            is_valid=False,
            failed_rule=name_error or "Invalid person name format",
            snippet=None,
        )

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

    name_found_in_any_block = False
    best_snippet_for_failure = None

    # Condition (a): Check if name and company appear in the same sentence/block
    for block in blocks:
        block_lower = block.lower()

        # Check name presence
        name_in_block = name_lower in block_lower or (
            len(name_parts) >= 2 and name_parts[0] in block_lower and name_parts[-1] in block_lower
        )
        if not name_in_block:
            continue

        name_found_in_any_block = True
        best_snippet_for_failure = block

        # Check if company appears in the same block
        if comp_tokens:
            comp_in_block = any(tok in block_lower for tok in comp_tokens)
            if not comp_in_block:
                continue

        # Condition (a) passed! Now check Condition (b):
        title_matches = bool(candidate.title and RECRUITER_PATTERN.search(candidate.title))
        block_matches = bool(RECRUITER_PATTERN.search(block))

        if not (title_matches or block_matches):
            return ValidationResult(
                is_valid=False,
                failed_rule="Rule (b) failed: Title and block do not mention recruiting, talent acquisition, campus hiring, or HR",
                snippet=block,
            )

        return ValidationResult(
            is_valid=True,
            matched_rule=block,
            snippet=block,
        )

    if not name_found_in_any_block:
        return ValidationResult(
            is_valid=False,
            failed_rule="Rule (a) failed: Person name not found in evaluated text",
            snippet=blocks[0] if blocks else text[:200],
        )

    return ValidationResult(
        is_valid=False,
        failed_rule=f"Rule (a) failed: Name found but target company '{comp_target}' not found in the same sentence/result block",
        snippet=best_snippet_for_failure,
    )


class CompanyExtractionResult(tuple):
    """
    Tuple containing (valid_contacts, dropped_candidates, was_cached)
    with an additional attribute .skipped_no_info.
    """

    def __new__(cls, valid_contacts, dropped_candidates, was_cached, skipped_no_info=0):
        return super().__new__(cls, (valid_contacts, dropped_candidates, was_cached))

    def __init__(self, valid_contacts, dropped_candidates, was_cached, skipped_no_info=0):
        self.valid_contacts = valid_contacts
        self.dropped_candidates = dropped_candidates
        self.was_cached = was_cached
        self.skipped_no_info = skipped_no_info


def extract_company_contacts(
    results: List[Dict[str, Any]],
    target_company: str,
    llm_provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
) -> CompanyExtractionResult:
    """
    Extracts recruiter contacts for a company from all its search results in ONE single LLM call.
    Uses extraction cache keyed by hash(model:company:prompt) to avoid redundant quota usage.
    Returns:
      CompanyExtractionResult((valid_contacts, dropped_candidates, was_cached), skipped_no_info=N)
    """
    if not results:
        return CompanyExtractionResult([], [], False, skipped_no_info=0)

    # Filter out results from data-broker blocklist BEFORE extraction
    valid_results = []
    broker_rejected_count = 0
    for r in results:
        url = r.get("url", "")
        if is_data_broker(url):
            broker_rejected_count += 1
            continue
        valid_results.append(r)

    if broker_rejected_count > 0:
        logger.info(f"Rejected {broker_rejected_count} data-broker result(s) matching blocklist")

    # Pre-filter: drop results with empty snippet AND name-only title
    clean_results = []
    skipped_no_info = 0
    for r in valid_results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        page_text = r.get("page_text")
        if is_name_only_empty_snippet(title, snippet, page_text):
            skipped_no_info += 1
            continue
        clean_results.append(r)

    if not clean_results:
        return CompanyExtractionResult([], [], False, skipped_no_info=skipped_no_info)

    selected_model = model or settings.LLM_FAST_MODEL

    formatted_items = []
    for idx, r in enumerate(clean_results, 1):
        url = r.get("url", "")
        title = r.get("title", "")
        pub_date = r.get("published_date") or ""
        snippet = r.get("snippet", "")
        page_text = r.get("page_text")
        body = page_text if page_text else snippet
        date_str = f"\nPublished Date: {pub_date}" if pub_date else ""
        hint = parse_title_hint(title)
        hint_str = ""
        if hint:
            hint_str = f"\nTitle Hint: [Name: {hint.get('name', '')} | Title: {hint.get('title', '')} | Company: {hint.get('company', '')}]"
        formatted_items.append(f"Result [{idx}]:\nTitle: {title}\nURL: {url}{date_str}{hint_str}\nContent: {body}\n")

    combined_web_content = (
        f"{WEB_CONTENT_PROMPT_RULE}\n\n<web_content>\n" + "\n---\n".join(formatted_items) + "\n</web_content>"
    )

    cache_key = hashlib.sha256(f"{selected_model}:{target_company}:{combined_web_content}".encode("utf-8")).hexdigest()

    cached_raw = get_cached_extraction(cache_key)
    if cached_raw is not None:
        was_cached = True
        raw_contacts = [CandidateContact.model_validate(c) for c in cached_raw]
    else:
        was_cached = False
        try:
            provider = llm_provider or get_llm_provider()
            extraction_result: ExtractionResult = provider.generate_structured(
                prompt=combined_web_content,
                response_model=ExtractionResult,
                system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
                model=selected_model,
            )
            raw_contacts = extraction_result.contacts
            write_cached_extraction(cache_key, [c.model_dump() for c in raw_contacts])
        except Exception as exc:
            logger.warning(f"Structured extraction LLM call failed, falling back to title hint parsing: {exc}")
            raw_contacts = []
            for r in clean_results:
                h = parse_title_hint(r.get("title", ""))
                if h and h.get("name"):
                    raw_contacts.append(
                        CandidateContact(
                            name=h["name"],
                            title=h.get("title") or "Campus Recruiter",
                            company=h.get("company") or target_company,
                            source_url=r.get("url"),
                            confidence=0.6,
                        )
                    )

    valid_contacts: List[CandidateContact] = []
    dropped_candidates: List[Dict[str, Any]] = []

    for cand in raw_contacts:
        is_name_ok, name_error = validate_full_name(cand.name)
        if not is_name_ok:
            dropped_candidates.append(
                {
                    "name": cand.name or "N/A",
                    "company": target_company,
                    "extracted_title": cand.title,
                    "source_url": cand.source_url or "",
                    "snippet": "",
                    "rule_failed": name_error,
                }
            )
            continue

        # Match candidate to its search result
        matched_r = None
        if cand.source_url:
            for r in clean_results:
                if (r.get("url") or "").strip().lower() == cand.source_url.strip().lower():
                    matched_r = r
                    break

        if not matched_r:
            name_low = cand.name.strip().lower()
            for r in clean_results:
                haystack = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
                if name_low in haystack:
                    matched_r = r
                    break

        if matched_r:
            cand.source_url = cand.source_url or matched_r.get("url")
            cand.published_date = cand.published_date or matched_r.get("published_date")
            fetch_status = matched_r.get("fetch_status", "not_fetched")
            cand.fetch_status = fetch_status
            cand.verified = fetch_status == "ok"
            result_block = f"{matched_r.get('title', '')}\n{matched_r.get('snippet', '')}"
            if matched_r.get("page_text"):
                result_block += f"\n{matched_r.get('page_text')}"
            fallback_snippet = matched_r.get("snippet") or matched_r.get("title") or ""
        else:
            cand.fetch_status = "not_fetched"
            cand.verified = False
            result_block = combined_web_content
            fallback_snippet = cand.matched_rule or ""

        # Staleness computation
        cand.stale = compute_staleness(cand.published_date)

        # Role type classification: campus/early-careers/university recruiting -> campus_recruiter
        if cand.title and any(
            k in cand.title.lower()
            for k in (
                "campus",
                "early career",
                "early-career",
                "early careers",
                "university recruit",
                "university relations",
            )
        ):
            cand.role_type = "campus_recruiter"

        # Location guard: location is null unless stated in the source text; never infer or default
        if cand.location:
            loc_lower = cand.location.strip().lower()
            if loc_lower not in result_block.lower():
                cand.location = None

        # Validate recruiter precision rules
        val_res = validate_recruiter_candidate(
            candidate=cand,
            text=result_block,
            target_company=target_company,
        )

        if not val_res.is_valid:
            dropped_candidates.append(
                {
                    "name": cand.name,
                    "company": target_company,
                    "extracted_title": cand.title,
                    "source_url": cand.source_url or "",
                    "snippet": val_res.snippet or fallback_snippet,
                    "rule_failed": val_res.failed_rule or "Failed precision validation",
                }
            )
            continue

        cand.matched_rule = val_res.matched_rule

        # Confidence capping:
        # For candidates backed only by a single unfetched source, cap confidence at 0.4 when stale and 0.6 otherwise
        if not cand.verified or cand.fetch_status != "ok":
            if cand.stale is True:
                cand.confidence = min(cand.confidence, 0.4)
            else:
                cand.confidence = min(cand.confidence, 0.6)

        valid_contacts.append(cand)

    return CompanyExtractionResult(valid_contacts, dropped_candidates, was_cached, skipped_no_info=skipped_no_info)


def extract_contacts_from_text(
    text: str,
    source_url: Optional[str] = None,
    gemini_client: Optional[genai.Client] = None,
    llm_provider: Optional[LLMProvider] = None,
    target_company: Optional[str] = None,
) -> List[CandidateContact]:
    """
    Extracts CandidateContact records from single web text using Pydantic validation via LLMProvider.
    Maintains compatibility with test fixtures.
    """
    if not text or not text.strip():
        return []

    if source_url and is_data_broker(source_url):
        logger.info("Rejected data-broker result matching blocklist")
        return []

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
            is_name_ok, _ = validate_full_name(contact.name)
            if not is_name_ok:
                continue

            val_res = validate_recruiter_candidate(
                candidate=contact,
                text=text,
                target_company=target_company,
            )
            if not val_res.is_valid:
                continue

            contact.matched_rule = val_res.matched_rule
            if source_url and not contact.source_url:
                contact.source_url = source_url

            contact.stale = compute_staleness(contact.published_date)
            if contact.location:
                if contact.location.strip().lower() not in text.lower():
                    contact.location = None

            if not contact.verified or contact.fetch_status != "ok":
                if contact.stale is True:
                    contact.confidence = min(contact.confidence, 0.4)
                else:
                    contact.confidence = min(contact.confidence, 0.6)

            valid_contacts.append(contact)

        return valid_contacts

    except Exception as exc:
        logger.warning(f"Error extracting contacts with LLM provider: {exc}")
        return []

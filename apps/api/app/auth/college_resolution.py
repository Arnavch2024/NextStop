"""
College resolution by email domain and fuzzy matching.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from supabase import Client

from app.db.supabase import get_supabase_client
from app.logger import logger

FREE_MAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "yahoo.co.uk",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "proton.me",
    "zoho.com",
    "mail.com",
    "yandex.com",
    "gmx.com",
}

NON_STANDALONE_SUFFIXES = {
    "ac.in",
    "edu.in",
    "res.in",
    "gov.in",
    "org.in",
    "co.in",
    "net.in",
    "ac.uk",
    "edu",
    "com",
    "in",
    "org",
    "net",
}


def get_candidate_domains(domain: str) -> List[str]:
    """
    Returns candidate domains to search in priority order:
    1. Exact domain (e.g. 'student.vjti.ac.in')
    2. Parent domains (e.g. 'vjti.ac.in')
    Does not yield bare suffixes like 'ac.in' or 'in'.
    """
    candidates = []
    parts = domain.lower().strip().split(".")

    for i in range(len(parts)):
        sub = ".".join(parts[i:])
        if sub in NON_STANDALONE_SUFFIXES or "." not in sub:
            continue
        candidates.append(sub)
    return candidates


def is_freemail_domain(domain: str) -> bool:
    """Returns True if the domain is a free-mail service provider (e.g. gmail.com, yahoo.com)."""
    if not domain:
        return False
    d = domain.lower().strip()
    return d in FREE_MAIL_DOMAINS or any(d == f or d.endswith("." + f) for f in FREE_MAIL_DOMAINS)


def get_registrable_root(domain: str) -> str:
    """
    Returns the registrable root (parent domain) for a given domain or subdomain.
    E.g.:
      'student.vjti.ac.in' -> 'vjti.ac.in'
      'me.vjti.ac.in' -> 'vjti.ac.in'
      'kjsce.somaiya.edu' -> 'somaiya.edu'
      'engineering.nmims.edu' -> 'nmims.edu'
      'vjti.ac.in' -> 'vjti.ac.in'
    """
    cands = get_candidate_domains(domain)
    return cands[-1] if cands else domain.lower().strip()


def resolve_college_from_email(
    email: Optional[str],
    is_email_verified: bool = True,
    client: Optional[Client] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolves the college record for a given email address.

    Rules:
    - Returns None if email is unverified (Supabase email_confirmed is False).
    - Returns None if email is empty or invalid.
    - Free-mail domains (gmail.com, yahoo.com, outlook.com, etc.) NEVER match.
    - Matches exact domain first, then parent domain (e.g. student.spit.ac.in -> spit.ac.in).
    - Returns college dict with id, name, city, etc.
    """
    if not is_email_verified:
        logger.debug(f"Email resolution skipped: unverified email '{email}'")
        return None

    if not email or "@" not in email:
        return None

    domain = email.strip().split("@")[-1].lower()

    if not domain or domain in FREE_MAIL_DOMAINS:
        logger.debug(f"Email resolution rejected: free-mail or empty domain '{domain}'")
        return None

    cli = client or get_supabase_client()
    candidates = get_candidate_domains(domain)

    for cand in candidates:
        try:
            res = (
                cli.table("college_domains")
                .select("id, college_id, domain, kind, source_url, colleges(*)")
                .eq("domain", cand)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                row = res.data[0]
                college = row.get("colleges")
                if college and isinstance(college, dict):
                    college_data = dict(college)
                    college_data["matched_domain"] = cand
                    college_data["domain_kind"] = row.get("kind")
                    return college_data
                elif row.get("college_id"):
                    c_res = cli.table("colleges").select("*").eq("id", row["college_id"]).limit(1).execute()
                    if c_res.data and len(c_res.data) > 0:
                        college_data = dict(c_res.data[0])
                        college_data["matched_domain"] = cand
                        college_data["domain_kind"] = row.get("kind")
                        return college_data
        except Exception as exc:
            logger.warning(f"Error querying college_domains for '{cand}': {exc}")

    return None


def fuzzy_match_college(
    query_text: str,
    client: Optional[Client] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fuzzily matches a user's free-text college mention against the colleges table.
    Checks acronyms in parentheses, token overlap, and string similarity.
    """
    if not query_text or not query_text.strip():
        return None

    clean_query = query_text.strip().lower()
    cli = client or get_supabase_client()

    try:
        res = cli.table("colleges").select("id, name, city").execute()
        colleges = res.data or []
    except Exception as exc:
        logger.warning(f"Could not load colleges for fuzzy match: {exc}")
        return None

    if not colleges:
        return None

    best_match = None
    best_score = 0.0

    for col in colleges:
        name = col.get("name", "")
        clean_name = name.lower()

        # 1. Exact match
        if clean_query == clean_name:
            return col

        # 2. Acronym match (e.g. 'vjti' in 'Veermata Jijabai Technological Institute (VJTI)')
        acronyms = re.findall(r"\((.*?)\)", clean_name)
        for acr in acronyms:
            if clean_query == acr or clean_query in acr.split():
                return col

        # 3. Substring match
        if clean_query in clean_name:
            score = len(clean_query) / len(clean_name) + 0.5
            if score > best_score:
                best_score = score
                best_match = col

        # 4. SequenceMatcher similarity
        sim = SequenceMatcher(None, clean_query, clean_name).ratio()
        if sim > 0.65 and sim > best_score:
            best_score = sim
            best_match = col

    if best_match and best_score >= 0.5:
        return best_match

    return None

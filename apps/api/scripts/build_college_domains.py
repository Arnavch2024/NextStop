#!/usr/bin/env python3
"""
Build data/seed/college_domains.csv from public sources.
Planning mode: writes NOTHING to the database.

Rules:
- 2 cached searches per college:
    "{college} placement cell contact email"
    "{college} official contact email"
- Data broker blocklist, no LinkedIn, no phone numbers.
- Read ONLY the college's own pages and official PDFs.
- Only write a row when the source page itself shows an address on that domain.
- Registrable root used as domain, subdomains noted in evidence.
- Skip free-mail domains (gmail.com, yahoo.com, outlook.com, etc.) and aggregators.
- Unresolved colleges go to a console list, never into the CSV.
- Print estimated call count first; require --yes above 80.
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# Add apps/api to sys.path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

import httpx  # noqa: E402

from app.auth.college_resolution import get_registrable_root, is_freemail_domain  # noqa: E402
from app.db.seed import MUMBAI_COLLEGES  # noqa: E402
from app.db.supabase import get_supabase_client  # noqa: E402
from app.logger import logger  # noqa: E402
from app.search.providers.extract import (  # noqa: E402
    is_data_broker,
    is_linkedin,
    robots_allows,
)
from app.search.web import web_search_enrich  # noqa: E402

CSV_OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed" / "college_domains.csv"

# Known aggregator and directory domains to reject
AGGREGATOR_DOMAINS: Set[str] = {
    "shiksha.com",
    "collegedunia.com",
    "careers360.com",
    "getmyuni.com",
    "collegedekho.com",
    "targetadmission.com",
    "collegepravesh.com",
    "zollege.in",
    "vidyavision.com",
    "embibe.com",
    "jagranjosh.com",
    "indiatoday.in",
    "hindustantimes.com",
    "timesofindia.indiatimes.com",
    "wikipedia.org",
    "wikimedia.org",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "quora.com",
    "reddit.com",
    "justdial.com",
    "sulekha.com",
    "indiamart.com",
    "yellowpages.com",
    "glassdoor.com",
    "indeed.com",
    "naukri.com",
    "ambitionbox.com",
    "yolasite.com",
    "weebly.com",
    "wixsite.com",
    "wordpress.com",
    "blogspot.com",
    "blogspot.in",
    "medium.com",
    "github.com",
    "linkedin.com",
    "lnkd.in",
}

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.(?:ac\.in|edu\.in|gov\.in|res\.in|co\.in|net\.in|org\.in|somaiya\.edu|nmims\.edu|edu|ac\.uk|org|in|com|net))\b",
    re.IGNORECASE,
)


def is_aggregator(url: str) -> bool:
    """Returns True if the URL belongs to an education aggregator or directory site."""
    try:
        host = urlparse(url).netloc.lower()
        if ":" in host:
            host = host.split(":")[0]
        for agg in AGGREGATOR_DOMAINS:
            if host == agg or host.endswith("." + agg):
                return True
        return False
    except Exception:
        return False


def is_pdf_url(url: str) -> bool:
    """Checks if the URL likely points to a PDF document."""
    clean = url.lower().split("?")[0].split("#")[0]
    return clean.endswith(".pdf")


def extract_text_from_pdf(content_bytes: bytes) -> str:
    """Safely and quickly extracts text from PDF bytes using fitz (PyMuPDF)."""
    try:
        import fitz

        doc = fitz.open(stream=content_bytes, filetype="pdf")
        pages_text = []
        for i in range(min(5, len(doc))):
            pages_text.append(doc[i].get_text())
        return "\n".join(pages_text)
    except Exception as exc:
        logger.debug(f"fitz PDF extraction failed: {exc}")
        return ""


def fetch_page_or_pdf(url: str, timeout: float = 4.0) -> Tuple[Optional[str], Optional[str]]:
    """Fetches public webpage or official PDF text.

    Returns (text, content_type). Never fetches LinkedIn, data brokers, or aggregators.
    """
    if is_linkedin(url) or is_data_broker(url) or is_aggregator(url):
        return None, None

    if not robots_allows(url):
        logger.debug(f"robots.txt disallows {url}")
        return None, None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    }

    try:
        t = httpx.Timeout(timeout, connect=2.0)
        with httpx.Client(timeout=t, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200 or len(resp.content) > 3 * 1024 * 1024:
                return None, None

            ctype = resp.headers.get("content-type", "").lower()
            if "application/pdf" in ctype or is_pdf_url(url):
                pdf_text = extract_text_from_pdf(resp.content)
                return pdf_text, "pdf"

            # Plain text / HTML
            return resp.text, "html"
    except Exception as exc:
        logger.debug(f"Fetch error for {url}: {exc}")
        return None, None


def classify_kind(context_window: str) -> str:
    """Classifies email domain kind as staff, student, or unknown based on surrounding context.

    Keep kind=unknown unless the page explicitly says the domain/email is for students or for staff.
    """
    cw = context_window.lower()
    is_student = any(
        k in cw
        for k in (
            "student email",
            "student domain",
            "students email",
            "student portal",
            "student id",
            "student mail",
            "student.ac.in",
            "student.",
            "@student",
            "for students",
        )
    )
    is_staff = any(
        k in cw
        for k in (
            "staff email",
            "faculty email",
            "staff domain",
            "faculty domain",
            "tpo email",
            "placement officer email",
            "officer email",
            "administration email",
            "dean email",
            "principal email",
            "for staff",
            "for faculty",
        )
    )
    if is_student and not is_staff:
        return "student"
    if is_staff and not is_student:
        return "staff"
    return "unknown"


def resolve_college_domain(
    college_name: str,
    known_placement_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Runs at most 2 cached searches for the college, reads official pages/PDFs,

    and extracts confirmed domain evidence.
    Returns record dict if resolved, None otherwise.
    """
    college_target = college_name if "mumbai" in college_name.lower() else f"{college_name} Mumbai"
    queries = [
        f"{college_target} placement cell contact email",
        f"{college_target} official contact email",
    ]

    all_results: List[Dict[str, Any]] = []

    # If known placement url exists, include as first candidate to check
    if known_placement_url:
        all_results.append({"url": known_placement_url, "snippet": ""})

    for q in queries:
        try:
            # Client=None writes NOTHING to database, uses local cache
            res = web_search_enrich(
                client=None,
                query=q,
                num_results=5,
            )
            results = res.get("results", [])
            for r in results:
                all_results.append(r)
        except Exception as exc:
            logger.warning(f"Search failed for '{q}': {exc}")

    # Pass 1: Check snippets of all candidate results first (fast, zero HTTP fetch overhead)
    for item in all_results:
        url = item.get("url", "")
        if not url:
            continue
        if is_data_broker(url) or is_linkedin(url) or is_aggregator(url):
            continue

        url_host = urlparse(url).netloc.lower()
        if ":" in url_host:
            url_host = url_host.split(":")[0]
        url_root = get_registrable_root(url_host)

        snippet = item.get("snippet", "") or ""
        if not snippet:
            continue

        for m in EMAIL_REGEX.finditer(snippet):
            email_domain = m.group(1).lower().rstrip(".")
            if is_freemail_domain(email_domain):
                continue
            if any(
                email_domain.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".pdf", ".svg", ".css", ".js", ".html")
            ):
                continue

            email_root = get_registrable_root(email_domain)
            if url_root and (
                email_root == url_root or url_host.endswith("." + email_root) or email_domain.endswith("." + url_root)
            ):
                start_idx = max(0, m.start() - 150)
                end_idx = min(len(snippet), m.end() + 150)
                kind = classify_kind(snippet[start_idx:end_idx])
                return {
                    "college_name": college_name,
                    "domain": email_root,
                    "kind": kind,
                    "source_url": url,
                    "evidence": f"x@{email_domain}",
                    "confidence": 1.0,
                }

    # Pass 2: If no snippet matched, inspect top 3 official pages/PDFs
    visited_urls: Set[str] = set()
    fetch_count = 0

    for item in all_results:
        url = item.get("url", "")
        if not url or url in visited_urls:
            continue
        visited_urls.add(url)

        if is_data_broker(url) or is_linkedin(url) or is_aggregator(url):
            continue

        url_host = urlparse(url).netloc.lower()
        if ":" in url_host:
            url_host = url_host.split(":")[0]
        url_root = get_registrable_root(url_host)

        fetch_count += 1
        if fetch_count > 3:
            break

        page_text, content_type = fetch_page_or_pdf(url)
        if not page_text:
            continue

        for m in EMAIL_REGEX.finditer(page_text):
            email_domain = m.group(1).lower().rstrip(".")
            if is_freemail_domain(email_domain):
                continue
            if any(
                email_domain.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".pdf", ".svg", ".css", ".js", ".html")
            ):
                continue

            email_root = get_registrable_root(email_domain)
            if url_root and (
                email_root == url_root or url_host.endswith("." + email_root) or email_domain.endswith("." + url_root)
            ):
                start_idx = max(0, m.start() - 150)
                end_idx = min(len(page_text), m.end() + 150)
                kind = classify_kind(page_text[start_idx:end_idx])
                return {
                    "college_name": college_name,
                    "domain": email_root,
                    "kind": kind,
                    "source_url": url,
                    "evidence": f"x@{email_domain}",
                    "confidence": 1.0 if not is_pdf_url(url) else 0.95,
                }

    return None


def load_colleges_list(
    explicit_colleges: Optional[List[str]] = None,
    extra_colleges: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Loads college targets from database, MUMBAI_COLLEGES, or CLI arguments."""
    colleges: List[Dict[str, Any]] = []

    if explicit_colleges:
        for c in explicit_colleges:
            colleges.append({"name": c.strip(), "placement_url": None})
    else:
        # Try loading from database without modifying it
        try:
            cli = get_supabase_client()
            res = cli.table("colleges").select("id, name, placement_url").execute()
            if res.data and len(res.data) > 0:
                for row in res.data:
                    colleges.append(
                        {
                            "id": row.get("id"),
                            "name": row["name"],
                            "placement_url": row.get("placement_url"),
                        }
                    )
        except Exception as exc:
            logger.debug(f"Could not load colleges from DB: {exc}")

        # Fallback to MUMBAI_COLLEGES seed data if DB returned nothing
        if not colleges:
            colleges = list(MUMBAI_COLLEGES)

    # Append any extra colleges requested
    if extra_colleges:
        existing_names = {c["name"].strip().lower() for c in colleges}
        for ec in extra_colleges:
            clean_ec = ec.strip()
            if clean_ec.lower() not in existing_names:
                colleges.append({"name": clean_ec, "placement_url": None})
                existing_names.add(clean_ec.lower())

    return colleges


def build_college_domains(
    colleges_list: List[Dict[str, Any]],
    output_path: Path,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Resolves domains for all colleges in list, formats CSV, and returns (resolved, unresolved)."""
    resolved_rows: List[Dict[str, Any]] = []
    unresolved_colleges: List[str] = []

    for idx, c in enumerate(colleges_list, 1):
        name = c["name"]
        p_url = c.get("placement_url")
        print(f"[{idx}/{len(colleges_list)}] Checking {name}...", flush=True)

        record = resolve_college_domain(name, known_placement_url=p_url)
        if record:
            if c.get("id"):
                record["college_id"] = c["id"]
            print(
                f"  -> Resolved: {record['domain']} (evidence: {record['evidence']}, kind: {record['kind']})",
                flush=True,
            )
            resolved_rows.append(record)
        else:
            print("  -> Unresolved: no verified institutional email domain found on official pages", flush=True)
            unresolved_colleges.append(name)

    # Print unresolved list in the console
    print("\n" + "=" * 50, flush=True)
    print(f"UNRESOLVED COLLEGES ({len(unresolved_colleges)}):", flush=True)
    print("=" * 50, flush=True)
    for un in unresolved_colleges:
        print(f" - {un}", flush=True)

    # Write CSV if not dry run
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["college_id", "college_name", "domain", "kind", "source_url", "evidence", "confidence"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in resolved_rows:
                writer.writerow(row)
        print(f"\nWrote {len(resolved_rows)} resolved records to {output_path}", flush=True)

    return resolved_rows, unresolved_colleges


def main() -> int:
    parser = argparse.ArgumentParser(description="Build college_domains.csv from public sources (planning mode).")
    parser.add_argument("--colleges", type=str, default=None, help="Comma-separated list of college names")
    parser.add_argument("--extra-colleges", type=str, default=None, help="Comma-separated list of extra colleges")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of colleges to process")
    parser.add_argument("--output", type=str, default=str(CSV_OUTPUT_PATH), help="Target CSV output path")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output CSV")
    parser.add_argument("--yes", action="store_true", help="Confirm execution when estimated search calls exceeds 80")

    args = parser.parse_args()

    explicit = [c.strip() for c in args.colleges.split(",") if c.strip()] if args.colleges else None
    extra = [c.strip() for c in args.extra_colleges.split(",") if c.strip()] if args.extra_colleges else None

    colleges = load_colleges_list(explicit_colleges=explicit, extra_colleges=extra)
    if args.limit:
        colleges = colleges[: args.limit]

    # Cap at 2 searches per college; print estimated call count first
    estimated_calls = len(colleges) * 2
    print(f"Estimated search calls: {estimated_calls}")

    if estimated_calls > 80 and not args.yes:
        print(f"ERROR: Estimated search calls ({estimated_calls}) exceeds 80. Pass --yes to confirm execution.")
        return 1

    out_p = Path(args.output)
    resolved, unresolved = build_college_domains(colleges, out_p, dry_run=args.dry_run)

    print("\nSummary:")
    print(f"Colleges resolved:   {len(resolved)}")
    print(f"Colleges unresolved: {len(unresolved)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Admin ingestion script: populates the shared contacts lake with real web data.
Never exposed as an API endpoint.
Features:
- Filters companies by optional --category (e.g. GCC) and --limit N
- Uses web_search_enrich with 7-day TTL cache
- Drops nameless candidates, merges on linkedin/email/name+company
- Respects rate limits via --delay (seconds)
- Supports --dry-run (simulates additions without writes)
- LinkedIn is never fetched; only public search result snippets/URLs used
- Never stores phone numbers
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from app.db.supabase import get_supabase_client  # noqa: E402
from app.search.ingest import run_ingest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest real-world recruiter contacts into the shared lake.")
    parser.add_argument("--category", type=str, default=None, help="Filter companies by category (e.g. 'GCC')")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies to process")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between search calls (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate ingestion without writing to database")
    parser.add_argument(
        "--queries-per-company",
        type=int,
        default=None,
        help="Number of search query templates per company (default from settings: 2)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm execution when estimated search calls exceeds 200",
    )
    parser.add_argument(
        "--only-urls",
        type=str,
        default=None,
        help="Comma-separated approved source URLs or path to file containing approved URLs",
    )

    args = parser.parse_args()

    print("==================================================")
    print("      Shared Lake Real Contact Ingestion         ")
    print("==================================================")
    print(f"Category:  {args.category or 'ALL'}")
    print(f"Limit:     {args.limit or 'ALL'}")
    print(f"Delay:     {args.delay}s")
    print(f"Dry Run:   {args.dry_run}")
    print(f"Queries:   {args.queries_per_company or 'Default (2)'}")
    if args.only_urls:
        print(f"Only URLs: {args.only_urls}")
    print("--------------------------------------------------")

    client = get_supabase_client()
    try:
        stats = run_ingest(
            client=client,
            category=args.category,
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
            queries_per_company=args.queries_per_company,
            confirm_yes=args.yes,
            only_urls=args.only_urls,
        )
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        return 1

    candidates = stats.get("candidates", [])
    if candidates:
        print("\nCandidate Contacts Identified (Accepted):")
        print(
            f"{'Company':<22} | {'Name':<20} | {'Op':<5} | {'Conf':<5} | {'Location':<18} | {'Stale':<5} | {'Pub Date':<10} | {'Title':<28} | {'Source URL'}"
        )
        print("-" * 180)
        for c in candidates:
            stale_str = "True" if c.get("stale") is True else ("False" if c.get("stale") is False else "None")
            loc_str = c.get("location") or "None"
            pub_str = (c.get("published_date") or "None")[:10]
            source_url = c.get("source_url") or "None"
            print(
                f"{c['company'][:21]:<22} | {c['name'][:19]:<20} | {c['operation']:<5} | {c.get('confidence', 0.6):<5.2f} | {loc_str:<18} | {stale_str:<5} | {pub_str:<10} | {c['title'][:27]:<28} | {source_url}"
            )

    dropped = stats.get("dropped_candidates", [])
    if dropped:
        print("\nDropped Candidates Identified:")
        print(f"{'Company':<22} | {'Name':<20} | {'Extracted Title':<25} | {'Rule Failed':<45} | {'Snippet'}")
        print("-" * 170)
        for d in dropped:
            name = (d.get("name") or "N/A")[:19]
            comp = (d.get("company") or "")[:21]
            title = (d.get("extracted_title") or "N/A")[:24]
            rule = (d.get("rule_failed") or "")[:44]
            snip = (d.get("snippet") or "").replace("\n", " ")
            snip_short = (snip[:50] + "...") if len(snip) > 50 else snip
            print(f"{comp:<22} | {name:<20} | {title:<25} | {rule:<45} | {snip_short}")

    print("\n================ Ingestion Summary ================")
    print(f"Companies processed:      {stats['companies_processed']}")
    print(f"Contacts added:           {stats['contacts_added']}")
    print(f"Contacts merged:          {stats['contacts_merged']}")
    print(f"Contacts dropped:         {stats['contacts_dropped']}")
    print(f"Skipped, no information:  {stats.get('skipped_no_info', 0)}")
    print(f"Broker results rejected:  {stats.get('broker_results_rejected', 0)}")
    print(f"Errors encountered:       {stats['errors']}")
    calls = stats.get("provider_calls", {})
    if calls:
        print("---------------- Provider Calls ----------------")
        print(f"Exa search calls:    {calls.get('exa', 0)}")
        print(f"Tavily search calls: {calls.get('tavily', 0)}")
        print(f"Gemini LLM calls:    {calls.get('gemini', 0)}")
        print(f"Served from cache:   {calls.get('cache_hits', 0)}")
        print("---------------- Gemini Calls per Company ------")
        print("Before fix: ~10 calls per company (30 total for 3 companies)")
        gem_per_comp = calls.get("gemini_per_company", {})
        for comp, count in gem_per_comp.items():
            print(f"After fix:  {comp[:25]:<26}: {count} call(s)")
    print("====================================================")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

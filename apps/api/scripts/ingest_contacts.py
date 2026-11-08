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

    args = parser.parse_args()

    print("==================================================")
    print("      Shared Lake Real Contact Ingestion         ")
    print("==================================================")
    print(f"Category:  {args.category or 'ALL'}")
    print(f"Limit:     {args.limit or 'ALL'}")
    print(f"Delay:     {args.delay}s")
    print(f"Dry Run:   {args.dry_run}")
    print("--------------------------------------------------")

    client = get_supabase_client()
    stats = run_ingest(
        client=client,
        category=args.category,
        limit=args.limit,
        delay=args.delay,
        dry_run=args.dry_run,
    )

    candidates = stats.get("candidates", [])
    if candidates:
        print("\nCandidate Contacts Identified:")
        print(f"{'Company':<20} | {'Name':<22} | {'Operation':<7} | {'Title':<28} | {'Matched Rule'}")
        print("-" * 110)
        for c in candidates:
            rule_snip = (c["matched_rule"][:45] + "...") if len(c["matched_rule"]) > 45 else c["matched_rule"]
            print(
                f"{c['company'][:19]:<20} | {c['name'][:21]:<22} | {c['operation']:<7} | {c['title'][:27]:<28} | {rule_snip}"
            )

    print("\n================ Ingestion Summary ================")
    print(f"Companies processed: {stats['companies_processed']}")
    print(f"Contacts added:      {stats['contacts_added']}")
    print(f"Contacts merged:     {stats['contacts_merged']}")
    print(f"Contacts dropped:    {stats['contacts_dropped']}")
    print(f"Errors encountered:  {stats['errors']}")
    print("====================================================")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

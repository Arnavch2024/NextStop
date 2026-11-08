#!/usr/bin/env python3
"""
Admin script to purge synthetic/seed contacts and their provenance rows from the shared lake.
Requires explicit --yes flag to perform deletion.
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from app.db.supabase import get_supabase_client  # noqa: E402
from app.search.purge import run_purge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge seed contacts and provenance records from the lake.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion of seed contacts and contact_sources rows",
    )

    args = parser.parse_args()

    client = get_supabase_client()
    res = run_purge(client=client, confirm=args.yes)

    print("==================================================")
    print("           Purge Seed Data Scan                   ")
    print("==================================================")
    print(f"Seed contacts found:        {res['contacts_found']}")
    print(f"Seed contact_sources found: {res['sources_found']}")
    print("--------------------------------------------------")

    if not args.yes:
        print("[WARNING] Dry-run only. To delete these rows, re-run with --yes:")
        print("          python scripts/purge_seed.py --yes")
        return 0

    print(f"[SUCCESS] Purged {res['contacts_deleted']} seed contacts and {res['sources_deleted']} sources rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

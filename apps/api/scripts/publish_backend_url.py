import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.supabase import get_supabase_client


def publish_backend_url(url: str):
    cli = get_supabase_client()
    payload = json.dumps({"api_base_url": url.strip().rstrip("/")}).encode("utf-8")
    try:
        res = cli.storage.from_("app-config").upload(
            "backend_url.json", payload, file_options={"upsert": "true", "content-type": "application/json"}
        )
        print(f"Successfully published active backend URL to Supabase: {url}")
        return res
    except Exception as e:
        print(f"Error publishing backend URL: {e}")
        return None


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://characteristics-minds-compute-friends.trycloudflare.com"
    publish_backend_url(target_url)

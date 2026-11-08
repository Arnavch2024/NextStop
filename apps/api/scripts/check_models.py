#!/usr/bin/env python3
"""
Pre-flight check script to verify that configured LLM models are accepted by the provider.
Makes one cheap 1-token real call per configured model. Fails loudly with exit code 1
and the rejected model name if any model is rejected.
"""

import sys
from pathlib import Path

# Add project root to sys.path
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from app.config import settings  # noqa: E402
from app.llm.base import ModelRejectedError  # noqa: E402
from app.llm.check_models import check_configured_models  # noqa: E402


def run():
    print(f"Checking configured LLM models (Provider: {settings.LLM_PROVIDER})...")
    print(f"  LLM_AGENT_MODEL: {settings.LLM_AGENT_MODEL}")
    print(f"  LLM_FAST_MODEL:  {settings.LLM_FAST_MODEL}")

    try:
        results = check_configured_models(raise_on_error=True)
        for model, status in results.items():
            print(f"  [OK] Model '{model}' responded successfully: {status}")
        print("\nAll configured models verified.")
        sys.exit(0)
    except ModelRejectedError as err:
        print(f"\n[FATAL] Model rejection error:\n{err}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error during model check:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()

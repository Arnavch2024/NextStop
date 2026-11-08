import os
import sys
from typing import Dict, List, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.llm.base import ModelRejectedError
from app.logger import logger


def should_skip_model_check() -> bool:
    """
    Returns True if model verification should be skipped (e.g., in CI or test runners).
    """
    if os.environ.get("CI", "").lower() in ("true", "1"):
        return True
    if os.environ.get("GITHUB_ACTIONS", "").lower() in ("true", "1"):
        return True
    if os.environ.get("SKIP_MODEL_CHECK", "").lower() in ("true", "1", "yes"):
        return True
    if settings.ENVIRONMENT.lower() in ("test", "testing"):
        return True
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True

    key = settings.raw_gemini_api_key
    if not key or key.startswith("dummy-") or key.startswith("placeholder-"):
        return True

    return False


def check_model_cheap_call(
    model_name: str,
    client: Optional[genai.Client] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Makes a single cheap 1-token real call to verify that the configured model is accepted.
    Raises ModelRejectedError loudly with the model name if rejected by the provider.
    """
    if not client:
        effective_key = api_key or settings.raw_gemini_api_key
        if not effective_key:
            raise ModelRejectedError(model_name, "API key is missing or not configured.")
        client = genai.Client(api_key=effective_key)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents="ping",
            config=types.GenerateContentConfig(max_output_tokens=1),
        )
        return response.text or "OK"
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Configured model '{model_name}' was rejected: {err_msg}")
        raise ModelRejectedError(model_name=model_name, message=err_msg) from exc


def check_configured_models(
    models: Optional[List[str]] = None,
    raise_on_error: bool = True,
    client: Optional[genai.Client] = None,
) -> Dict[str, str]:
    """
    Checks each configured LLM model with a cheap real call.
    Fails loudly with ModelRejectedError if rejected.
    """
    if should_skip_model_check():
        logger.info("Skipping LLM model verification in CI/test environment.")
        target = models or [settings.LLM_AGENT_MODEL, settings.LLM_FAST_MODEL]
        return {m: "SKIPPED (CI/test)" for m in target}

    target_models = list(dict.fromkeys(models or [settings.LLM_AGENT_MODEL, settings.LLM_FAST_MODEL]))
    results: Dict[str, str] = {}

    for model_name in target_models:
        try:
            check_model_cheap_call(model_name=model_name, client=client)
            results[model_name] = "OK"
            logger.info(f"Model '{model_name}' verified successfully.")
        except ModelRejectedError as exc:
            results[model_name] = f"REJECTED: {exc}"
            if raise_on_error:
                raise exc

    return results


def main() -> int:
    """CLI runner for checking configured models."""
    print("Verifying configured Gemini models with a cheap real call...")
    models_to_check = [settings.LLM_AGENT_MODEL, settings.LLM_FAST_MODEL]
    try:
        results = check_configured_models(models=models_to_check, raise_on_error=True)
        for m, status in results.items():
            print(f"  [OK] Model '{m}': {status}")
        print("All configured models are active and accepted.")
        return 0
    except ModelRejectedError as err:
        print(f"\n[FATAL ERROR] {err}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

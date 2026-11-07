import logging
import re

# Regex to detect bearer tokens or sensitive API keys
BEARER_TOKEN_PATTERN = re.compile(r"(Bearer\s+)([A-Za-z0-9\-_\.=]{8,})", re.IGNORECASE)
GENERIC_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|authorization)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-_\.]{8,})", re.IGNORECASE
)


def redact_secret_string(text: str) -> str:
    """Masks tokens and secrets in strings."""
    if not isinstance(text, str):
        return text

    # Redact Bearer tokens: keep Bearer and first 4 chars, redact the rest
    def _mask_bearer(m):
        prefix = m.group(1)
        token = m.group(2)
        if len(token) > 8:
            return f"{prefix}{token[:4]}...[REDACTED]"
        return f"{prefix}[REDACTED]"

    text = BEARER_TOKEN_PATTERN.sub(_mask_bearer, text)

    def _mask_secret(m):
        key = m.group(1)
        val = m.group(2)
        return f"{key}='{val[:3]}...[REDACTED]'"

    text = GENERIC_SECRET_PATTERN.sub(_mask_secret, text)
    return text


class SafeLogFilter(logging.Filter):
    """Logging filter that ensures tokens and secrets are redacted from all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secret_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (redact_secret_string(v) if isinstance(v, str) else v) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_secret_string(v) if isinstance(v, str) else v for v in record.args)
        return True


def get_logger(name: str = "api") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SafeLogFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger("recruiting_api")

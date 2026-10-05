"""Console logging for local development."""

import logging

from app.core.config import get_settings


def setup_logging(level: str | None = None) -> None:
    """Send application logs to the console. Callers must not log secrets."""
    resolved_level = level or get_settings().log_level
    numeric_level = getattr(logging, resolved_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )

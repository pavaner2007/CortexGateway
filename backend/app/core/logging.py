"""
Cortex Gateway — Structured Logging Configuration.

Uses Loguru for structured, JSON-friendly logging.
Call ``configure_logging()`` once during application startup.
Import ``logger`` from this module everywhere else in the application.
"""

import sys

from loguru import logger

from app.config.settings import get_settings


def configure_logging() -> None:
    """
    Remove default Loguru handlers and install a single stderr sink
    configured according to application settings.

    Output format includes timestamp, level, request_id (when present),
    module, and message.  In production the level is typically INFO;
    DEBUG is available in development via the LOG_LEVEL env var.
    """
    settings = get_settings()

    logger.remove()  # drop the default handler

    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
        colorize=True,
        backtrace=False,      # never print full tracebacks to the sink
        diagnose=False,       # never expose local variable values
        enqueue=True,         # thread-safe async-friendly logging
    )

    logger.info(
        "Logging configured",
        level=settings.log_level.upper(),
        environment=settings.environment,
    )


# Re-export the Loguru logger so all modules import from one place.
__all__ = ["logger", "configure_logging"]

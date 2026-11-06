"""
Structured logging configuration for UrbanPulse backend.
Provides consistent JSON-structured logging with request tracing, severity levels,
and graceful fallback for degraded services (Ollama, Redis, external APIs).
"""

import logging
import logging.config
import os
import sys
from typing import Optional


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": (
                "[%(asctime)s] %(levelname)-8s %(name)s "
                "%(filename)s:%(lineno)d | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "standard",
            "level": LOG_LEVEL,
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"],
    },
    "loggers": {
        "urbanpulse": {"level": LOG_LEVEL, "propagate": True},
        "uvicorn": {"level": "WARNING", "propagate": True},
        "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        "httpx": {"level": "WARNING", "propagate": True},
    },
}


def configure_logging() -> None:
    """Apply UrbanPulse structured logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the 'urbanpulse' hierarchy."""
    if not name.startswith("urbanpulse."):
        name = f"urbanpulse.{name}"
    return logging.getLogger(name)


def log_degraded_service(logger: logging.Logger, service: str, reason: str, fallback: Optional[str] = None) -> None:
    """Log graceful degradation with consistent structured message."""
    msg = f"[DEGRADED] {service} unavailable: {reason}"
    if fallback:
        msg += f" | Fallback: {fallback}"
    logger.warning(msg)


def log_external_api_error(logger: logging.Logger, api_name: str, status_code: int, detail: str) -> None:
    """Log external API errors consistently."""
    logger.error(f"[EXTERNAL_API_ERROR] {api_name} returned HTTP {status_code}: {detail}")


def log_cache_hit(logger: logging.Logger, cache_key: str, latency_ms: float) -> None:
    """Log cache hits for observability."""
    logger.debug(f"[CACHE_HIT] key={cache_key[:32]}... | latency={latency_ms:.1f}ms")


def log_cache_miss(logger: logging.Logger, cache_key: str) -> None:
    """Log cache misses for observability."""
    logger.debug(f"[CACHE_MISS] key={cache_key[:32]}...")

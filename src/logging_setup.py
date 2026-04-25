"""Loguru configuration: stderr + daily-rotating file logs."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level: <8}</level> "
    "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
    "| {message}"
)


def configure_logging(level: str, log_dir: Path) -> None:
    """Configure loguru sinks. Idempotent — safe to call more than once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stderr,
        level=level,
        format=_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=False,  # avoid leaking values into prod logs
    )

    logger.add(
        log_dir / "bot_{time:YYYY-MM-DD}.log",
        level=level,
        format=_FORMAT,
        rotation="00:00",  # rotate at midnight local time
        retention="30 days",
        compression="gz",
        enqueue=True,  # safe under concurrent writers
        backtrace=True,
        diagnose=False,
    )

    _CONFIGURED = True
    logger.debug("logging configured: level={} dir={}", level, log_dir)


def reset_logging_for_tests() -> None:
    """Test hook: undo configure_logging so a fresh call reconfigures."""
    global _CONFIGURED
    logger.remove()
    _CONFIGURED = False

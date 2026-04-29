"""Loguru-based structured logging with daily rotation."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
    )
    logger.add(
        log_dir / "bot_{time:YYYY-MM-DD}.log",
        level=level,
        rotation="00:00",
        retention="30 days",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} | {message}",
    )
    logger.add(
        log_dir / "orders_{time:YYYY-MM-DD}.log",
        level="INFO",
        rotation="00:00",
        retention="365 days",
        enqueue=True,
        filter=lambda record: record["extra"].get("channel") == "orders",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
    )


def order_logger():
    """Return a logger bound to the orders channel (for audit log)."""
    return logger.bind(channel="orders")

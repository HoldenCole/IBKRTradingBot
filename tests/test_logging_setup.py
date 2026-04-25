"""Tests for src.logging_setup."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.logging_setup import configure_logging, reset_logging_for_tests


def test_configure_creates_log_dir_and_writes_file(tmp_path: Path):
    reset_logging_for_tests()
    log_dir = tmp_path / "logs"
    configure_logging("DEBUG", log_dir)

    logger.info("hello from test")
    logger.complete()  # flush enqueued sinks

    assert log_dir.exists()
    log_files = list(log_dir.glob("bot_*.log"))
    assert len(log_files) == 1
    assert "hello from test" in log_files[0].read_text()


def test_configure_is_idempotent(tmp_path: Path):
    reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    configure_logging("INFO", log_dir)
    configure_logging("INFO", log_dir)  # second call should be a no-op

    logger.info("second message")
    logger.complete()

    log_files = list(log_dir.glob("bot_*.log"))
    text = log_files[0].read_text()
    # Message should appear exactly once, not duplicated by a second sink
    assert text.count("second message") == 1

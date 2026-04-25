"""Tests for src.config."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Mode, Settings


def _settings(**overrides) -> Settings:
    """Build Settings with kwargs, ignoring any .env file on disk."""
    return Settings(_env_file=None, **overrides)


def test_defaults_are_paper_safe():
    s = _settings()
    assert s.mode is Mode.PAPER
    assert s.is_paper
    assert not s.is_live
    assert s.ibkr_port == 4002
    assert s.weekly_loss_budget_usd == 500.0


def test_log_level_normalized_and_validated():
    assert _settings(log_level="debug").log_level == "DEBUG"
    with pytest.raises(ValidationError):
        _settings(log_level="bogus")


def test_port_range_enforced():
    with pytest.raises(ValidationError):
        _settings(ibkr_port=22)  # below 1024
    with pytest.raises(ValidationError):
        _settings(ibkr_port=70000)  # above 65535


def test_premium_cap_must_be_fraction():
    with pytest.raises(ValidationError):
        _settings(max_gross_premium_pct_nav=1.5)
    with pytest.raises(ValidationError):
        _settings(max_gross_premium_pct_nav=0)


def test_live_requires_risk_flag():
    s = _settings(mode="live")
    with pytest.raises(RuntimeError, match="i-understand-the-risk"):
        s.assert_live_authorized(risk_flag=False)
    s.assert_live_authorized(risk_flag=True)  # no raise


def test_paper_ignores_risk_flag():
    s = _settings(mode="paper")
    s.assert_live_authorized(risk_flag=False)
    s.assert_live_authorized(risk_flag=True)

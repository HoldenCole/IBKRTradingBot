"""Tests for the Yahoo provider — minimal because we don't want to hit
the network in unit tests. Cover the asset-mapping + error paths."""
from __future__ import annotations

from datetime import date

import pytest

from src.deploy.providers import YahooCloseProvider


def test_unknown_asset_raises():
    p = YahooCloseProvider()
    with pytest.raises(ValueError, match="Unknown asset"):
        p.closes("MNQ", date(2026, 6, 20), 250)


def test_asset_mapping_covers_stage1():
    # Hard guarantee: the providers module supports the two assets the
    # Stage-1 deployment uses. If a future PR drops one of these, the
    # daily-check job breaks; this test pins that contract.
    from src.deploy.providers import _ASSET_TO_YAHOO_TICKER
    assert "QQQ" in _ASSET_TO_YAHOO_TICKER
    assert "BTC" in _ASSET_TO_YAHOO_TICKER
    assert _ASSET_TO_YAHOO_TICKER["QQQ"] == "QQQ"
    assert _ASSET_TO_YAHOO_TICKER["BTC"] == "BTC-USD"

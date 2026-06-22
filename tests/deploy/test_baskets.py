"""Tests for the basket configuration + sizing layer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.deploy.baskets import BasketConfig, StrategySpec


def test_loads_default_config_and_validates():
    cfg = BasketConfig.load()
    assert cfg.stage == 1
    # Stage 1: baskets 2 and 3 enabled at 50/50
    assert cfg.baskets["2"].enabled and cfg.baskets["3"].enabled
    assert abs(cfg.enabled_weight_total() - 1.0) < 1e-9


def test_enabled_weights_must_sum_to_one(tmp_path):
    bad = {
        "schema_version": 1, "stage": 1, "rebalance": {},
        "baskets": {
            "2": {"name": "x", "weight": 0.5, "enabled": True,
                  "strategies": [{"id": "a", "asset": "BTC", "signal": "sma_crossover"}]},
            "3": {"name": "y", "weight": 0.4, "enabled": True,
                  "strategies": [{"id": "b", "asset": "QQQ", "signal": "sma_crossover"}]},
        },
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="sum to 1.0"):
        BasketConfig.load(p)


def test_disabled_basket_with_weight_rejected(tmp_path):
    bad = {
        "schema_version": 1, "stage": 1, "rebalance": {},
        "baskets": {
            "2": {"name": "x", "weight": 1.0, "enabled": True,
                  "strategies": [{"id": "a", "asset": "BTC", "signal": "sma_crossover"}]},
            "4": {"name": "z", "weight": 0.2, "enabled": False, "strategies": []},
        },
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="disabled but has nonzero weight"):
        BasketConfig.load(p)


def test_enabled_basket_without_strategy_rejected(tmp_path):
    bad = {
        "schema_version": 1, "stage": 1, "rebalance": {},
        "baskets": {
            "2": {"name": "x", "weight": 1.0, "enabled": True, "strategies": []},
        },
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="no strategies"):
        BasketConfig.load(p)


def test_allocations_stage1_50_50():
    cfg = BasketConfig.load()
    allocs = cfg.allocations(account_equity_usd=8000.0)
    # two enabled strategies (BTC, QQQ) at 50/50
    by_asset = {a.asset: a for a in allocs}
    assert set(by_asset) == {"BTC", "QQQ"}
    assert abs(by_asset["BTC"].target_dollars - 4000.0) < 1e-6
    assert abs(by_asset["QQQ"].target_dollars - 4000.0) < 1e-6
    assert abs(sum(a.target_weight for a in allocs) - 1.0) < 1e-9


def test_vehicle_resolves_by_account_size():
    cfg = BasketConfig.load()
    # BTC: IBIT below 25k, MBT at/above 25k
    a8k = {a.asset: a for a in cfg.allocations(8000.0)}
    a30k = {a.asset: a for a in cfg.allocations(30000.0)}
    assert a8k["BTC"].vehicle == "IBIT"
    assert a30k["BTC"].vehicle == "MBT"
    # QQQ: shares below 60k, MNQ at/above 60k
    a70k = {a.asset: a for a in cfg.allocations(70000.0)}
    assert a8k["QQQ"].vehicle == "QQQ_SHARES"
    assert a70k["QQQ"].vehicle == "MNQ"


def test_vehicle_for_account_threshold_logic():
    s = StrategySpec(id="x", asset="QQQ", signal="sma_crossover", params={},
                     off_vehicle="tbill",
                     vehicle_by_account_usd={"0": "QQQ_SHARES", "60000": "MNQ"})
    assert s.vehicle_for_account(0) == "QQQ_SHARES"
    assert s.vehicle_for_account(59999) == "QQQ_SHARES"
    assert s.vehicle_for_account(60000) == "MNQ"
    assert s.vehicle_for_account(250000) == "MNQ"


def test_filed_candidates_present_in_diversifier_baskets():
    cfg = BasketConfig.load()
    # Bonds filed in basket 5, commodities in basket 4
    assert any("Bond" in c or "bond" in c for c in cfg.baskets["5"].filed_candidates)
    assert any("ommodit" in c for c in cfg.baskets["4"].filed_candidates)
    # Both disabled at 0 weight (filed, not deployed)
    assert not cfg.baskets["4"].enabled and cfg.baskets["4"].weight == 0.0
    assert not cfg.baskets["5"].enabled and cfg.baskets["5"].weight == 0.0

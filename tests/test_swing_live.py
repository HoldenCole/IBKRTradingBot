"""Live 3x swing account: order planning, accounting and fills (synthetic data, temp files, no network)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio import swing_live as sv
from src.regime.quadrant import Quadrant
from tests.test_swing_logger import CALM_SP, book, uptrend


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(sv, "CONFIG", tmp_path / "acct.json")
    monkeypatch.setattr(sv, "ORDERS", tmp_path / "orders.csv")
    monkeypatch.setattr(sv, "TRADES", tmp_path / "trades.csv")
    cfg = sv.load_config()
    cfg["deposits"] = [{"date": "2026-12-01", "amount": 1000.0}]
    sv.save_config(cfg)
    return tmp_path


def test_buy_order_sizes_whole_shares_of_the_3x_fund_from_half_the_equity(files):
    px = book(uptrend(tail=(-0.01, -0.025, -0.045)), uptrend())
    cfg = sv.load_config()
    orders = sv.plan_orders(px, CALM_SP, Quadrant.REFLATION, cfg, [], {"UPRO": 117.0, "TQQQ": 45.0}, 1000.0)
    buys = [o for o in orders if o["side"] == "BUY"]
    assert len(buys) == 1 and buys[0]["fund"] == "UPRO" and buys[0]["shares"] == 4      # floor(500 / 117)


def test_blocked_signal_gives_no_order(files):
    px = book(uptrend(tail=(-0.01, -0.025, -0.045)), uptrend())
    orders = sv.plan_orders(px, CALM_SP, Quadrant.STAGFLATION, sv.load_config(), [], {"UPRO": 117.0, "TQQQ": 45.0}, 1000.0)
    assert not [o for o in orders if o["side"] in ("BUY", "SELL")]
    assert any(o["reason"].startswith("BLOCKED") for o in orders)


def test_exit_order_sells_the_live_position(files):
    spy = uptrend(tail=(-0.01, -0.025, -0.045, -0.035, -0.02, 0.0))
    px = book(spy, uptrend())
    entry = spy.index[-4].date().isoformat()
    live = [{"trade_id": "1", "signal": "SPY", "fund": "UPRO", "entry_date": entry, "shares": "4", "entry_px": "110",
             "entry_source": "close", "exit_date": "", "exit_px": "", "exit_source": "", "exit_reason": "", "commission": "0.35", "pnl": ""}]
    orders = sv.plan_orders(px, CALM_SP, Quadrant.REFLATION, sv.load_config(), live, {"UPRO": 117.0, "TQQQ": 45.0}, 1000.0)
    sells = [o for o in orders if o["side"] == "SELL"]
    assert sells and sells[0]["fund"] == "UPRO" and sells[0]["shares"] == "4" and sells[0]["trade_id"] == "1"


def test_settle_books_at_the_close_and_a_confirmed_fill_overrides(files, monkeypatch):
    sv._write(sv.ORDERS, [{"date": "2026-12-02", "issued_at": "x", "side": "BUY", "fund": "UPRO", "signal": "SPY",
                           "shares": 4, "ref_price": 117.0, "reason": "band", "trade_id": ""}], sv.ORDER_FIELDS)
    monkeypatch.setattr(sv, "_raw_last", lambda f: (pd.Timestamp("2026-12-02"), 116.0))
    assert sv.settle("2026-12-02") == ["bought 4 UPRO at 116.00"]
    assert sv.settle("2026-12-02") == []                       # idempotent
    sv.record_fill("2026-12-02", "BUY", "UPRO", "4", "115.5")
    e = sv.equity(sv.load_config(), sv._read(sv.TRADES), {"UPRO": 120.0})
    assert e["cash"] == pytest.approx(1000 - 4 * 115.5 - 0.35)
    assert e["equity"] == pytest.approx(1000 - 4 * 115.5 - 0.35 + 4 * 120.0)


def test_sell_settles_pnl_net_of_both_commissions(files, monkeypatch):
    sv._write(sv.TRADES, [{"trade_id": "1", "signal": "SPY", "fund": "UPRO", "entry_date": "2026-12-02", "shares": "4",
                           "entry_px": "116", "entry_source": "close", "exit_date": "", "exit_px": "", "exit_source": "",
                           "exit_reason": "", "commission": "0.35", "pnl": ""}], sv.TRADE_FIELDS)
    sv._write(sv.ORDERS, [{"date": "2026-12-04", "issued_at": "x", "side": "SELL", "fund": "UPRO", "signal": "SPY",
                           "shares": "4", "ref_price": 121.0, "reason": "above_sma5", "trade_id": "1"}], sv.ORDER_FIELDS)
    monkeypatch.setattr(sv, "_raw_last", lambda f: (pd.Timestamp("2026-12-04"), 121.0))
    sv.settle("2026-12-04")
    t = sv._read(sv.TRADES)[0]
    assert float(t["pnl"]) == pytest.approx(4 * 5 - 0.70)
    e = sv.equity(sv.load_config(), sv._read(sv.TRADES), {})
    assert e["equity"] == pytest.approx(1000 + 4 * 5 - 0.70) and e["positions"] == 0

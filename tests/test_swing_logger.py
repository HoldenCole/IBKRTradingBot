"""Swing paper-logger tests — synthetic prices, no network."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.swing_logger import LEVERED, SYMBOLS, account_curve, fragile_state, indicators, step
from src.regime.quadrant import Quadrant


def series(vals, end="2026-11-13"):
    idx = pd.bdate_range(end=end, periods=len(vals))
    return pd.Series(np.asarray(vals, dtype=float), index=idx)


def uptrend(n=260, tail=()):
    base = list(100 * 1.0005 ** np.arange(n - len(tail)))
    last = base[-1]
    return series(base + [last * (1 + x) for x in tail])


def book(spy, qqq):
    px = {"SPY": spy, "QQQ": qqq}
    for s, (l2, l3) in LEVERED.items():
        px[l2] = px[s] ** 2 / px[s].iloc[0]          # any co-moving series will do
        px[l3] = px[s] ** 3 / px[s].iloc[0] ** 2
    return px


CALM_SP = uptrend(260)
CALM_SP = CALM_SP * (1 + 0.10 * np.linspace(0, 1, len(CALM_SP)))   # well above its 200d, low vol


def test_pullback_in_uptrend_is_an_entry_signal():
    ind = indicators(uptrend(tail=(-0.01, -0.025, -0.045)))
    assert ind["rsi2"] < 10 and ind["above_200"] and ind["entry_signal"]
    assert not indicators(uptrend())["entry_signal"]


def test_enters_when_gate_open_and_blocks_when_not():
    px = book(uptrend(tail=(-0.01, -0.025, -0.045)), uptrend())
    trades, row, actions = step(px, CALM_SP, Quadrant.REFLATION, [])
    assert [t["symbol"] for t in trades] == ["SPY"] and row["gate_ok"]
    assert any(a.startswith("ENTER SPY") for a in actions)
    trades, row, actions = step(px, CALM_SP, Quadrant.STAGFLATION, [])
    assert trades == [] and not row["gate_ok"]
    assert any(a.startswith("BLOCKED SPY") for a in actions)


def test_exit_on_close_above_sma5_and_levered_marks():
    spy = uptrend(tail=(-0.01, -0.025, -0.045, -0.035, -0.02, 0.0))   # dip then recovery
    px = book(spy, uptrend())
    entry = spy.index[-4]                                             # the -4.5% close
    open_trade = [{"trade_id": 1, "symbol": "SPY", "entry_date": entry.date().isoformat(),
                   "entry_px": float(spy.loc[entry])}]
    trades, row, actions = step(px, CALM_SP, Quadrant.REFLATION, open_trade)
    t = trades[0]
    assert t["exit_reason"] == "above_sma5" and t["days"] == 3
    gross = spy.iloc[-1] / spy.loc[entry] - 1
    assert abs(t["ret_1x"] - (gross - 0.001)) < 1e-4
    assert t["ret_3x"] > t["ret_2x"] > t["ret_1x"] > 0


def test_time_stop_after_ten_bars():
    spy = uptrend(tail=tuple(-0.01 * k for k in range(1, 13)))        # keeps falling: never above SMA5
    px = book(spy, uptrend())
    entry = spy.index[-11]
    trades, _, _ = step(px, CALM_SP, Quadrant.GROWTH,
                        [{"trade_id": 1, "symbol": "SPY", "entry_date": entry.date().isoformat(), "entry_px": 1.0}])
    assert trades[0]["exit_reason"] == "time_stop" and trades[0]["days"] == 10


def test_fragile_state_blocks_entries():
    rng = np.random.default_rng(0)
    flat = 100 * np.cumprod(1 + rng.normal(0, 0.015, 260))            # ~24% vol
    sp = series(flat)
    sp.iloc[-1] = sp.iloc[-200:-1].mean() * 1.015                      # ~1.5% above its 200d
    fragile, ext, rvol = fragile_state(sp)
    assert fragile and 0 <= ext <= 0.03 and rvol > 0.16
    px = book(uptrend(tail=(-0.01, -0.025, -0.045)), uptrend())
    trades, row, _ = step(px, sp, Quadrant.GROWTH, [])
    assert trades == [] and row["fragile"] and not row["gate_ok"]


def test_account_curve_uses_half_slots():
    trades = [{"exit_date": "x", "ret_1x": 0.02, "ret_2x": 0.04, "ret_3x": 0.06},
              {"exit_date": "", "ret_1x": "", "ret_2x": "", "ret_3x": ""}]
    acc = account_curve(trades)
    assert abs(acc["1x"] - 0.01) < 1e-12 and abs(acc["3x"] - 0.03) < 1e-12
    assert set(SYMBOLS) == {"SPY", "QQQ"}

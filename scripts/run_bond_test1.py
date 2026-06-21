"""Test 1 (priority) — Bond trend on Treasury futures (ZN, ZB, ZF).

The one genuine equity-stress diversifier not yet tested. Equity-validated
50/200 trend, vol-targeted basket across the 3 tenors, long-flat, T-bill on
OFF capital, no same-bar look-ahead. Databento 2010-2026 (pre-2010 not
available; the load-bearing question is post-2020 anyway).

THE LOAD-BEARING QUESTION: does bond trend work in the POST-2020 regime
(mixed/rising rates), not just the 1982-2020 declining-rate bull. 2022 is the
decisive data point — the year buy-and-hold bonds lost 30%+ and the
diversification thesis broke. If bond TREND was profitable/flat in 2022 while
being uncorrelated with equity, that's the finding.

================================ LOCKED CRITERIA ===============================
  Tier A: Sortino > 1.0 full  AND  Sortino > 0.5 in 2022 specifically
          AND positive in 2018-Q4  AND correlation with equity < 0.3
  Tier B: Sortino > 0.7 full  AND  non-negative in 2022
          AND positive in >=1 equity-stress window  AND correlation < 0.4
  Tier C: Sortino > 0.5 but fails post-2020 robustness (historical, not deployable)
  Tier D: anything else
===============================================================================
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.data.databento_loader import DatabentoLoader, collapse_to_trade_date, panama_adjust
from src.commodity import signals as sig
from src.commodity import metrics as M
from src.commodity.engine import run_backtest, EngineConfig, _roll_dates_from_raw

RAW = REPO / "data" / "commodities" / "databento_raw"
START, END = "2010-06-06", "2026-06-20"
TENORS = {"ZN": "10yr note", "ZB": "30yr bond", "ZF": "5yr note"}
SECTORS = {s: "Rates" for s in TENORS}   # all one 'sector' for the engine cost map

SUBPERIODS = [
    ("pre-2020 declining-rate", date(2010, 6, 6),  date(2019, 12, 31)),
    ("post-2020 mixed regime",  date(2020, 1, 1),  date(2026, 6, 20)),
    ("2022 ONLY (load-bearing)",date(2022, 1, 1),  date(2022, 12, 31)),
]
EQUITY_STRESS = [
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def equity_returns():
    from src.data import yahoo
    df = yahoo.daily("QQQ", "2010-01-01", "2026-06-21")
    r = df["close"].pct_change(); r.index = pd.to_datetime(r.index)
    return r


def load_bond_panel():
    loader = DatabentoLoader()
    adj = {}
    for root in TENORS:
        v0 = collapse_to_trade_date(loader.continuous(root, depth=0, start=START, end=END))
        v1 = collapse_to_trade_date(loader.continuous(root, depth=1, start=START, end=END))
        adj[root] = panama_adjust(v0, v1)["close"]
    close = pd.DataFrame(adj).sort_index()
    # returns from back-adjusted: diff / raw-prior. Use raw v0 prior for scale.
    rets = {}
    for root in TENORS:
        v0 = collapse_to_trade_date(loader.continuous(root, depth=0, start=START, end=END))["close"]
        rets[root] = adj[root].diff() / v0.reindex(adj[root].index).shift(1)
    return close, pd.DataFrame(rets).sort_index()


def main() -> int:
    close, rets = load_bond_panel()
    roll_dates = _roll_dates_from_raw(RAW, list(TENORS))
    on = sig.sma_crossover(close, 50, 200)

    cfg = EngineConfig(target_vol=0.10, max_weight=0.50, cov_lookback=60,
                       tbill_annual=0.02, apply_costs=True, scheme="inverse_vol")
    res = run_backtest(close, rets, on, SECTORS, cfg, roll_dates)
    m = M.compute(res.daily_returns, res.equity)

    print("=" * 92)
    print("# BOND TREND TEST 1 — 50/200 vol-targeted basket (ZN/ZB/ZF), 2010-2026")
    print("=" * 92)
    print(f"\n  Universe: {', '.join(f'{k} ({v})' for k,v in TENORS.items())}")
    print(f"  Vol target 10%, T-bill 2% OFF, costs on, no look-ahead\n")
    print(f"  Full sample: CAGR {m.cagr:+.1%}  Sortino {m.sortino:.2f}  "
          f"Sharpe {m.sharpe:.2f}  MaxDD {m.max_drawdown:.0%}  Vol {m.vol:.0%}")
    print(f"  Avg instruments ON/day {res.n_on.mean():.1f}, "
          f"turnover {res.turnover.sum()/(len(res.turnover)/252):.1f}x/yr")

    # ---- per-era ----
    print("\n  REGIME SPLIT (the load-bearing test):")
    sub_metrics = {}
    for lbl, a, b in SUBPERIODS:
        mm = M.compute(sub(res.daily_returns, a, b))
        sub_metrics[lbl] = mm
        print(f"    {lbl:<26} Sortino {mm.sortino:+.2f}  CAGR {mm.cagr:+.1%}  MaxDD {mm.max_drawdown:.0%}")

    # bond buy-and-hold comparison in 2022 (the thesis-break year)
    bah_2022 = {}
    for root in TENORS:
        r = sub(rets[root], date(2022,1,1), date(2022,12,31))
        bah_2022[root] = (1+r.fillna(0)).prod()-1
    print(f"\n  2022 context — bond BUY-AND-HOLD returns (the thesis broke here):")
    print("    " + "  ".join(f"{k} {v:+.0%}" for k,v in bah_2022.items()))
    print(f"    bond TREND in 2022: {sub_metrics['2022 ONLY (load-bearing)'].cagr:+.1%} "
          f"(Sortino {sub_metrics['2022 ONLY (load-bearing)'].sortino:+.2f})")

    # ---- equity correlation + per-stress-window ----
    eq = equity_returns()
    full_corr = M.correlation(res.daily_returns, eq)
    print(f"\n  Equity correlation (full sample): {full_corr:+.2f}")
    print(f"\n  {'Equity-stress window':<22}{'Bond ret':>10}{'Equity ret':>12}{'Corr':>8}")
    stress_pos = 0
    win_2018q4 = None
    for lbl, a, b in EQUITY_STRESS:
        bd, ed = sub(res.daily_returns, a, b), sub(eq, a, b)
        bond_ret = (1+bd).prod()-1
        if bond_ret > 0:
            stress_pos += 1
        if lbl.startswith("2018"):
            win_2018q4 = bond_ret
        print(f"  {lbl:<22}{bond_ret:>+9.1%}{(1+ed).prod()-1:>+11.1%}{M.correlation(bd,ed):>+8.2f}")

    # ---- locked verdict ----
    print("\n" + "=" * 92)
    print("# VERDICT (locked criteria)")
    print("=" * 92)
    s2022 = sub_metrics["2022 ONLY (load-bearing)"].sortino
    c2022 = sub_metrics["2022 ONLY (load-bearing)"].cagr
    def verdict():
        if (m.sortino > 1.0 and s2022 > 0.5 and (win_2018q4 or 0) > 0 and full_corr < 0.3):
            return "A"
        if (m.sortino > 0.7 and c2022 >= 0 and stress_pos >= 1 and full_corr < 0.4):
            return "B"
        if m.sortino > 0.5:
            return "C"
        return "D"
    t = verdict()
    print(f"\n  Full Sortino {m.sortino:.2f} | 2022 Sortino {s2022:+.2f} (CAGR {c2022:+.1%}) | "
          f"2018-Q4 {win_2018q4:+.1%} | corr {full_corr:+.2f} | stress-wins {stress_pos}/4")
    print(f"\n  >>> BOND TREND: TIER {t} <<<")
    if t in ("A", "B"):
        print("  Clears Tier B -> deployable equity-stress diversifier. FX test (Test 2) shelved.")
    else:
        print("  Fails Tier B -> trigger Test 2 (FX carry + trend) per the decision tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

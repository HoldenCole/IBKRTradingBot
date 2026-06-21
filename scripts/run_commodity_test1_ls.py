"""Second pass — Test 1: Long-short V3 (vol-adjusted momentum).

Takes the one variant that worked long-flat (V3) and removes the long-flat
restriction: LONG top 1/3 of trailing range, SHORT bottom 1/3, FLAT middle.
Futures-collateral accounting (capital earns T-bill; long/short futures
overlay on top). Same basket / costs / vol-targeting as the first pass.

Reframed mandate: the commodity sleeve must provide UNCORRELATED returns
during equity stress, not match the equity Sortino. So the headline is the
PER-REGIME correlation analysis, not just full-sample stats.

Locked Tier criteria (second pass — more DD tolerance):
  A: Sortino>1.0, MaxDD<30%, corr_equity<0.3, BOTH sub-periods +Sortino,
     >=3 of 6 sectors positive
  B: Sortino>0.7, MaxDD<35%, corr_equity<0.4, both sub-periods robust,
     >=2 sectors
  C: Sortino>0.5, marginal otherwise
  D: else
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.commodity import loader as cload
from src.commodity import signals as sig
from src.commodity import metrics as M
from src.commodity.engine import run_backtest_ls, EngineConfig, _roll_dates_from_raw

RAW_DIR = REPO / "data" / "commodities" / "databento_raw"
TAX_HIGHER = (0.20, 0.37)

SUBPERIODS = [
    ("2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 6, 20)),
    ("2013-2017 (held-out)", date(2013, 1, 1), date(2017, 12, 31)),
]

# Crisis windows for the per-regime correlation analysis (the real test).
REGIMES = [
    ("2014-16 oil crash",   date(2014, 6, 1),  date(2016, 2, 28)),
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]


def sub(s: pd.Series, a: date, b: date) -> pd.Series:
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def equity_strategy_returns() -> pd.Series | None:
    """QQQ 50/200 + T-bill-OFF daily returns (Convention 2, no-lookahead)."""
    try:
        from src.data import yahoo
        df = yahoo.daily("QQQ", "2010-01-01", "2026-06-20")
        c = df["close"]
        smaf = c.rolling(50, min_periods=50).mean()
        smas = c.rolling(200, min_periods=200).mean()
        on = ((c > smaf) & (smaf > smas)).shift(1).fillna(False)
        r = c.pct_change().where(on, 0.0)
        r.index = pd.to_datetime(r.index)
        return r
    except Exception as e:
        print(f"  (equity strategy returns unavailable: {e!r})")
        return None


def main() -> int:
    panel = cload.load()
    rets = panel.returns()
    sectors = {s: cload.SECTOR[s] for s in panel.symbols}
    roll_dates = _roll_dates_from_raw(RAW_DIR, panel.symbols)

    direction = sig.vol_adj_momentum_ls(rets, 252, 504)
    cfg = EngineConfig(target_vol=0.15, max_weight=0.25, cov_lookback=60,
                       tbill_annual=0.02, apply_costs=True)
    res = run_backtest_ls(rets, direction, sectors, cfg, roll_dates)
    m = M.compute(res.daily_returns, res.equity, ltcg=TAX_HIGHER[0], stcg=TAX_HIGHER[1])

    print("=" * 96)
    print("# SECOND PASS — TEST 1: Long-short V3 vol-adjusted momentum")
    print("# Databento 2010-2026, 10 CME commodities, futures-collateral accounting")
    print("=" * 96)

    print("\n## Headline (full sample, net of costs)")
    print(f"  CAGR {m.cagr:+.1%}  Sharpe {m.sharpe:.2f}  Sortino {m.sortino:.2f}  "
          f"MaxDD {m.max_drawdown:.0%}  Vol {m.vol:.0%}  AT-CAGR {m.after_tax_cagr:+.1%}")
    print(f"  Avg active positions/day: {res.n_on.mean():.1f}  "
          f"median gross |exposure|: {res.gross_long.median():.2f}")
    print(f"  Annual turnover: {res.turnover.sum()/(len(res.turnover)/252):.1f}x  "
          f"cost drag: {res.cost_drag.sum()/(len(res.cost_drag)/252)*100:.2f}%/yr")

    # Long-flat V3 reference (first pass) for context
    onmask = sig.vol_adj_momentum(rets, 252, 504)
    from src.commodity.engine import run_backtest
    res_lf = run_backtest(panel.close, rets, onmask, sectors, cfg, roll_dates)
    m_lf = M.compute(res_lf.daily_returns, res_lf.equity, ltcg=TAX_HIGHER[0], stcg=TAX_HIGHER[1])
    print(f"\n  [reference] long-FLAT V3 (first pass): Sortino {m_lf.sortino:.2f}, "
          f"CAGR {m_lf.cagr:+.1%}, MaxDD {m_lf.max_drawdown:.0%}")

    print("\n## Sub-period robustness (locked criterion: BOTH must be +Sortino)")
    sub_sortinos = []
    for lbl, a, b in SUBPERIODS:
        d = sub(res.daily_returns, a, b)
        mm = M.compute(d)
        sub_sortinos.append(mm.sortino)
        flag = "OK" if mm.sortino > 0 else "NEGATIVE"
        print(f"  {lbl:<26} Sortino {mm.sortino:+.2f}  CAGR {mm.cagr:+.1%}   [{flag}]")

    # Per-sector attribution
    print("\n## Per-sector P&L attribution (cumulative contribution %)")
    bysec = {}
    for s in panel.symbols:
        bysec.setdefault(cload.SECTOR[s], 0.0)
        bysec[cload.SECTOR[s]] += res.per_instrument_pnl.get(s, 0.0)
    for sec, v in sorted(bysec.items(), key=lambda kv: -kv[1]):
        print(f"  {sec:<12} {v*100:+.1f}")
    n_sec_pos = sum(1 for v in bysec.values() if v > 0)
    print(f"  -> {n_sec_pos} of {len(bysec)} sectors positive")
    print("  per-instrument:", {s: round(res.per_instrument_pnl.get(s,0)*100,1)
                                  for s in panel.symbols})

    # ---------------- THE KEY TEST: per-regime correlation ----------------
    eq = equity_strategy_returns()
    print("\n" + "=" * 96)
    print("# PER-REGIME CORRELATION WITH EQUITY STRATEGY (the diversification test)")
    print("=" * 96)
    if eq is None:
        print("  equity strategy returns unavailable — skipping")
    else:
        full_corr = M.correlation(res.daily_returns, eq)
        print(f"\n  Full-sample correlation with equity strategy: {full_corr:+.2f}")
        print(f"\n  {'Regime':<22}{'Comm ret':>10}{'Equity ret':>12}"
              f"{'Corr':>8}{'N days':>8}")
        for lbl, a, b in REGIMES:
            cd = sub(res.daily_returns, a, b)
            ed = sub(eq, a, b)
            comm_cum = (1 + cd).prod() - 1
            eq_cum = (1 + ed).prod() - 1
            c = M.correlation(cd, ed)
            print(f"  {lbl:<22}{comm_cum:>+9.1%}{eq_cum:>+11.1%}"
                  f"{c:>+8.2f}{len(cd):>8}")
        print("\n  Interpretation: low/negative corr DURING equity drawdowns is the")
        print("  value we want. High corr during crises = limited diversification.")

    # ---------------- Tier verdict ----------------
    print("\n" + "=" * 96)
    print("# TIER VERDICT (second-pass criteria)")
    print("=" * 96)
    full_corr = M.correlation(res.daily_returns, eq) if eq is not None else 0.0
    sub_ok = all(s > 0 for s in sub_sortinos)
    def verdict():
        if (m.sortino > 1.0 and m.max_drawdown < 0.30 and full_corr < 0.3
                and sub_ok and n_sec_pos >= 3):
            return "A"
        if (m.sortino > 0.7 and m.max_drawdown < 0.35 and full_corr < 0.4
                and sub_ok and n_sec_pos >= 2):
            return "B"
        if m.sortino > 0.5:
            return "C"
        return "D"
    t = verdict()
    print(f"\n  Sortino {m.sortino:.2f} | MaxDD {m.max_drawdown:.0%} | "
          f"corr_equity {full_corr:+.2f} | sub-periods both+ {sub_ok} "
          f"({sub_sortinos[0]:+.2f},{sub_sortinos[1]:+.2f}) | sectors+ {n_sec_pos}")
    print(f"\n  >>> TIER {t} <<<")
    if t in ("C", "D"):
        print("  Fails Tier B -> proceed to Test 2 (carry signal) per the decision tree.")
    else:
        print("  Clears Tier B -> deployable candidate; carry test optional.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Second pass — Test 2: Carry (term-structure roll-yield) signal.

Triggered because Test 1 (long-short V3 trend) landed Tier C, failing Tier B.
Question: is a NON-trend signal a real, additional return stream?

Signal (locked):
  ratio = (front_month - second_month) / front_month     [per instrument]
    +1 LONG  when ratio > 0            (backwardation, positive roll yield)
    -1 SHORT when ratio < -0.005       (deep contango, negative roll yield)
     0 FLAT  otherwise
Computed on RAW (unadjusted) front (.v.0) and second (.v.1) closes — the
term-structure relationship requires actual contract prices, not the Panama
back-adjusted series. RETURNS are still the back-adjusted series (you hold the
front and roll it; your P&L is the back-adjusted continuous return).

Caveat (locked-definition limitation, documented not fixed): the front-second
gap is ~1 month for energy but ~2 months for metals and ~quarter for grains,
so the raw ratio is exact "monthly carry" only for energy. The LONG leg is
sign-based (unaffected); the SHORT threshold is magnitude-sensitive and biases
longer-gap sectors away from shorting. A second look would normalize by
days-to-expiry; per one-look discipline we run the locked definition.

Same vol-targeting, costs, futures-collateral accounting as Test 1.

CRITICAL per the mandate: report carry's correlation against BOTH the equity
strategy AND the Test 1 trend strategy. Uncorrelated with both => real third
line. Correlated with either => not adding new information.

Tier criteria identical to Test 1.
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
from src.data.databento_loader import DatabentoLoader, collapse_to_trade_date

RAW_DIR = REPO / "data" / "commodities" / "databento_raw"
START, END = "2010-06-06", "2026-06-20"
TAX_HIGHER = (0.20, 0.37)

SUBPERIODS = [
    ("2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 6, 20)),
    ("2013-2017 (held-out)", date(2013, 1, 1), date(2017, 12, 31)),
]
REGIMES = [
    ("2014-16 oil crash",   date(2014, 6, 1),  date(2016, 2, 28)),
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def equity_strategy_returns():
    from src.data import yahoo
    df = yahoo.daily("QQQ", "2010-01-01", "2026-06-20")
    c = df["close"]
    on = ((c > c.rolling(50, min_periods=50).mean()) &
          (c.rolling(50, min_periods=50).mean() > c.rolling(200, min_periods=200).mean())
          ).shift(1).fillna(False)
    r = c.pct_change().where(on, 0.0); r.index = pd.to_datetime(r.index)
    return r


def load_raw_front_second(symbols):
    """Raw (unadjusted) front (.v.0) and second (.v.1) closes, trade-date
    collapsed, as date x symbol DataFrames."""
    loader = DatabentoLoader()
    front, second = {}, {}
    for s in symbols:
        v0 = collapse_to_trade_date(loader.continuous(s, depth=0, start=START, end=END))
        v1 = collapse_to_trade_date(loader.continuous(s, depth=1, start=START, end=END))
        front[s] = v0["close"]
        second[s] = v1["close"]
    return pd.DataFrame(front), pd.DataFrame(second)


def main() -> int:
    panel = cload.load()
    rets = panel.returns()
    sectors = {s: cload.SECTOR[s] for s in panel.symbols}
    roll_dates = _roll_dates_from_raw(RAW_DIR, panel.symbols)

    front, second = load_raw_front_second(panel.symbols)
    front = front.reindex(rets.index)
    second = second.reindex(rets.index)
    direction = sig.carry_signal(front, second, short_threshold_monthly=-0.005)

    cfg = EngineConfig(target_vol=0.15, max_weight=0.25, cov_lookback=60,
                       tbill_annual=0.02, apply_costs=True)
    res = run_backtest_ls(rets, direction, sectors, cfg, roll_dates)
    m = M.compute(res.daily_returns, res.equity, ltcg=TAX_HIGHER[0], stcg=TAX_HIGHER[1])

    print("=" * 96)
    print("# SECOND PASS — TEST 2: Carry (term-structure roll-yield)")
    print("# Databento 2010-2026, 10 CME commodities, futures-collateral accounting")
    print("=" * 96)

    print("\n## Headline (full sample, net of costs)")
    print(f"  CAGR {m.cagr:+.1%}  Sharpe {m.sharpe:.2f}  Sortino {m.sortino:.2f}  "
          f"MaxDD {m.max_drawdown:.0%}  Vol {m.vol:.0%}  AT-CAGR {m.after_tax_cagr:+.1%}")
    print(f"  Avg active positions/day: {res.n_on.mean():.1f}  "
          f"median gross |exposure|: {res.gross_long.median():.2f}  "
          f"turnover {res.turnover.sum()/(len(res.turnover)/252):.1f}x/yr")

    print("\n## Sub-period robustness (BOTH must be +Sortino)")
    sub_sortinos = []
    for lbl, a, b in SUBPERIODS:
        mm = M.compute(sub(res.daily_returns, a, b))
        sub_sortinos.append(mm.sortino)
        print(f"  {lbl:<26} Sortino {mm.sortino:+.2f}  CAGR {mm.cagr:+.1%}  "
              f"[{'OK' if mm.sortino>0 else 'NEGATIVE'}]")

    print("\n## Per-sector P&L attribution (cumulative %)")
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

    # ---- correlations: vs equity AND vs Test 1 trend (the critical test) ----
    eq = equity_strategy_returns()
    # rebuild Test 1 trend returns for the cross-correlation
    tr_dir = sig.vol_adj_momentum_ls(rets, 252, 504)
    res_tr = run_backtest_ls(rets, tr_dir, sectors, cfg, roll_dates)

    print("\n" + "=" * 96)
    print("# CORRELATIONS — carry vs equity strategy AND vs Test 1 trend (KEY)")
    print("=" * 96)
    c_eq = M.correlation(res.daily_returns, eq)
    c_tr = M.correlation(res.daily_returns, res_tr.daily_returns)
    print(f"\n  Carry vs EQUITY strategy:   {c_eq:+.2f}")
    print(f"  Carry vs TEST-1 trend:      {c_tr:+.2f}")
    print("  (Uncorrelated with BOTH => real third line. Correlated with either")
    print("   => not adding new information.)")

    print("\n## Per-regime: carry behavior during equity stress")
    print(f"\n  {'Regime':<22}{'Carry ret':>10}{'Equity ret':>12}{'Corr':>8}{'N':>6}")
    for lbl, a, b in REGIMES:
        cd, ed = sub(res.daily_returns, a, b), sub(eq, a, b)
        print(f"  {lbl:<22}{(1+cd).prod()-1:>+9.1%}{(1+ed).prod()-1:>+11.1%}"
              f"{M.correlation(cd, ed):>+8.2f}{len(cd):>6}")

    # ---- combined trend+carry sleeve (50/50 daily-return blend) ----
    print("\n" + "=" * 96)
    print("# COMBINED trend + carry sleeve (50/50 equal-risk daily blend)")
    print("=" * 96)
    joined = pd.concat([res_tr.daily_returns.rename("trend"),
                        res.daily_returns.rename("carry")], axis=1).dropna()
    combo = 0.5 * joined["trend"] + 0.5 * joined["carry"]
    mc = M.compute(combo)
    cc_eq = M.correlation(combo, eq)
    print(f"\n  Combined Sortino {mc.sortino:.2f}  CAGR {mc.cagr:+.1%}  "
          f"MaxDD {mc.max_drawdown:.0%}  corr_equity {cc_eq:+.2f}")
    cs = []
    for lbl, a, b in SUBPERIODS:
        cs.append(M.compute(sub(combo, a, b)).sortino)
    print(f"  Sub-periods: 2018-26 {cs[0]:+.2f}, 2013-17 {cs[1]:+.2f}")

    # ---- Tier verdict for carry standalone ----
    print("\n" + "=" * 96)
    print("# TIER VERDICT — carry standalone (second-pass criteria)")
    print("=" * 96)
    sub_ok = all(s > 0 for s in sub_sortinos)
    def verdict(sortino, dd, corr, ok, nsec):
        if sortino > 1.0 and dd < 0.30 and corr < 0.3 and ok and nsec >= 3: return "A"
        if sortino > 0.7 and dd < 0.35 and corr < 0.4 and ok and nsec >= 2: return "B"
        if sortino > 0.5: return "C"
        return "D"
    t = verdict(m.sortino, m.max_drawdown, c_eq, sub_ok, n_sec_pos)
    print(f"\n  Sortino {m.sortino:.2f} | MaxDD {m.max_drawdown:.0%} | corr_eq {c_eq:+.2f} | "
          f"sub both+ {sub_ok} ({sub_sortinos[0]:+.2f},{sub_sortinos[1]:+.2f}) | sectors+ {n_sec_pos}")
    print(f"\n  >>> Carry standalone: TIER {t} <<<")
    print(f"  >>> Carry vs trend corr {c_tr:+.2f} — "
          f"{'orthogonal, real third line' if abs(c_tr) < 0.3 else 'overlaps trend'} <<<")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

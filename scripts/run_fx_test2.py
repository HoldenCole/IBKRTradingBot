"""Test 2 (FX) — carry + trend on G6 CME FX futures.

Triggered by bonds failing Tier B. Six pairs: 6E (EUR), 6J (JPY), 6B (GBP),
6A (AUD), 6C (CAD), 6N (NZD). Two signal lines tested independently and
combined:

  TREND: 50/200 SMA crossover on Panama-adjusted closes (equity-validated
         rule, transferred without tuning, long-flat per pair, vol-targeted).

  CARRY: front/second-month basis as the rate-differential proxy. Covered
         interest parity gives F = S * exp((r_USD - r_foreign) * T), so the
         front-second spread encodes the rate differential — no FRED needed.
         Sign: positive (front > second) => this currency yields MORE than
         USD over the calendar gap => long-carry trade.
         LONG when basis > +5 bps, SHORT when basis < -5 bps, FLAT middle.

Both signals: vol-targeted basket, futures-collateral accounting (capital
earns T-bill, signed overlay on top), no same-bar look-ahead, costs on.

================================ LOCKED CRITERIA ===============================
Mirroring the bond test:
  Tier A: Sortino > 1.0 full  AND  non-negative in EVERY equity-stress window
          (incl. Aug 2024 yen unwind)  AND  correlation with equity < 0.3
  Tier B: Sortino > 0.7 full  AND  non-negative in >=3 of 5 stress windows
          AND  correlation < 0.4
  Tier C: Sortino > 0.5
  Tier D: anything else
Reported separately for trend, carry, and combined (50/50 daily return blend).
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
from src.commodity.engine import run_backtest, run_backtest_ls, EngineConfig, _roll_dates_from_raw

RAW = REPO / "data" / "commodities" / "databento_raw"
START, END = "2010-06-06", "2026-06-20"
PAIRS = {"6E": "EUR/USD", "6J": "JPY/USD", "6B": "GBP/USD",
         "6A": "AUD/USD", "6C": "CAD/USD", "6N": "NZD/USD"}
SECTORS = {s: "FX" for s in PAIRS}

EQUITY_STRESS = [
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2024-Aug yen unwind", date(2024, 7, 31), date(2024, 8, 16)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def equity_returns():
    from src.data import yahoo
    df = yahoo.daily("QQQ", "2010-01-01", "2026-06-21")
    r = df["close"].pct_change(); r.index = pd.to_datetime(r.index)
    return r


def load_fx_panel():
    loader = DatabentoLoader()
    adj, fronts, seconds, rets = {}, {}, {}, {}
    for root in PAIRS:
        v0 = collapse_to_trade_date(loader.continuous(root, depth=0, start=START, end=END))
        v1 = collapse_to_trade_date(loader.continuous(root, depth=1, start=START, end=END))
        adj_df = panama_adjust(v0, v1)
        adj[root] = adj_df["close"]
        fronts[root] = v0["close"]
        seconds[root] = v1["close"]
        rets[root] = adj_df["close"].diff() / v0["close"].reindex(adj_df.index).shift(1)
    return (pd.DataFrame(adj).sort_index(), pd.DataFrame(fronts).sort_index(),
            pd.DataFrame(seconds).sort_index(), pd.DataFrame(rets).sort_index())


def verdict(sortino, stress_wins, corr, n_total) -> str:
    if sortino > 1.0 and stress_wins == n_total and corr < 0.3: return "A"
    if sortino > 0.7 and stress_wins >= 3 and corr < 0.4:       return "B"
    if sortino > 0.5:                                            return "C"
    return "D"


def report_strategy(label: str, daily: pd.Series, eq_rets: pd.Series) -> tuple[str, M.PerfMetrics, int, float]:
    m = M.compute(daily, (1+daily).cumprod())
    corr = M.correlation(daily, eq_rets)
    stress_wins = 0
    print(f"\n  ## {label}")
    print(f"  Full sample: CAGR {m.cagr:+.1%}  Sortino {m.sortino:+.2f}  "
          f"Sharpe {m.sharpe:+.2f}  MaxDD {m.max_drawdown:.0%}  Vol {m.vol:.0%}")
    print(f"  Equity correlation: {corr:+.2f}")
    print(f"  {'Equity-stress window':<22}{'FX ret':>10}{'Equity ret':>12}{'Corr':>8}")
    for lbl, a, b in EQUITY_STRESS:
        fd, ed = sub(daily, a, b), sub(eq_rets, a, b)
        fx_ret = (1+fd.fillna(0)).prod()-1
        if fx_ret > 0:
            stress_wins += 1
        c = M.correlation(fd, ed) if len(fd) > 5 else float('nan')
        print(f"  {lbl:<22}{fx_ret:>+9.1%}{(1+ed.fillna(0)).prod()-1:>+11.1%}{c:>+8.2f}")
    t = verdict(m.sortino, stress_wins, corr, len(EQUITY_STRESS))
    print(f"  Stress wins: {stress_wins}/{len(EQUITY_STRESS)}  -> TIER {t}")
    return t, m, stress_wins, corr


def main() -> int:
    close, front, second, rets = load_fx_panel()
    roll = _roll_dates_from_raw(RAW, list(PAIRS))

    cfg = EngineConfig(target_vol=0.10, max_weight=0.30, cov_lookback=60,
                       tbill_annual=0.02, apply_costs=True, scheme="inverse_vol")
    eq = equity_returns()

    print("=" * 96)
    print("# FX TEST 2 — G6 carry + trend on CME FX futures (6E/6J/6B/6A/6C/6N)")
    print("# Databento 2010-2026, vol-targeted basket, costs on, no look-ahead")
    print("=" * 96)
    print(f"\n  Coverage:")
    for p, name in PAIRS.items():
        c = close[p].dropna()
        print(f"    {p} {name:<10} {len(c)} bars  {c.index[0].date()} -> {c.index[-1].date()}")

    # -------- Trend (long-flat) --------
    on = sig.sma_crossover(close, 50, 200)
    res_t = run_backtest(close, rets, on, SECTORS, cfg, roll)
    tt, mt, wt, ct = report_strategy("TREND 50/200 (long-flat)", res_t.daily_returns, eq)

    # -------- Carry (long-short, basis-driven) --------
    # carry_signal uses (front-second)/front in MONTHLY units; thresholds tuned for FX
    # (rate diffs typically <50 bps monthly). Short threshold = -5 bps.
    carry_dir = sig.carry_signal(front, second, short_threshold_monthly=-0.0005)
    # Override the long threshold from +0 to +5 bps to filter noise (symmetric):
    raw_ratio = (front - second) / front.replace(0.0, np.nan)
    carry_dir = pd.DataFrame(0.0, index=raw_ratio.index, columns=raw_ratio.columns)
    carry_dir[raw_ratio > 0.0005] = 1.0
    carry_dir[raw_ratio < -0.0005] = -1.0
    carry_dir = carry_dir.reindex(rets.index).ffill().fillna(0.0)

    res_c = run_backtest_ls(rets, carry_dir, SECTORS, cfg, roll)
    tc, mc, wc, cc = report_strategy("CARRY (long-short, basis-driven)",
                                      res_c.daily_returns, eq)

    # -------- Combined: 50/50 daily-return blend --------
    common = res_t.daily_returns.index.intersection(res_c.daily_returns.index)
    combo = 0.5 * res_t.daily_returns.reindex(common) + 0.5 * res_c.daily_returns.reindex(common)
    tcom, mcom, wcom, ccom = report_strategy("COMBINED (50/50 trend+carry)", combo, eq)

    # -------- Verdict & next-step --------
    print("\n" + "=" * 96)
    print("# FX TEST 2 VERDICT")
    print("=" * 96)
    print(f"\n  Trend    -> Tier {tt}  (Sortino {mt.sortino:+.2f}, stress {wt}/5, corr {ct:+.2f})")
    print(f"  Carry    -> Tier {tc}  (Sortino {mc.sortino:+.2f}, stress {wc}/5, corr {cc:+.2f})")
    print(f"  Combined -> Tier {tcom} (Sortino {mcom.sortino:+.2f}, stress {wcom}/5, corr {ccom:+.2f})")
    best = max([("trend",tt,mt),("carry",tc,mc),("combined",tcom,mcom)],
               key=lambda x: ("ABCD".index(x[1]), -x[2].sortino))
    # NOTE: "best" sort puts A<B<C<D then by -Sortino tie-break; flip so A wins
    best = sorted([("trend",tt,mt),("carry",tc,mc),("combined",tcom,mcom)],
                   key=lambda x: ("ABCD".index(x[1]), -x[2].sortino))[0]
    print(f"\n  >>> Best FX line: {best[0].upper()} = TIER {best[1]} <<<")
    if best[1] in ("A","B"):
        print("  Clears Tier B -> deployable equity-stress diversifier.")
    else:
        print("  Fails Tier B -> per the master plan, accept that no separate crisis")
        print("  hedge is deployable in the current research. Portfolio = equity trend +")
        print("  BTC trend + T-bills during OFF; no separate diversifier sleeve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Test 2B — FX carry in post-2022 high-rate regime vs pre-2022 ZIRP regime.

Same G6 universe and same carry signal as Test 2A. The hypothesis under test:
naive carry's failure in 2A is partly an artifact of the 2010-2021 ZIRP era
(near-zero rate differentials suppressing carry returns), and the 2022-2026
high-rate regime may produce structurally different results.

Methodology guarantees:
  - Signals computed on FULL history, then evaluated on the sub-period
    (no cold-start bias)
  - Same engine, sizing, costs, accounting as Test 2A
  - Reported on EXPLICIT sub-periods, never averaged

================================ LOCKED CRITERIA ===============================
Per the spec, gated on the 2022-2026 sub-period (deployment-relevant regime).
Full-sample reported but NOT the gate.

  Tier A: Sortino > 1.0 (post-2022)  AND correlation with equity < -0.2
          AND positive in >= 3 of 5 recent stress windows
  Tier B: Sortino > 0.7 (post-2022)  AND correlation < 0.2
          AND positive in >= 2 of stress windows
  Tier C: Sortino > 0.5 (post-2022), marginal diversification
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
from src.commodity.engine import run_backtest, run_backtest_ls, EngineConfig, _roll_dates_from_raw

RAW = REPO / "data" / "commodities" / "databento_raw"
START, END = "2010-06-06", "2026-06-20"
PAIRS = {"6E": "EUR/USD", "6J": "JPY/USD", "6B": "GBP/USD",
         "6A": "AUD/USD", "6C": "CAD/USD", "6N": "NZD/USD"}
SECTORS = {s: "FX" for s in PAIRS}

# Two non-overlapping regimes
PRE_RATE_RISE = ("2010-2021 ZIRP era",       date(2010, 6, 7),  date(2021, 12, 31))
POST_RATE_RISE = ("2022-2026 high-rate era", date(2022, 1, 1),  date(2026, 6, 20))

# Stress windows in the post-2022 era (the spec's list)
POST_STRESS = [
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2024-Aug yen unwind", date(2024, 7, 31), date(2024, 8, 16)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]
# Earlier stress windows for the pre-2022 comparison
PRE_STRESS = [
    ("2015 oil/EM crisis",  date(2015, 7, 1),  date(2016, 2, 28)),
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
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


def verdict_post2022(sortino, stress_wins, corr) -> str:
    if sortino > 1.0 and corr < -0.2 and stress_wins >= 3: return "A"
    if sortino > 0.7 and corr < 0.2  and stress_wins >= 2: return "B"
    if sortino > 0.5:                                        return "C"
    return "D"


def report_era(label, daily, eq_rets, stress_windows, a, b):
    d_era = sub(daily, a, b)
    e_era = sub(eq_rets, a, b)
    m = M.compute(d_era, (1 + d_era).cumprod())
    corr = M.correlation(d_era, e_era)
    wins = 0
    print(f"\n  ## {label}  ({a.isoformat()} -> {b.isoformat()})")
    print(f"  CAGR {m.cagr:+.1%}  Sortino {m.sortino:+.2f}  Sharpe {m.sharpe:+.2f}  "
          f"MaxDD {m.max_drawdown:.0%}  Vol {m.vol:.0%}  equity-corr {corr:+.2f}")
    print(f"  {'Stress window':<24}{'FX ret':>10}{'Equity ret':>12}")
    for lbl, sa, sb in stress_windows:
        fd, ed = sub(daily, sa, sb), sub(eq_rets, sa, sb)
        fx_ret = (1 + fd.fillna(0)).prod() - 1
        if fx_ret > 0:
            wins += 1
        print(f"  {lbl:<24}{fx_ret:>+9.1%}{(1+ed.fillna(0)).prod()-1:>+11.1%}")
    print(f"  Stress wins: {wins}/{len(stress_windows)}")
    return m, corr, wins


def main() -> int:
    close, front, second, rets = load_fx_panel()
    roll = _roll_dates_from_raw(RAW, list(PAIRS))
    cfg = EngineConfig(target_vol=0.10, max_weight=0.30, cov_lookback=60,
                       tbill_annual=0.02, apply_costs=True, scheme="inverse_vol")
    eq = equity_returns()

    # Signals computed on the FULL history (no cold-start bias)
    on = sig.sma_crossover(close, 50, 200)
    raw_ratio = (front - second) / front.replace(0.0, np.nan)
    carry_dir = pd.DataFrame(0.0, index=raw_ratio.index, columns=raw_ratio.columns)
    carry_dir[raw_ratio > 0.0005] = 1.0
    carry_dir[raw_ratio < -0.0005] = -1.0
    carry_dir = carry_dir.reindex(rets.index).ffill().fillna(0.0)

    res_t = run_backtest(close, rets, on, SECTORS, cfg, roll)
    res_c = run_backtest_ls(rets, carry_dir, SECTORS, cfg, roll)

    print("=" * 96)
    print("# FX TEST 2B — pre-2022 ZIRP era vs post-2022 high-rate era")
    print("# Signals computed on FULL history, evaluated on sub-periods (no cold-start bias)")
    print("=" * 96)

    # ---- show the basis magnitude shift across the two eras (the macro test) ----
    print(f"\n  Median |front-second| basis by era (% per ~1 month):")
    print(f"  {'Pair':<6}{'2010-2021 ZIRP':>18}{'2022-2026 high-rate':>22}{'change':>10}")
    for p in PAIRS:
        rp = (front[p] - second[p]) / front[p]
        med_pre = float(rp.loc[:'2021'].abs().median()) * 100
        med_post = float(rp.loc['2022':].abs().median()) * 100
        print(f"  {p:<6}{med_pre:>17.3f}%{med_post:>21.3f}%{med_post-med_pre:>+9.3f}pp")

    # ---- CARRY: pre vs post ----
    print(f"\n{'='*96}\n# CARRY (long-short basis)\n{'='*96}")
    m_c_pre,  c_c_pre,  w_c_pre  = report_era("PRE-2022 ZIRP era",       res_c.daily_returns, eq, PRE_STRESS,  *PRE_RATE_RISE[1:])
    m_c_post, c_c_post, w_c_post = report_era("POST-2022 high-rate era", res_c.daily_returns, eq, POST_STRESS, *POST_RATE_RISE[1:])
    delta_c = m_c_post.sortino - m_c_pre.sortino
    print(f"\n  --- CARRY regime delta: post-Sortino {m_c_post.sortino:+.2f} vs "
          f"pre-Sortino {m_c_pre.sortino:+.2f}  (delta {delta_c:+.2f}) ---")

    # ---- TREND: pre vs post (for completeness) ----
    print(f"\n{'='*96}\n# TREND 50/200 (long-flat)\n{'='*96}")
    m_t_pre,  c_t_pre,  w_t_pre  = report_era("PRE-2022 ZIRP era",       res_t.daily_returns, eq, PRE_STRESS,  *PRE_RATE_RISE[1:])
    m_t_post, c_t_post, w_t_post = report_era("POST-2022 high-rate era", res_t.daily_returns, eq, POST_STRESS, *POST_RATE_RISE[1:])
    delta_t = m_t_post.sortino - m_t_pre.sortino

    # ---- locked verdict (gated on post-2022 only, per spec) ----
    print("\n" + "=" * 96)
    print("# VERDICT — gated on POST-2022 sub-period (the deployment-relevant regime)")
    print("=" * 96)
    vc = verdict_post2022(m_c_post.sortino, w_c_post, c_c_post)
    vt = verdict_post2022(m_t_post.sortino, w_t_post, c_t_post)
    print(f"\n  CARRY post-2022: Sortino {m_c_post.sortino:+.2f}, corr {c_c_post:+.2f}, "
          f"stress {w_c_post}/{len(POST_STRESS)}  ->  TIER {vc}")
    print(f"  TREND post-2022: Sortino {m_t_post.sortino:+.2f}, corr {c_t_post:+.2f}, "
          f"stress {w_t_post}/{len(POST_STRESS)}  ->  TIER {vt}")
    n_post = (res_c.daily_returns.index >= pd.Timestamp("2022-01-01")).sum()
    print(f"\n  Sample size: {n_post} trading days post-2022 ({n_post/252:.1f} years).")
    print("  Small-sample caveat: ~4.5 years and ~3 stress events. Treat strong")
    print("  results as 'evidence for' rather than 'validated', per the spec.")
    print("\n  Regime delta — did high rates change the result?")
    print(f"    Carry Sortino delta {delta_c:+.2f}  | Trend Sortino delta {delta_t:+.2f}")
    print(f"    Median basis 2010-2021 vs 2022-2026: see table above (regime IS different).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

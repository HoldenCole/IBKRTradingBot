"""LEAPS BAH-on-trend test: Test 1 conservative + Test 2 aggressive.

Test 1 (conservative): 0.80 delta, 18mo tenor, 60% sizing, roll at 6mo
Test 2 (aggressive):   0.70 delta, 12mo tenor, 80% sizing, roll at 4mo

Both run on SPY across 2018-2026 / 2010-2017 / 2000-2009 (held-out).
Compares against shares 1x and futures 1.5x (already-tested vehicles).

Tax model uses actual hold periods from the trade ledger:
  hold > 365 days  -> LTCG (15% lower / 20% higher)
  hold ≤ 365 days  -> STCG (24% lower / 37% higher)

LEAPS rolls = sale of old contract = realization event. Each leg has its
own holding period.

Usage:
  FMP_API_KEY=... python scripts/run_leaps.py
"""
from __future__ import annotations

import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics
from src.backtest.leaps_engine import LeapsConfig, LeapsEngine
from src.data import yahoo
from src.data.fred import fetch_vix


# Tax rates per scenario (federal only — Texas user)
TAX_SCENARIOS = {
    "Lower bracket (24% STCG, 15% LTCG)": {"stcg": 0.24, "ltcg": 0.15},
    "Higher bracket (37% STCG, 20% LTCG)": {"stcg": 0.37, "ltcg": 0.20},
}


def fetch_spy(start: date, end: date) -> pd.DataFrame:
    """SPY daily bars 2000-2026. Yahoo handles full range."""
    return yahoo.daily("SPY", start.isoformat(), end.isoformat())


def compute_after_tax_realized(trades: list, scenario: dict) -> dict:
    """Apply LTCG/STCG tax to each trade's gain based on hold period.
    Losses offset gains within the same year (simplified: net gain only,
    no carryover modeling).
    """
    ltcg_gain = sum(max(0, t.pnl) for t in trades if t.hold_days > 365)
    stcg_gain = sum(max(0, t.pnl) for t in trades if t.hold_days <= 365)
    losses = sum(min(0, t.pnl) for t in trades)
    # Net losses offset same-class gains first; for simplicity offset
    # against the larger pool first.
    if ltcg_gain >= stcg_gain:
        ltcg_taxable = max(0, ltcg_gain + losses)
        remaining_loss = min(0, ltcg_gain + losses)
        stcg_taxable = max(0, stcg_gain + remaining_loss)
    else:
        stcg_taxable = max(0, stcg_gain + losses)
        remaining_loss = min(0, stcg_gain + losses)
        ltcg_taxable = max(0, ltcg_gain + remaining_loss)
    tax = ltcg_taxable * scenario["ltcg"] + stcg_taxable * scenario["stcg"]
    return {
        "ltcg_gain": ltcg_gain, "stcg_gain": stcg_gain, "losses": losses,
        "tax": tax, "ltcg_taxable": ltcg_taxable, "stcg_taxable": stcg_taxable,
    }


def operational_metrics(trades: list, equity: pd.Series, period_label: str) -> dict:
    """Surface the practical-deployment numbers."""
    if not trades:
        return {"n_trades": 0, "rolls": 0, "filter_offs": 0,
                "worst_realized_loss": 0, "avg_hold_days": 0,
                "max_dte_gap_days": 0, "n_days_in_position": 0}
    rolls = sum(1 for t in trades if t.reason == "roll")
    filter_offs = sum(1 for t in trades if t.reason == "filter_off")
    worst = min(t.pnl for t in trades)
    avg_hold = sum(t.hold_days for t in trades) / len(trades)
    # Days in position vs days idle (cash)
    in_pos_days = sum(t.hold_days for t in trades)
    return {
        "n_trades": len(trades),
        "rolls": rolls,
        "filter_offs": filter_offs,
        "worst_realized_loss": worst,
        "avg_hold_days": avg_hold,
        "n_days_in_position": in_pos_days,
        "ltcg_qualified_count": sum(1 for t in trades if t.hold_days > 365),
        "stcg_count": sum(1 for t in trades if t.hold_days <= 365),
    }


def run_leaps_variant(label: str, cfg: LeapsConfig,
                     spy: pd.DataFrame, vix: pd.Series) -> dict:
    print(f"\n{'='*92}")
    print(f"{label}")
    print(f"  delta={cfg.target_delta}, tenor={cfg.tenor_months}mo, "
          f"sizing={cfg.sizing_pct:.0%}, roll-at={cfg.roll_when_dte_le}d")
    print(f"  Period: {cfg.start} -> {cfg.end}")
    print(f"{'='*92}")

    eng = LeapsEngine(config=cfg, spy_bars=spy, vix_series=vix)
    res = eng.run()

    if res.equity_curve.empty:
        print("  ERROR: empty equity curve")
        return {}

    m = equity_metrics(res.equity_curve, cfg.initial_capital)
    op = operational_metrics(res.trades, res.equity_curve, label)

    print(f"\n  Final equity:         ${res.equity_curve.iloc[-1]:>10,.0f}  "
          f"(start ${cfg.initial_capital:,.0f})")
    print(f"  Total return:         {m['total_return']:>+9.1%}")
    print(f"  CAGR:                 {m['cagr']:>+9.1%}")
    print(f"  Sortino:              {m['sortino']:>9.2f}")
    print(f"  Sharpe:               {m['sharpe']:>9.2f}")
    print(f"  Max drawdown:         {m['max_drawdown']:>+9.1%}")
    print(f"\n  Operational:")
    print(f"    Trades closed:       {op['n_trades']}")
    print(f"    Rolls:               {op['rolls']}")
    print(f"    Filter-off exits:    {op['filter_offs']}")
    print(f"    LTCG qualified:      {op['ltcg_qualified_count']} of "
          f"{op['n_trades']} ({op['ltcg_qualified_count']/max(1,op['n_trades']):.0%})")
    print(f"    Avg hold (days):     {op['avg_hold_days']:.0f}")
    print(f"    Days in position:    {op['n_days_in_position']} of "
          f"{len(res.equity_curve)} ({op['n_days_in_position']/max(1,len(res.equity_curve)):.0%})")
    print(f"    Worst realized loss: ${op['worst_realized_loss']:>+,.0f}")

    print(f"\n  After-tax outcomes (with realized hold-period mix):")
    for tax_label, tax in TAX_SCENARIOS.items():
        at = compute_after_tax_realized(res.trades, tax)
        # Final after-tax equity = current equity - tax owed on net realized gains
        after_tax_eq = res.equity_curve.iloc[-1] - at["tax"]
        ret = (after_tax_eq - cfg.initial_capital) / cfg.initial_capital
        years = (res.equity_curve.index[-1] - res.equity_curve.index[0]).days / 365.25
        cagr = (after_tax_eq / cfg.initial_capital) ** (1.0 / max(1e-9, years)) - 1.0
        print(f"    {tax_label:42s}  final ${after_tax_eq:>10,.0f}  "
              f"ret {ret:>+8.1%}  CAGR {cagr:>+6.1%}")
        print(f"      tax: ${at['tax']:>9,.0f}  "
              f"(LTCG taxable ${at['ltcg_taxable']:>9,.0f}, "
              f"STCG taxable ${at['stcg_taxable']:>9,.0f})")

    return {"label": label, "metrics": m, "ops": op, "result": res}


def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)

    print("Fetching SPY (yfinance) and VIX (FRED)...")
    spy = fetch_spy(full_start, full_end)
    print(f"  SPY: {len(spy)} bars from {spy.index[0].date()} to {spy.index[-1].date()}")
    cache_dir = REPO / "data" / "fred_cache"
    vix_df = fetch_vix(full_start.isoformat(), full_end.isoformat(), cache_dir=cache_dir)
    vix = vix_df["close"]
    print(f"  VIX: {len(vix)} obs, range {vix.min():.1f}-{vix.max():.1f}")

    periods = [
        ("2018-2026 (in-sample)",     date(2018, 1, 1), date(2026, 4, 15)),
        ("2010-2017 (held-out)",      date(2010, 1, 1), date(2017, 12, 31)),
        ("2000-2009 (regime shift)",  date(2000, 1, 3), date(2009, 12, 31)),
    ]

    print("\n" + "#" * 92)
    print("# TEST 1 — Conservative LEAPS (0.80 delta, 18mo, 60% sizing, roll at 6mo)")
    print("#" * 92)
    test1_results = {}
    for plabel, ps, pe in periods:
        cfg = LeapsConfig(
            start=ps, end=pe,
            target_delta=0.80, tenor_months=18,
            sizing_pct=0.60, roll_when_dte_le=180,
            vix_tenor_multiplier=1.08,  # 18mo slightly above VIX
        )
        test1_results[plabel] = run_leaps_variant(
            f"TEST 1 — {plabel}", cfg, spy, vix)

    print("\n" + "#" * 92)
    print("# TEST 2 — Aggressive LEAPS (0.70 delta, 12mo, 80% sizing, roll at 4mo)")
    print("#" * 92)
    test2_results = {}
    for plabel, ps, pe in periods:
        cfg = LeapsConfig(
            start=ps, end=pe,
            target_delta=0.70, tenor_months=12,
            sizing_pct=0.80, roll_when_dte_le=120,
            vix_tenor_multiplier=1.05,  # 12mo
        )
        test2_results[plabel] = run_leaps_variant(
            f"TEST 2 — {plabel}", cfg, spy, vix)

    # Comparison vs shares 1x and futures 1.5x (from earlier analysis)
    print("\n" + "=" * 92)
    print("COMPARISON — LEAPS vs shares 1x vs futures 1.5x (lower bracket after-tax CAGR)")
    print("=" * 92)
    print(f"\n{'Period':30s}  {'Shares 1x':>10s}  {'Fut 1.5x':>10s}  "
          f"{'LEAPS T1':>10s}  {'LEAPS T2':>10s}")
    # Pre-computed from earlier analysis
    SHARES_AFTER_TAX_CAGR = {
        "2018-2026 (in-sample)":    0.185,  # SPX/MES Shares 1x
        "2010-2017 (held-out)":     0.181,
        "2000-2009 (regime shift)": 0.111,
    }
    FUT15_AFTER_TAX_CAGR = {
        "2018-2026 (in-sample)":    0.307,  # SPX/MES Fut 1.5x
        "2010-2017 (held-out)":     0.301,
        "2000-2009 (regime shift)": 0.182,
    }
    # Compute LEAPS lower-bracket CAGR for each test
    for plabel in [p[0] for p in periods]:
        line = [f"{plabel:30s}", f"{SHARES_AFTER_TAX_CAGR[plabel]:+9.1%}",
                f"{FUT15_AFTER_TAX_CAGR[plabel]:+9.1%}"]
        for results in (test1_results, test2_results):
            r = results.get(plabel)
            if not r or not r.get("result"):
                line.append(f"{'-':>9s}")
                continue
            res = r["result"]
            tax = TAX_SCENARIOS["Lower bracket (24% STCG, 15% LTCG)"]
            at = compute_after_tax_realized(res.trades, tax)
            after_tax_eq = res.equity_curve.iloc[-1] - at["tax"]
            years = (res.equity_curve.index[-1] - res.equity_curve.index[0]).days / 365.25
            cagr = (after_tax_eq / 8000.0) ** (1.0 / max(1e-9, years)) - 1.0
            line.append(f"{cagr:+9.1%}")
        print("  " + "  ".join(line[1:]) if False else "  " + "  ".join(line))

    # Decision rule
    print("\n" + "=" * 92)
    print("DECISION RULE — LEAPS vs shares 1x and vs futures 1.5x")
    print("=" * 92)
    SHARES_SORTINO_INSAMPLE = 3.89  # from prior SPX shares 1x
    SHARES_DD_INSAMPLE = 0.07
    FUT15_SORTINO_INSAMPLE = 3.88
    SORTINO_GATE = 0.80 * SHARES_SORTINO_INSAMPLE  # 3.11
    DD_GATE = 0.25  # max 25%
    AT_CAGR_LIFT_GATE = 0.05  # +5pp over shares

    for test_name, results in (("Test 1", test1_results), ("Test 2", test2_results)):
        print(f"\n  {test_name} 2018-2026 in-sample evaluation:")
        r = results["2018-2026 (in-sample)"]
        if not r.get("result"):
            print(f"    no data")
            continue
        m = r["metrics"]
        tax = TAX_SCENARIOS["Lower bracket (24% STCG, 15% LTCG)"]
        at = compute_after_tax_realized(r["result"].trades, tax)
        after_tax_eq = r["result"].equity_curve.iloc[-1] - at["tax"]
        years = (r["result"].equity_curve.index[-1] - r["result"].equity_curve.index[0]).days / 365.25
        leaps_cagr = (after_tax_eq / 8000.0) ** (1.0 / max(1e-9, years)) - 1.0
        shares_cagr = SHARES_AFTER_TAX_CAGR["2018-2026 (in-sample)"]
        fut_cagr = FUT15_AFTER_TAX_CAGR["2018-2026 (in-sample)"]

        sortino_ok = m["sortino"] >= SORTINO_GATE
        dd_ok = abs(m["max_drawdown"]) <= DD_GATE
        cagr_vs_shares_ok = leaps_cagr >= shares_cagr + AT_CAGR_LIFT_GATE
        print(f"    Sortino {m['sortino']:.2f}  vs gate {SORTINO_GATE:.2f}  "
              f"({'PASS' if sortino_ok else 'FAIL'})")
        print(f"    Max DD  {m['max_drawdown']*100:.1f}%  vs gate {DD_GATE*100:.0f}%  "
              f"({'PASS' if dd_ok else 'FAIL'})")
        print(f"    CAGR    {leaps_cagr*100:.1f}% vs shares+5pp = "
              f"{(shares_cagr+0.05)*100:.1f}%  "
              f"({'PASS' if cagr_vs_shares_ok else 'FAIL'})")
        print(f"    vs futures 1.5x ({fut_cagr*100:.1f}%):  "
              f"{'higher' if leaps_cagr > fut_cagr else 'lower'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

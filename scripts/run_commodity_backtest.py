"""M6/M7 — run all three signal variants through the engine and produce the
comparative analysis: headline metrics, sub-period breakdown, per-sector
attribution, cross-variant + indices-strategy correlation, tier classification.

Benchmark: equal-weight commodity buy-and-hold (vol-targeted-off, always long
all instruments, no signal) over the same window.

Outputs everything to stdout (captured into reports/commodity_trend/).
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
from src.commodity.engine import (
    run_backtest, EngineConfig, _roll_dates_from_raw,
)

RAW_DIR = REPO / "data" / "commodities" / "databento_raw"

# Section 1256 tax brackets (lower / higher), federal-only (Texas).
TAX_LOWER = (0.15, 0.24)   # (ltcg, stcg)
TAX_HIGHER = (0.20, 0.37)

# Locked tier criteria (REVISED per Q3 — calibrated to the asset class).
def classify_tier(full, subperiods, corr_indices, max_dd, n_sectors_robust,
                  lift_over_bah) -> str:
    """full: Sortino over full sample; subperiods: list of sub-period Sortinos;
    corr_indices: corr with indices strategy; max_dd: full-sample maxDD;
    n_sectors_robust: # sectors with positive contribution; lift_over_bah:
    Sortino lift over equal-weight commodity BAH."""
    sub_min = min(subperiods) if subperiods else -9
    # Tier A
    if (full > 1.0 and sub_min > 0.7 and corr_indices < 0.3 and max_dd < 0.25
            and n_sectors_robust >= 4 and lift_over_bah > 0.5):
        return "A"
    # Tier B
    if (full > 0.7 and sub_min > 0.5 and corr_indices < 0.4 and max_dd < 0.30
            and n_sectors_robust >= 3 and lift_over_bah > 0.3):
        return "B"
    # Tier C
    if full > 0.5:
        return "C"
    return "D"


SUBPERIODS = [
    ("2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 6, 20)),
    ("2013-2017 (held-out)", date(2013, 1, 1), date(2017, 12, 31)),
    # Note: 2010-2012 is warmup for momentum; full 2010-2017 not testable for V3.
]

EQUITY_BEARS = [
    ("2020 COVID", date(2020, 2, 19), date(2020, 4, 30)),
    ("2022 inflation", date(2022, 1, 3), date(2022, 10, 13)),
    ("2014-16 oil bust", date(2014, 6, 1), date(2016, 2, 28)),
]


def equal_weight_bah(returns: pd.DataFrame) -> pd.Series:
    """Equal-weight, always-long commodity basket daily returns (benchmark)."""
    return returns.mean(axis=1, skipna=True)


def sub(daily: pd.Series, s: date, e: date) -> pd.Series:
    idx = daily.index
    return daily.loc[(idx >= pd.Timestamp(s)) & (idx <= pd.Timestamp(e))]


def load_indices_returns() -> pd.Series | None:
    """Load the equity BAH-on-trend daily returns if available (for the
    <0.3 correlation diversifier test). Best-effort: reconstruct QQQ
    50/200 + T-bill OFF from yahoo. Returns None if unavailable."""
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
        print(f"  (indices returns unavailable: {e!r})")
        return None


def main() -> int:
    panel = cload.load()
    close, rets = panel.close, panel.returns()
    sectors = {s: cload.SECTOR[s] for s in panel.symbols}
    roll_dates = _roll_dates_from_raw(RAW_DIR, panel.symbols)
    masks = sig.compute_all(close, rets)

    print("=" * 100)
    print("# COMMODITY TREND RESEARCH — comparative backtest (Databento 2010-2026, 10 CME)")
    print("=" * 100)
    print(f"\nUniverse: {', '.join(panel.symbols)}")
    print(f"Sectors: Energy(CL,NG,HO,RB) Precious(GC,SI) Industrial(HG) Grains(ZC,ZS,ZW)")
    print("NOTE: 3 of 13 spec instruments (Brent, Sugar, Coffee) and the 2000-2009")
    print("      sub-period are pending Norgate backfill (M3, deferred).")

    cfg = EngineConfig(target_vol=0.15, max_weight=0.25, cov_lookback=60,
                       scheme="inverse_vol", tbill_annual=0.02, apply_costs=True)

    # Run each variant
    results = {}
    for key, mask in masks.items():
        results[key] = run_backtest(close, rets, mask, sectors, cfg, roll_dates)

    # Benchmark: equal-weight commodity BAH
    bah_daily = equal_weight_bah(rets)
    bah_eq = (1 + bah_daily.fillna(0)).cumprod()

    # Indices strategy (for diversifier corr)
    idx_rets = load_indices_returns()

    # ---------------- Headline ----------------
    print("\n" + "=" * 100)
    print("# Headline metrics (full sample, net of costs, target 15% vol, Sec-1256 higher bracket)")
    print("=" * 100)
    print(f"\n{'Variant':<26}{'CAGR':>7}{'Sharpe':>7}{'Sortino':>8}{'MaxDD':>7}"
          f"{'Vol':>6}{'AT-CAGR':>8}{'FinalEq':>9}")
    bah_m = M.compute(bah_daily.fillna(0), bah_eq, *TAX_HIGHER[::-1])
    # NOTE compute signature is (…, ltcg, stcg); TAX tuples are (ltcg,stcg)
    bah_m = M.compute(bah_daily.fillna(0), bah_eq, ltcg=TAX_HIGHER[0], stcg=TAX_HIGHER[1])
    print(f"{'EW commodity BAH':<26}{bah_m.cagr:>+6.1%}{bah_m.sharpe:>7.2f}"
          f"{bah_m.sortino:>8.2f}{bah_m.max_drawdown:>6.0%}{bah_m.vol:>6.0%}"
          f"{bah_m.after_tax_cagr:>+7.1%}{bah_m.final_equity:>9.2f}")
    variant_metrics = {}
    for key, res in results.items():
        m = M.compute(res.daily_returns, res.equity, ltcg=TAX_HIGHER[0], stcg=TAX_HIGHER[1])
        variant_metrics[key] = m
        print(f"{sig.SIGNAL_LABELS[key][:25]:<26}{m.cagr:>+6.1%}{m.sharpe:>7.2f}"
              f"{m.sortino:>8.2f}{m.max_drawdown:>6.0%}{m.vol:>6.0%}"
              f"{m.after_tax_cagr:>+7.1%}{m.final_equity:>9.2f}")

    # ---------------- Sub-periods ----------------
    print("\n" + "=" * 100)
    print("# Sub-period Sortino (net)")
    print("=" * 100)
    print(f"\n{'Variant':<26}", end="")
    for lbl, _, _ in SUBPERIODS:
        print(f"{lbl[:22]:>24}", end="")
    print()
    subperiod_sortinos = {k: [] for k in results}
    for key, res in results.items():
        print(f"{sig.SIGNAL_LABELS[key][:25]:<26}", end="")
        for lbl, s, e in SUBPERIODS:
            d = sub(res.daily_returns, s, e)
            mm = M.compute(d)
            subperiod_sortinos[key].append(mm.sortino)
            print(f"{f'{mm.sortino:.2f} ({mm.cagr:+.0%})':>24}", end="")
        print()

    # ---------------- Per-sector attribution ----------------
    print("\n" + "=" * 100)
    print("# Per-instrument P&L attribution (cumulative weight*return contribution)")
    print("=" * 100)
    print(f"\n{'Variant':<26}", end="")
    for s in panel.symbols:
        print(f"{s:>7}", end="")
    print()
    for key, res in results.items():
        print(f"{sig.SIGNAL_LABELS[key][:25]:<26}", end="")
        for s in panel.symbols:
            print(f"{res.per_instrument_pnl.get(s,0)*100:>+6.1f}", end=" ")
        print()

    # sectors robust = # sectors with positive total contribution
    def sectors_positive(res) -> int:
        bysec = {}
        for s in panel.symbols:
            bysec.setdefault(cload.SECTOR[s], 0.0)
            bysec[cload.SECTOR[s]] += res.per_instrument_pnl.get(s, 0.0)
        return sum(1 for v in bysec.values() if v > 0)

    # ---------------- Correlations ----------------
    print("\n" + "=" * 100)
    print("# Cross-variant + indices-strategy correlation (daily net returns)")
    print("=" * 100)
    rdf = pd.DataFrame({k: results[k].daily_returns for k in results})
    print("\nCross-variant:")
    print(rdf.corr().round(2).to_string())
    corr_idx = {}
    if idx_rets is not None:
        print("\nvs indices strategy (QQQ 50/200 + T-bill OFF):")
        for key in results:
            c = M.correlation(results[key].daily_returns, idx_rets)
            corr_idx[key] = c
            print(f"  {sig.SIGNAL_LABELS[key][:30]:<32} corr = {c:+.2f}")
    else:
        for key in results:
            corr_idx[key] = float("nan")

    # ---------------- Equity-bear behavior ----------------
    print("\n" + "=" * 100)
    print("# Behavior during equity bear regimes (commodity strat return over window)")
    print("=" * 100)
    print(f"\n{'Variant':<26}", end="")
    for lbl, _, _ in EQUITY_BEARS:
        print(f"{lbl:>18}", end="")
    print()
    for key, res in results.items():
        print(f"{sig.SIGNAL_LABELS[key][:25]:<26}", end="")
        for lbl, s, e in EQUITY_BEARS:
            d = sub(res.daily_returns, s, e)
            cum = (1 + d).prod() - 1
            print(f"{cum:>+17.1%}", end="")
        print()

    # ---------------- Diagnostics ----------------
    print("\n" + "=" * 100)
    print("# Diagnostics")
    print("=" * 100)
    for key, res in results.items():
        print(f"\n{sig.SIGNAL_LABELS[key]}:")
        print(f"  Avg instruments ON/day: {res.n_on.mean():.1f}  (median {res.n_on.median():.0f})")
        print(f"  Median gross long: {res.gross_long.median():.2f}  "
              f"P95: {res.gross_long.quantile(0.95):.2f}")
        print(f"  Annual turnover: {res.turnover.sum()/(len(res.turnover)/252):.1f}x")
        print(f"  Total cost drag: {res.cost_drag.sum()*100:.1f}% over full sample "
              f"({res.cost_drag.sum()/(len(res.cost_drag)/252)*100:.2f}%/yr)")

    # ---------------- Tier classification ----------------
    print("\n" + "=" * 100)
    print("# Tier classification (REVISED criteria per Q3)")
    print("=" * 100)
    print("  Tier A: Sortino>1.0 full, >0.7 each sub, corr<0.3, MaxDD<25%, >=4 sectors, lift>0.5")
    print("  Tier B: Sortino>0.7 full, >0.5 each sub, corr<0.4, MaxDD<30%, >=3 sectors, lift>0.3")
    print("  Tier C: Sortino>0.5 full.   Tier D: else.\n")
    for key, res in results.items():
        m = variant_metrics[key]
        lift = m.sortino - bah_m.sortino
        nsec = sectors_positive(res)
        tier = classify_tier(m.sortino, subperiod_sortinos[key],
                             corr_idx.get(key, 1.0) if not np.isnan(corr_idx.get(key, float('nan'))) else 0.0,
                             m.max_drawdown, nsec, lift)
        print(f"  {sig.SIGNAL_LABELS[key][:32]:<34} TIER {tier}  "
              f"(Sortino {m.sortino:.2f}, subMin {min(subperiod_sortinos[key]):.2f}, "
              f"corrIdx {corr_idx.get(key, float('nan')):+.2f}, MaxDD {m.max_drawdown:.0%}, "
              f"sectors+ {nsec}/5, lift {lift:+.2f})")

    print(f"\n  Benchmark EW-BAH Sortino: {bah_m.sortino:.2f} "
          f"(variants must beat this by the lift margin)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

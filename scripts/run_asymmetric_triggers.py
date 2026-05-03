"""Asymmetric trigger variants — slow exit, fast entry.

User's hypothesis: by the time SMA(50) crosses SMA(200) from below, most
of the recovery is already done. A faster entry filter (20/50 or 50/100
cross) would catch the bottom sooner without giving up the proven 50/200
exit safety.

Risk: bear-market rallies trigger fast-filter ON while slow is still OFF,
creating whipsaws. To handle this we use a regime-aware state machine:

  flat → fast filter triggers → "fast regime" (long, but fast filter active)
    "fast regime" → fast filter OFF → flat (cut bear-rally losses quickly)
    "fast regime" → slow filter ON → "slow regime" (slow has confirmed)
  "slow regime" → slow filter OFF → flat (the original 50/200 exit)

Variants:
  V1: SS_50_200   — symmetric 50/200 (baseline; current deployment)
  V2: AS_20_50    — asymmetric: 20/50 entry, 50/200 promoted exit
  V3: AS_50_100   — asymmetric: 50/100 entry, 50/200 promoted exit
  V4: AS_20_100   — asymmetric: 20/100 entry, 50/200 promoted exit
  V5: SS_50_100   — symmetric 50/100 (single filter throughout)

Reporting:
  - 26-year QQQ Conv 2 backtest (Sortino, CAGR, AT-CAGR, |DD|, transitions)
  - Liberation Day 2025: exit/entry dates, captured/missed return
  - Per-period results across the 98-year ^GSPC sample
  - Locked Tier-A criteria (already failed by symmetric — does asymmetric
    move the needle?)

Convention 2 throughout (realistic MOC).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m


def daily_tbill_factor(tbill_pct: pd.Series, idx: pd.Index) -> pd.Series:
    rate = tbill_pct.reindex(idx, method="ffill").bfill().fillna(0.0)
    return (1.0 + rate / 100.0) ** (1.0 / 252.0) - 1.0


def fast_filter_flag(close: pd.Series, fast: int, slow: int) -> pd.Series:
    f = close.rolling(fast, min_periods=fast).mean()
    s = close.rolling(slow, min_periods=slow).mean()
    return ((close > f) & (f > s)).fillna(False)


def slow_filter_flag(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    return fast_filter_flag(close, fast, slow)


def asymmetric_state_machine(
    close: pd.Series,
    entry_flag: pd.Series,
    slow_flag: pd.Series,
) -> pd.Series:
    """Returns a position series (True = long, False = flat) using the
    regime-aware state machine.

    States: 'flat', 'fast' (long, fast-entry regime), 'slow' (long, slow-
    confirmed regime).
    """
    state = "flat"
    pos = pd.Series(False, index=close.index)
    for i, ts in enumerate(close.index):
        e = bool(entry_flag.iloc[i])
        s = bool(slow_flag.iloc[i])
        if state == "flat":
            if e:
                state = "fast"
        elif state == "fast":
            if not e:
                state = "flat"
            elif s:
                state = "slow"
        elif state == "slow":
            if not s:
                state = "flat"
        pos.iloc[i] = state in ("fast", "slow")
    return pos


def symmetric_position(close: pd.Series, fast: int, slow: int) -> pd.Series:
    flag = fast_filter_flag(close, fast, slow)
    return flag


def equity_curve_conv2(close: pd.Series, position: pd.Series,
                       tbill_daily: pd.Series, start_capital: float = 8000.0
                       ) -> pd.Series:
    """Convention 2: position[t-1] determines whether we capture ret[t]."""
    rets = close.pct_change().fillna(0.0)
    shifted = position.shift(1).fillna(False).astype(bool)
    daily = rets.where(shifted, tbill_daily.reindex(close.index).fillna(0.0))
    return (1 + daily).cumprod() * start_capital


def transitions_per_year(position: pd.Series) -> float:
    flips = position.ne(position.shift(1)).sum()
    years = (position.index[-1] - position.index[0]).days / 365.25
    return float(flips / max(1e-9, years))


def find_state_changes(position: pd.Series, ps: date, pe: date
                       ) -> list[tuple[str, date, str]]:
    """Returns [(date, type)] where type is 'entry' or 'exit', within the
    [ps, pe] window."""
    changes = []
    prev = False
    for ts, p in position.items():
        d = ts.date() if hasattr(ts, "date") else ts
        if not (ps <= d <= pe):
            prev = bool(p)
            continue
        if bool(p) and not prev:
            changes.append(("entry", d, ""))
        elif prev and not bool(p):
            changes.append(("exit", d, ""))
        prev = bool(p)
    return changes


def main() -> int:
    print("Fetching QQQ + T-bill...")
    qqq_start, qqq_end = "2000-01-01", "2026-04-15"
    df = yahoo.daily("QQQ", qqq_start, qqq_end)
    cache = REPO / "data" / "fred_cache"
    tbill_pct = fetch_tbill_3m(qqq_start, qqq_end, cache_dir=cache)["close"]
    tbill_daily = daily_tbill_factor(tbill_pct, df.index)
    close = df["close"]

    # Build positions for each variant
    sma_50_200 = fast_filter_flag(close, 50, 200)
    sma_50_100 = fast_filter_flag(close, 50, 100)
    sma_20_50 = fast_filter_flag(close, 20, 50)
    sma_20_100 = fast_filter_flag(close, 20, 100)

    variants = {
        "V1: SS_50/200 (baseline)":
            symmetric_position(close, 50, 200),
        "V2: AS 20/50 entry → 50/200 promoted":
            asymmetric_state_machine(close, sma_20_50, sma_50_200),
        "V3: AS 50/100 entry → 50/200 promoted":
            asymmetric_state_machine(close, sma_50_100, sma_50_200),
        "V4: AS 20/100 entry → 50/200 promoted":
            asymmetric_state_machine(close, sma_20_100, sma_50_200),
        "V5: SS_50/100 (single filter)":
            symmetric_position(close, 50, 100),
    }

    # ===== Headline metrics =====
    print(f"\n{'='*100}")
    print("# Asymmetric trigger variants | QQQ 2000-2026 | Convention 2 (MOC)")
    print('='*100)

    print(f"\n{'Variant':40s}  {'Sortino':>7s}    {'CAGR':>6s}  {'AT CAGR':>7s}  "
          f"{'|DD|':>5s}  {'Trans/yr':>8s}  {'Final $':>10s}")

    bah_eq = (1 + close.pct_change().fillna(0.0)).cumprod() * 8000.0
    mb = equity_metrics(bah_eq, 8000.0)
    print(f"  {'(QQQ buy-and-hold)':40s}  {mb['sortino']:>5.2f}    "
          f"{mb['cagr']:>+5.1%}    {'n/a':>5s}     {abs(mb['max_drawdown']):>4.0%}    "
          f"{'  --':>6s}  ${mb['final_equity']:>8,.0f}")

    results = {}
    for label, pos in variants.items():
        eq = equity_curve_conv2(close, pos, tbill_daily, 8000.0)
        m = equity_metrics(eq, 8000.0)
        gain = m["final_equity"] - 8000.0
        at_final = 8000.0 + max(0, gain) * (1 - 0.24)
        years = (eq.index[-1] - eq.index[0]).days / 365.25
        at_cagr = (at_final / 8000.0) ** (1 / max(1e-9, years)) - 1.0 \
                  if at_final > 0 else -1.0
        tpy = transitions_per_year(pos)
        results[label] = {"metrics": m, "at_cagr": at_cagr, "tpy": tpy, "pos": pos}
        print(f"  {label:40s}  {m['sortino']:>5.2f}    "
              f"{m['cagr']:>+5.1%}    {at_cagr:>+5.1%}     "
              f"{abs(m['max_drawdown']):>4.0%}    "
              f"{tpy:>5.2f}/yr  ${m['final_equity']:>8,.0f}")

    # ===== Liberation Day specific =====
    print(f"\n{'='*100}")
    print("# Liberation Day 2025 — exit/entry dates per variant")
    print(f"# QQQ peak Feb 19 2025: $539 | Liberation Day Apr 2: $476 | Apr 8 low: $416 | Jul peak: $556")
    print('='*100)

    lib_window_start = date(2025, 1, 1)
    lib_window_end = date(2025, 9, 30)

    for label, info in results.items():
        pos = info["pos"]
        changes = find_state_changes(pos, lib_window_start, lib_window_end)
        print(f"\n  {label}")
        # Get QQQ price at each transition
        for change_type, d, _ in changes:
            ts = pd.Timestamp(d)
            if ts in close.index:
                px = float(close.loc[ts])
            else:
                idx = close.index.get_indexer([ts], method="nearest")[0]
                px = float(close.iloc[idx])
                ts = close.index[idx]
            print(f"    {change_type:>6s} {ts.date()} at QQQ ${px:.2f}")

    # ===== Locked criteria check =====
    print(f"\n{'='*100}")
    print("# Locked Tier-A criteria (vs V1 baseline)")
    print("# Sortino +0.3, AT-CAGR ≥ baseline, |DD| materially better, transitions ≤ 2x")
    print('='*100)

    base = results["V1: SS_50/200 (baseline)"]
    bs = base["metrics"]["sortino"]
    ba = base["at_cagr"]
    bd = abs(base["metrics"]["max_drawdown"])
    bt = base["tpy"]
    print(f"\n  Baseline V1: Sortino {bs:.2f}, AT-CAGR {ba:+.2%}, |DD| {bd:.0%}, "
          f"Trans/yr {bt:.2f}")

    print(f"\n  {'Variant':40s}  "
          f"{'ΔSortino':>9s}  {'ΔAT-CAGR':>9s}  {'ΔDD':>6s}  {'TPY≤2x?':>7s}  {'PASS?':>6s}")

    winners = []
    for label, info in results.items():
        if "baseline" in label:
            continue
        ds = info["metrics"]["sortino"] - bs
        da = info["at_cagr"] - ba
        dd = abs(info["metrics"]["max_drawdown"]) - bd
        tpy_ok = info["tpy"] <= 2 * bt
        c1 = ds >= 0.3
        c2 = da >= 0
        c3 = dd <= -0.005
        c4 = tpy_ok
        passed = c1 and c2 and c3 and c4
        if passed:
            winners.append(label)
        print(f"  {label:40s}  "
              f"{'✓' if c1 else '✗':1s} {ds:>+5.2f}  "
              f"{'✓' if c2 else '✗':1s} {da*100:>+5.1f}pp "
              f"{'✓' if c3 else '✗':1s} {dd*100:>+4.0f}pp "
              f"{'✓' if c4 else '✗':>5s}  "
              f"{'WIN' if passed else 'fail':>5s}")

    print(f"\n  Variants passing locked criteria: {winners or 'NONE'}")

    # ===== 98-year sanity check on the winning variant (or all if none) =====
    print(f"\n{'='*100}")
    print("# Long-history check on ^GSPC 1928-2026 (baseline V1 vs V2 only — savings test)")
    print('='*100)

    print("\nFetching ^GSPC + TB3MS...")
    gspc = yahoo.daily("^GSPC", "1928-12-30", "2026-04-14")
    from scripts.run_long_history import fetch_tb3ms
    tb3ms = fetch_tb3ms("1928-12-30", "2026-04-14", cache_dir=cache)
    tbill_long = daily_tbill_factor(tb3ms, gspc.index)
    gspc_close = gspc["close"]

    PERIODS = [
        ("1928-1949 Depression+WWII",  date(1928, 12, 30), date(1949, 12, 31)),
        ("1950-1965 Post-war bull",    date(1950, 1, 3),   date(1965, 12, 31)),
        ("1966-1982 Secular bear",     date(1966, 1, 3),   date(1982, 12, 31)),
        ("1983-1999 Disinflationary",  date(1983, 1, 3),   date(1999, 12, 31)),
        ("2000-2009 Dotcom+GFC",       date(2000, 1, 3),   date(2009, 12, 31)),
        ("2010-2017 Post-GFC",         date(2010, 1, 4),   date(2017, 12, 31)),
        ("2018-2026 Modern",           date(2018, 1, 2),   date(2026, 4, 14)),
        ("FULL 1928-2026",             date(1928, 12, 30), date(2026, 4, 14)),
    ]

    sma_50_200_g = fast_filter_flag(gspc_close, 50, 200)
    sma_20_50_g = fast_filter_flag(gspc_close, 20, 50)
    sma_20_100_g = fast_filter_flag(gspc_close, 20, 100)
    pos_v1_g = symmetric_position(gspc_close, 50, 200)
    pos_v2_g = asymmetric_state_machine(gspc_close, sma_20_50_g, sma_50_200_g)
    pos_v4_g = asymmetric_state_machine(gspc_close, sma_20_100_g, sma_50_200_g)

    print(f"\n{'Period':28s}  {'V1 (50/200)':>22s}  {'V2 (AS 20/50)':>22s}  "
          f"{'V4 (AS 20/100)':>22s}")
    print(f"{'':28s}  {'Sort  CAGR  |DD|':>22s}  {'Sort  CAGR  |DD|':>22s}  "
          f"{'Sort  CAGR  |DD|':>22s}")

    for plabel, ps, pe in PERIODS:
        idx = [d.date() if hasattr(d, "date") else d for d in gspc_close.index]
        mask = pd.Series([ps <= d <= pe for d in idx], index=gspc_close.index)
        sub_close = gspc_close.loc[mask]
        sub_tbill = tbill_long.loc[mask]
        if len(sub_close) < 250:
            continue
        sub_pos_v1 = pos_v1_g.loc[mask]
        sub_pos_v2 = pos_v2_g.loc[mask]
        sub_pos_v4 = pos_v4_g.loc[mask]
        eq1 = equity_curve_conv2(sub_close, sub_pos_v1, sub_tbill, 8000)
        eq2 = equity_curve_conv2(sub_close, sub_pos_v2, sub_tbill, 8000)
        eq4 = equity_curve_conv2(sub_close, sub_pos_v4, sub_tbill, 8000)
        m1 = equity_metrics(eq1, 8000)
        m2 = equity_metrics(eq2, 8000)
        m4 = equity_metrics(eq4, 8000)
        print(f"  {plabel:28s}  "
              f"{m1['sortino']:>4.2f} {m1['cagr']:>+5.1%} {abs(m1['max_drawdown']):>4.0%}  "
              f"{m2['sortino']:>4.2f} {m2['cagr']:>+5.1%} {abs(m2['max_drawdown']):>4.0%}  "
              f"{m4['sortino']:>4.2f} {m4['cagr']:>+5.1%} {abs(m4['max_drawdown']):>4.0%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

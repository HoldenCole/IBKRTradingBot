"""Pull + validate Databento daily bars for the 10 CME commodities (2010-2026).

First concrete milestone of the Hybrid data plan:
  - Databento (this script): 10 CME commodities, calendar-roll continuous,
    front (.c.0) AND second month (.c.1), 2010-06-06 -> present.
  - Norgate backfill (separate, later): 2000-2009 + ICE trio (BRN/SB/KC).

Validation performed here (data-quality gate before any backtest):
  1. Row count + date range per instrument
  2. Price-level sanity (is the latest close in a plausible range?)
  3. Roll-gap scan: count days with >7% close-to-close moves and check whether
     they cluster (raw continuous is unadjusted, so SOME gaps are expected —
     we just confirm the series is the unadjusted one we think it is)
  4. CL 2020 negative-price episode: confirm presence / inspect handling
  5. NaN / zero / non-monotonic-date checks

This does NOT back-adjust. Back-adjustment (Panama) is the next milestone and
uses the .c.1 series pulled here.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="INFO")

import numpy as np
import pandas as pd

from src.data.databento_loader import (
    DatabentoLoader, CME_COMMODITY_ROOTS, collapse_to_trade_date,
)

START = "2010-06-06"
END = "2026-06-20"

# Milestone 1 validates the front-month series. Second month (.c.1), needed
# only for Panama back-adjustment, is pulled in the back-adjustment milestone.
PULL_SECOND_MONTH = False

# Rough plausibility windows for the latest close (sanity only, not strict).
PLAUSIBLE_LATEST = {
    "CL": (40, 130), "NG": (1, 15), "HO": (1.0, 5.0), "RB": (1.0, 5.0),
    "GC": (1000, 4000), "SI": (10, 60), "HG": (2.0, 7.0),
    "ZC": (300, 900), "ZS": (700, 2000), "ZW": (350, 1300),
}


def validate(root: str, label: str, df0: pd.DataFrame, df1: pd.DataFrame) -> dict:
    res = {"root": root, "label": label}
    if df0.empty:
        res["status"] = "NO DATA"
        return res

    # Raw (as-fetched) vs trade-date-collapsed (Sunday sessions merged)
    res["n_raw"] = len(df0)
    res["n_sunday_raw"] = int((df0.index.dayofweek == 6).sum())
    df0 = collapse_to_trade_date(df0)
    res["n_bars"] = len(df0)
    res["n_sunday_post"] = int((df0.index.dayofweek == 6).sum())
    yrs = (df0.index[-1] - df0.index[0]).days / 365.25
    res["bars_per_year"] = len(df0) / yrs
    res["first"] = df0.index[0].date().isoformat()
    res["last"] = df0.index[-1].date().isoformat()
    res["last_close"] = float(df0["close"].iloc[-1])

    # Price plausibility
    lo, hi = PLAUSIBLE_LATEST.get(root, (None, None))
    if lo is not None:
        res["price_ok"] = bool(lo <= res["last_close"] <= hi)
    else:
        res["price_ok"] = None

    # Roll-gap / big-move scan (unadjusted series => expect some gaps)
    rets = df0["close"].pct_change().dropna()
    res["pct_days_gt7"] = float((rets.abs() > 0.07).mean() * 100)
    res["max_up"] = float(rets.max())
    res["max_dn"] = float(rets.min())

    # Data hygiene
    res["n_nan_close"] = int(df0["close"].isna().sum())
    res["n_zero_close"] = int((df0["close"] <= 0).sum())
    res["monotonic_dates"] = bool(df0.index.is_monotonic_increasing)
    res["n_dupe_dates"] = int(df0.index.duplicated().sum())

    # Second-month coverage (needed for back-adjustment)
    res["c1_bars"] = 0 if df1 is None or df1.empty else len(df1)

    # CL negative-price episode (Apr 2020)
    if root == "CL":
        apr = df0.loc["2020-04-15":"2020-04-30", "close"]
        res["cl_2020_min_close"] = float(apr.min()) if not apr.empty else None

    return res


def main() -> int:
    loader = DatabentoLoader()
    rows = []
    print(f"Pulling {len(CME_COMMODITY_ROOTS)} CME commodities (.c.0 + .c.1), {START} -> {END}\n")

    for root, label in CME_COMMODITY_ROOTS.items():
        df0 = loader.continuous(root, depth=0, start=START, end=END)
        df1 = (loader.continuous(root, depth=1, start=START, end=END)
               if PULL_SECOND_MONTH else pd.DataFrame())
        r = validate(root, label, df0, df1)
        rows.append(r)
        logger.info(f"{root:<3} {label:<18} bars={r.get('n_bars','-'):>5} "
                    f"last={r.get('last','-')} close={r.get('last_close',float('nan')):>8.2f}")

    # ---- Summary table ----
    print("\n" + "=" * 104)
    print("# Databento CME commodity pull — validation summary")
    print("=" * 104)
    print(f"\n{'Root':<5}{'Label':<18}{'Raw':>6}{'Bars':>6}{'b/yr':>6}{'Sun':>5}  "
          f"{'First':>10}  {'Last':>10}  {'LastClose':>10} {'Px?':>4} "
          f"{'>7%d':>6} {'MaxDn':>7} {'Mono':>5}")
    for r in rows:
        if r.get("status") == "NO DATA":
            print(f"{r['root']:<5}{r['label']:<18}  NO DATA")
            continue
        pxok = "ok" if r["price_ok"] else ("?" if r["price_ok"] is None else "BAD")
        print(f"{r['root']:<5}{r['label']:<18}{r['n_raw']:>6}{r['n_bars']:>6}"
              f"{r['bars_per_year']:>6.0f}{r['n_sunday_post']:>5}  "
              f"{r['first']:>10}  {r['last']:>10}  {r['last_close']:>10.2f} {pxok:>4} "
              f"{r['pct_days_gt7']:>5.1f}% {r['max_dn']:>+7.1%} "
              f"{'yes' if r['monotonic_dates'] else 'NO':>5}")

    # ---- Hygiene flags ----
    print("\n# Data-hygiene flags (want all zeros):")
    for r in rows:
        if r.get("status") == "NO DATA":
            continue
        flags = []
        if r["n_nan_close"]: flags.append(f"{r['n_nan_close']} NaN close")
        if r["n_zero_close"]: flags.append(f"{r['n_zero_close']} zero/neg close")
        if r["n_dupe_dates"]: flags.append(f"{r['n_dupe_dates']} dupe dates")
        if not r["monotonic_dates"]: flags.append("non-monotonic dates")
        if PULL_SECOND_MONTH and r["c1_bars"] == 0:
            flags.append("NO second-month series")
        print(f"  {r['root']:<5} {'OK' if not flags else '; '.join(flags)}")

    # ---- CL 2020 episode ----
    cl = next((r for r in rows if r["root"] == "CL"), None)
    if cl and "cl_2020_min_close" in cl:
        print(f"\n# CL 2020 episode: min close 15-30 Apr 2020 = {cl['cl_2020_min_close']}")
        print("  (Negative => Databento preserves the real negative-price print;")
        print("   back-adjustment step must handle the sign change per Q2.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

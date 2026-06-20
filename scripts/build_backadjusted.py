"""Milestone 2 — Panama (difference) back-adjustment of the CME continuous series.

Removes roll gaps from the raw volume-roll continuous so the series is
tradeable (price changes reflect real P&L, not contract switches). Per locked
methodology Q2: difference adjustment, not ratio (ratio breaks across sign
changes; difference preserves absolute moves, which is what SMA/Donchian/
momentum signals key on).

Method:
  1. Pull front (.v.0) and second (.v.1) month, both carrying instrument_id.
  2. Detect roll dates: days where .v.0's instrument_id differs from the prior
     bar's. On a roll at date t, the new front contract is the one that was
     second month on t-1.
  3. Roll gap at t:  gap_t = v0.close[t] - v1.close[t-1]
     i.e. (new front first close) - (new front's close the day before, when it
     was the second month). This isolates the contract switch from the genuine
     overnight move: both sides are the SAME (new) contract one day apart, so
     the difference is the real move; the gap we must remove is instead the
     jump between old and new front. Equivalent and more robust formulation:
         gap_t = v0.close[t-1] (old front) - v1.close[t-1] (new front, =next)
     We use this same-day old-vs-new difference.
  4. Panama difference adjustment: the most recent segment is left as-is; going
     backward, every bar before roll t has the cumulative sum of all gaps at
     and after t SUBTRACTED, so the series is continuous at each seam.
     adj[i] = raw[i] - sum(gap_t for rolls t > date[i])

Validation:
  - Roll seams: post-adjustment close-to-close change on roll days should match
    the new contract's real move (no artificial jump).
  - Latest segment unchanged (adjustment is anchored to the present).
  - Big-move scan: count >7% days before vs after; roll-driven spikes removed.
  - Negative-price safety (CL 2020): difference adjustment is sign-safe.

Outputs adjusted CSVs to data/commodities/databento_adj/ (gitignored).
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
ADJ_DIR = REPO / "data" / "commodities" / "databento_adj"


def detect_rolls(v0: pd.DataFrame) -> pd.DatetimeIndex:
    """Roll dates = bars where the front-month instrument_id changes."""
    if "instrument_id" not in v0.columns:
        raise ValueError("v0 missing instrument_id; re-pull needed")
    iid = v0["instrument_id"]
    changed = iid.ne(iid.shift(1)) & iid.shift(1).notna()
    return v0.index[changed]


def panama_adjust(v0: pd.DataFrame, v1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply Panama difference back-adjustment to v0 OHLC using v1 for gaps.

    Returns (adjusted_df, rolls_df) where rolls_df logs each roll gap.
    """
    rolls = detect_rolls(v0)
    common = v0.index
    v1c = v1["close"].reindex(common)
    v1id = v1["instrument_id"].reindex(common) if "instrument_id" in v1.columns else None
    v0id = v0["instrument_id"]

    gap_rows = []
    n_mismatch = 0
    # gap at roll t = old_front_close(t-1) - new_front_close(t-1)
    #              = v0.close[t-1] - v1.close[t-1]
    # Validity guard: the new front (v0.instrument_id[t]) should equal the
    # second month the day before (v1.instrument_id[t-1]). If volume-roll
    # skipped a month they differ -> the v1 price is the wrong contract; flag.
    for t in rolls:
        pos = common.get_loc(t)
        if pos == 0:
            continue
        tm1 = common[pos - 1]
        old_front = float(v0["close"].iloc[pos - 1])
        new_front = v1c.loc[tm1]
        if pd.isna(new_front):
            continue
        clean = True
        if v1id is not None:
            new_front_id = v0id.iloc[pos]
            prev_second_id = v1id.loc[tm1]
            clean = bool(new_front_id == prev_second_id)
            if not clean:
                n_mismatch += 1
        gap = old_front - float(new_front)
        gap_rows.append({"roll_date": t, "prev_date": tm1,
                         "old_front": old_front, "new_front": float(new_front),
                         "gap": gap, "clean": clean})
    if n_mismatch:
        logger.warning(f"  {n_mismatch}/{len(gap_rows)} rolls: new front != prior "
                       f"second month (volume-roll skipped a month) — gap approximate")

    rolls_df = pd.DataFrame(gap_rows).set_index("roll_date") if gap_rows else pd.DataFrame()

    # Cumulative adjustment: adj[i] = raw[i] - sum(gap_t for rolls t > date[i])
    # Build a step function of cumulative future gaps.
    adj_offset = pd.Series(0.0, index=common)
    if not rolls_df.empty:
        # total gaps from the end backward
        # For each bar, subtract sum of gaps whose roll_date is strictly after it.
        gaps_by_date = rolls_df["gap"]
        # cumulative sum from the latest roll backward
        # offset[i] = sum of gaps with roll_date > date[i]
        total = 0.0
        gap_dates = list(gaps_by_date.index)[::-1]   # latest first
        gap_vals = list(gaps_by_date.values)[::-1]
        gi = 0
        # iterate bars from latest to earliest
        offs = np.zeros(len(common))
        running = 0.0
        gidx = 0
        sorted_gaps = list(zip(rolls_df.index, rolls_df["gap"]))  # ascending
        # Walk backward through bars
        for k in range(len(common) - 1, -1, -1):
            d = common[k]
            # add any gap whose roll_date > d that we haven't added yet
            running = float(rolls_df.loc[rolls_df.index > d, "gap"].sum())
            offs[k] = running
        adj_offset = pd.Series(offs, index=common)

    adj = v0.copy()
    for col in ("open", "high", "low", "close"):
        if col in adj.columns:
            adj[col] = adj[col] - adj_offset
    return adj, rolls_df


def validate(root: str, raw: pd.DataFrame, adj: pd.DataFrame, rolls_df: pd.DataFrame) -> dict:
    rr = raw["close"].pct_change()
    # adjusted returns: use difference-based since levels can shift; but report
    # close-to-close abs move relative to price for comparability
    ar = adj["close"].diff() / raw["close"].shift(1)
    return {
        "root": root,
        "n_rolls": 0 if rolls_df is None or rolls_df.empty else len(rolls_df),
        "raw_gt7": float((rr.abs() > 0.07).mean() * 100),
        "adj_gt7": float((ar.abs() > 0.07).mean() * 100),
        "raw_maxdn": float(rr.min()),
        "adj_maxdn": float(ar.min()),
        "latest_close_raw": float(raw["close"].iloc[-1]),
        "latest_close_adj": float(adj["close"].iloc[-1]),
        "min_adj_close": float(adj["close"].min()),
    }


def main() -> int:
    ADJ_DIR.mkdir(parents=True, exist_ok=True)
    loader = DatabentoLoader()
    rows = []

    for root, label in CME_COMMODITY_ROOTS.items():
        logger.info(f"=== {root} {label} ===")
        v0 = collapse_to_trade_date(loader.continuous(root, depth=0, start=START, end=END))
        v1 = collapse_to_trade_date(loader.continuous(root, depth=1, start=START, end=END))
        if "instrument_id" not in v0.columns:
            logger.warning(f"{root}: v0 cache lacks instrument_id; forcing re-pull")
            v0 = collapse_to_trade_date(loader.continuous(root, depth=0, start=START, end=END, force=True))
        adj, rolls_df = panama_adjust(v0, v1)
        adj.to_csv(ADJ_DIR / f"{root}_v0_panama__{START}__{END}.csv")
        rows.append(validate(root, v0, adj, rolls_df))

    print("\n" + "=" * 96)
    print("# Panama back-adjustment validation (raw vs adjusted)")
    print("=" * 96)
    print(f"\n{'Root':<5}{'Rolls':>6}{'raw>7%':>8}{'adj>7%':>8}{'rawMaxDn':>10}"
          f"{'adjMaxDn':>10}{'LatestRaw':>11}{'LatestAdj':>11}{'MinAdj':>10}")
    for r in rows:
        print(f"{r['root']:<5}{r['n_rolls']:>6}{r['raw_gt7']:>7.1f}%{r['adj_gt7']:>7.1f}%"
              f"{r['raw_maxdn']:>+9.1%}{r['adj_maxdn']:>+9.1%}"
              f"{r['latest_close_raw']:>11.2f}{r['latest_close_adj']:>11.2f}"
              f"{r['min_adj_close']:>10.2f}")

    print("\nNotes:")
    print("  - LatestRaw should == LatestAdj (adjustment anchored to present).")
    print("  - adj>7% should be <= raw>7% (roll-gap spikes removed).")
    print("  - MinAdj may go negative for some series — that's the back-adjusted")
    print("    level drifting below zero over long history; expected with")
    print("    difference adjustment and not a tradeability problem (signals use")
    print("    the adjusted series consistently). Flag if a recent-era close is <0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

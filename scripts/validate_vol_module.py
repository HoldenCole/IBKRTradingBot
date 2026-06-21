"""M4 validation — run realized vol + full-cov vol-targeting on the actual
10-CME panel. Reports realized vs target portfolio vol for several
all-instruments-on scenarios so we can see the formula behaves sensibly on
historical correlation regimes (energy 2014-16 sell-off, COVID, 2022 inflation).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.commodity import loader as cload
from src.commodity.vol import realized_vol, rolling_cov, vol_target_weights


def main() -> int:
    panel = cload.load()
    print("=== Loaded panel ===")
    print(panel.meta[["label", "sector", "source", "first_bar", "last_bar", "n_bars"]].to_string())

    rets = panel.returns()
    print(f"\n=== Returns shape: {rets.shape} ===")

    # Per-instrument realized vol — recent
    rv = realized_vol(rets, lookback=60)
    print("\n=== Per-instrument annualized realized vol (last 5 dates) ===")
    print((rv.tail(5) * 100).round(1).to_string())

    # Rolling covariance
    cov_hist = rolling_cov(rets, lookback=60)
    print(f"\n=== Rolling covariance: {len(cov_hist)} matrices over panel history ===")

    # Vol-targeting: ON = all instruments, every day, target 15% vol, cap 25%
    # Run BOTH schemes for explicit comparison.
    dates_sorted = sorted(cov_hist.keys())
    on_full = pd.Series(True, index=panel.symbols)
    scheme = "inverse_vol"   # default (matches spec wording)
    print(f"\n=== Running vol-targeting with scheme: {scheme!r} ===")

    weights_rows = []
    realized_pv_rows = []
    n_on_rows = []
    n_capped_rows = []
    for d in dates_sorted:
        cov = cov_hist[d]
        on = on_full.reindex(cov.columns).fillna(False)
        w = vol_target_weights(cov, on, target_vol=0.15, max_weight=0.25,
                               scheme=scheme)
        weights_rows.append((d, w))
        pv = float(np.sqrt(w.values @ cov.values @ w.values))
        realized_pv_rows.append((d, pv))
        n_on_rows.append((d, int(on.sum())))
        n_capped_rows.append((d, int((w >= 0.249).sum())))

    weights_df = pd.DataFrame({d: w for d, w in weights_rows}).T.fillna(0)
    pv_series = pd.Series({d: v for d, v in realized_pv_rows})
    nc_series = pd.Series({d: v for d, v in n_capped_rows})

    print("\n=== Realized portfolio vol (all-on, target 15%, cap 25%) ===")
    print(f"  Median: {pv_series.median()*100:.2f}%")
    print(f"  P95:    {pv_series.quantile(0.95)*100:.2f}%")
    print(f"  Min:    {pv_series.min()*100:.2f}%")
    print(f"  Max:    {pv_series.max()*100:.2f}%")
    print(f"  Fraction of days below target (cap-driven undershoot): "
          f"{(pv_series < 0.149).mean()*100:.1f}%")
    print(f"  Fraction of days exceeding target: "
          f"{(pv_series > 0.151).mean()*100:.1f}%")

    print("\n=== Weight cap activations ===")
    print(f"  Median # capped instruments per day: {nc_series.median():.1f}")
    print(f"  Max # capped instruments any day:    {nc_series.max()}")
    cap_days = (nc_series > 0).mean() * 100
    print(f"  Fraction of days with ANY cap binding: {cap_days:.1f}%")

    # Sanity: what's the gross book size (sum of weights) at typical dates?
    gross = weights_df.sum(axis=1)
    print(f"\n=== Gross book size (sum of weights) ===")
    print(f"  Median: {gross.median():.2f}  (1.0 = fully invested at target vol)")
    print(f"  P5:     {gross.quantile(0.05):.2f}")
    print(f"  P95:    {gross.quantile(0.95):.2f}")

    # Sample regime snapshots — show weights during three known regimes
    print("\n=== Weight snapshots at three regime dates ===")
    for d in (pd.Timestamp("2015-06-30"), pd.Timestamp("2020-04-30"),
              pd.Timestamp("2022-06-30")):
        if d in weights_df.index:
            row = weights_df.loc[d]
            row = (row[row > 0] * 100).round(1)
            print(f"\n  {d.date()}: target_pv={pv_series.loc[d]*100:.2f}%, "
                  f"capped={nc_series.loc[d]}, weights%:")
            print("    " + ", ".join(f"{s}={v:.1f}" for s, v in row.items()))

    # Ablation snapshot: equal-weight on the most recent date for comparison
    print("\n=== Ablation: equal-weight scheme on most recent cov ===")
    d_last = dates_sorted[-1]
    cov_last = cov_hist[d_last]
    on_last = on_full.reindex(cov_last.columns).fillna(False)
    w_eq = vol_target_weights(cov_last, on_last, target_vol=0.15,
                              max_weight=0.25, scheme="equal_weight")
    pv_eq = float(np.sqrt(w_eq.values @ cov_last.values @ w_eq.values))
    print(f"  {d_last.date()}: equal_weight pv={pv_eq*100:.2f}%, "
          f"weights%: " + ", ".join(f"{s}={v*100:.1f}" for s, v in w_eq.items() if v > 0))
    w_iv = vol_target_weights(cov_last, on_last, target_vol=0.15,
                              max_weight=0.25, scheme="inverse_vol")
    pv_iv = float(np.sqrt(w_iv.values @ cov_last.values @ w_iv.values))
    print(f"  {d_last.date()}: inverse_vol pv={pv_iv*100:.2f}%, "
          f"weights%: " + ", ".join(f"{s}={v*100:.1f}" for s, v in w_iv.items() if v > 0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

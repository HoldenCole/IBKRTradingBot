"""NQ trend margin-sensitivity test — robustness check on the futures-aware
accounting model used in the vehicle equivalence test.

Concern (legitimate post-hoc methodology concern): the futures-aware
adjustment was identified AFTER the naive test failed the locked Calmar
criterion. The adjustment is correct in principle (futures don't tie up
100% of capital) but the timing makes verification appropriate.

This test re-runs NQ 50/200 trend at three margin scenarios:
  - 94% T-bill credit (current optimistic case, normal-vol margin ~6%)
  - 90% T-bill credit (moderate, ~10% margin)
  - 86% T-bill credit (historical elevated, ~14% margin, similar to
                       March 2020 when CME raised margins materially)

Compare each scenario's Calmar to QQQ trend's Calmar 0.55. Locked tolerance
is 0.10 — if all three pass, the result is robust; if only optimistic
passes, MNQ migration plan needs conservative sizing.

LOCKED: no further methodology adjustments after seeing these results.
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
from src.crypto import metrics as CM


SUBPERIODS = [
    ("2018-2026 (in-sample)", date(2018, 1, 1),  date(2026, 6, 20)),
    ("2010-2017 (held-out)",  date(2010, 6, 6),  date(2017, 12, 31)),
]


def fetch_qqq() -> pd.Series:
    import yfinance as yf
    df = yf.download("QQQ", start="2010-06-06", end="2026-06-20",
                     progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float)


def load_nq() -> tuple[pd.Series, pd.Series]:
    loader = DatabentoLoader()
    v0 = collapse_to_trade_date(loader.continuous("NQ", depth=0,
                                start="2010-06-06", end="2026-06-20"))
    v1 = collapse_to_trade_date(loader.continuous("NQ", depth=1,
                                start="2010-06-06", end="2026-06-20"))
    return panama_adjust(v0, v1)["close"], v0["close"]


def trend_signal(close: pd.Series) -> pd.Series:
    smaf = close.rolling(50, min_periods=50).mean()
    smas = close.rolling(200, min_periods=200).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def run_nq_futures(adj, front, sig, tbill_credit_fraction: float,
                   tbill_annual=0.03, transition_bps=5.0):
    """NQ trend with explicit T-bill credit on the unencumbered margin.

    tbill_credit_fraction = fraction of capital earning T-bill on ON days.
    On OFF days, 100% of capital earns T-bill (position is closed; no margin).
    """
    common = adj.index.intersection(front.index).intersection(sig.index)
    adj_, front_, sig_ = adj.loc[common], front.loc[common], sig.loc[common]

    fut_pnl = (adj_.diff() / front_.shift(1)).fillna(0.0)
    sig_shifted = sig_.shift(1).fillna(False).astype(bool)
    tbill_daily = (1.0 + tbill_annual) ** (1.0 / 252.0) - 1.0

    # ON: futures P&L + T-bill on unencumbered fraction
    # OFF: full T-bill on the whole capital
    daily = pd.Series(0.0, index=common)
    daily[sig_shifted] = fut_pnl[sig_shifted] + tbill_credit_fraction * tbill_daily
    daily[~sig_shifted] = tbill_daily

    flips = sig_shifted.ne(sig_shifted.shift(1)).fillna(False)
    daily = daily - flips.astype(float) * (transition_bps / 1e4)

    equity = (1 + daily).cumprod()
    return daily, equity


def run_qqq(close, sig, tbill_annual=0.03, transition_bps=5.0):
    common = close.index.intersection(sig.index)
    c_, s_ = close.loc[common], sig.loc[common]
    rets = c_.pct_change().fillna(0.0)
    sig_shifted = s_.shift(1).fillna(False).astype(bool)
    tbill_daily = (1.0 + tbill_annual) ** (1.0 / 252.0) - 1.0
    daily = rets.where(sig_shifted, tbill_daily)
    flips = sig_shifted.ne(sig_shifted.shift(1)).fillna(False)
    daily = daily - flips.astype(float) * (transition_bps / 1e4)
    return daily, (1 + daily).cumprod()


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def main() -> int:
    print("Loading data...")
    nq_adj, nq_front = load_nq()
    qqq = fetch_qqq().dropna()
    common = nq_adj.index.intersection(qqq.index)
    nq_adj, nq_front, qqq = nq_adj.loc[common], nq_front.loc[common], qqq.loc[common]
    print(f"  {len(common)} bars, {common[0].date()} -> {common[-1].date()}\n")

    nq_sig = trend_signal(nq_adj)
    qqq_sig = trend_signal(qqq)

    # QQQ baseline (reference)
    qqq_daily, qqq_eq = run_qqq(qqq, qqq_sig)
    qqq_m = CM.compute(qqq_daily, qqq_eq)

    print("=" * 96)
    print("# MARGIN SENSITIVITY — NQ trend Calmar across margin scenarios")
    print(f"# Reference: QQQ trend Calmar = {qqq_m.calmar:.2f}  (locked tolerance: gap < 0.10)")
    print("=" * 96)

    scenarios = [
        (1.00, "100% credit (theoretical, no margin)"),
        (0.94, " 94% credit (current normal-vol, ~6% margin)"),
        (0.90, " 90% credit (moderate, ~10% margin)"),
        (0.86, " 86% credit (historical elevated, ~14% margin, like Mar 2020)"),
        (0.80, " 80% credit (stress, ~20% margin — extreme stress test)"),
        (0.00, "  0% credit (naive — buggy baseline for context)"),
    ]

    print(f"\n  {'Scenario':<46}{'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Gap':>8}{'Pass?':>8}")
    results = []
    for credit, label in scenarios:
        daily, eq = run_nq_futures(nq_adj, nq_front, nq_sig, credit)
        m = CM.compute(daily, eq)
        gap = abs(m.calmar - qqq_m.calmar)
        passes = gap <= 0.10
        results.append((credit, m, gap, passes))
        print(f"  {label:<46}{m.cagr:>+7.0%}{m.max_drawdown:>8.0%}"
              f"{m.calmar:>8.2f}{gap:>+8.2f}{'PASS' if passes else 'FAIL':>8s}")

    # Sub-period detail for the 86% case (the conservative scenario)
    print(f"\n## Sub-period detail under the 3 realistic margin scenarios")
    print(f"  {'Scenario':<26}{'2018-2026 Sort':>16}{'2010-2017 Sort':>16}")
    for credit, label in [(0.94, "94% credit"), (0.90, "90% credit"), (0.86, "86% credit")]:
        daily, _ = run_nq_futures(nq_adj, nq_front, nq_sig, credit)
        s18 = CM.compute(sub(daily, *SUBPERIODS[0][1:])).sortino
        s10 = CM.compute(sub(daily, *SUBPERIODS[1][1:])).sortino
        print(f"  {label:<26}{s18:>+15.2f}{s10:>+15.2f}")

    # Headline verdict
    print("\n" + "=" * 96)
    print("# VERDICT — margin-sensitivity robustness")
    print("=" * 96)
    realistic = [r for r in results if r[0] in (0.94, 0.90, 0.86)]
    all_pass = all(r[3] for r in realistic)
    n_pass = sum(1 for r in realistic if r[3])
    print(f"\n  Realistic scenarios (94/90/86 credit): {n_pass}/3 PASS locked 0.10 tolerance")
    if all_pass:
        print("\n  >>> ROBUST: vehicle equivalence holds across all realistic margin regimes <<<")
        print("     MNQ migration plan validated without conservative sizing adjustment.")
    elif n_pass >= 1:
        worst_pass = max((r[0] for r in realistic if r[3]), default=None)
        print(f"\n  >>> PARTIAL: passes at >= {worst_pass*100:.0f}% credit only <<<")
        print("     MNQ migration plan should be sized conservatively for elevated-margin regimes.")
    else:
        print("\n  >>> FAILS at all realistic margin levels <<<")
        print("     Vehicle equivalence is fragile to margin variation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

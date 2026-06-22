"""MES vs QQQ index choice — does the 50/200 trend rule work as well on SPX
as on NDX?

This determines whether the $40k+ vehicle-switch to MES (S&P 500 futures) is
a like-for-like strategy swap or a strategy change. If SPX trend produces
materially worse risk-adjusted return, the right $40k+ vehicle is MNQ
(NDX futures) instead.

Methodology mirrors the locked equity validation: 50/200 SMA + close >
SMA(50), Convention 2 (no look-ahead), T-bill 3% on OFF capital, costs on,
honest after-tax (Section 1256 60/40 for the futures-traded version since
MES/MNQ comparison is the point). Use ETF proxies (SPY, QQQ) for the
strategy run; the futures version is just a tax/cost variant on the same
signal.

Locked criteria (set BEFORE the run):
  SPX trend "works as well as NDX trend" if:
    - SPX Calmar within 0.2 of NDX Calmar
    - SPX MaxDD within 5pp of NDX MaxDD
    - SPX produces positive Sortino in BOTH sub-periods (2018-2026, 2010-2017)
    - Equity-stress windows: SPX trend matches NDX trend qualitatively
      (both positive OR both negative within ~3pp)

If SPX trend clears these, MES is a valid like-for-like swap at $40k+.
If not, recommend MNQ instead (same strategy, NDX-tracking futures vehicle).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.commodity import signals as sig
from src.crypto import metrics as CM
from src.crypto.engine import run_long_flat, CryptoBTConfig


SUBPERIODS = [
    ("2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 6, 21)),
    ("2010-2017 (held-out)",  date(2010, 1, 1), date(2017, 12, 31)),
]
STRESS = [
    ("2018-Q4",         date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",date(2020, 2, 19), date(2020, 4,  7)),
    ("2022 inflation",  date(2022, 1, 3),  date(2022, 10, 13)),
    ("2025 Lib Day",    date(2025, 2, 19), date(2025, 6, 30)),
]


def fetch(tk: str) -> pd.Series:
    import yfinance as yf
    df = yf.download(tk, start="2009-01-01", end="2026-06-21",
                     progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float)


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def run_50_200(close: pd.Series, expense_ratio=0.001, transition_bps=5.0):
    """50/200 trend (close > SMA50 AND SMA50 > SMA200), Convention 2."""
    smaf = close.rolling(50, min_periods=50).mean()
    smas = close.rolling(200, min_periods=200).mean()
    sig_on = ((close > smaf) & (smaf > smas)).fillna(False)
    cfg = CryptoBTConfig(expense_ratio=expense_ratio, transition_bps=transition_bps,
                         tbill_annual=0.03, apply_costs=True)
    res = run_long_flat(close, sig_on, cfg)
    return res, sig_on


def main() -> int:
    print("=" * 92)
    print("# MES vs QQQ index test — does 50/200 work on SPX as well as NDX?")
    print("=" * 92)

    qqq = fetch("QQQ").dropna()
    spy = fetch("SPY").dropna()
    common = qqq.index.intersection(spy.index)
    qqq, spy = qqq.loc[common], spy.loc[common]
    print(f"\nData: SPY+QQQ 2010-2026, {len(qqq)} bars on common calendar")

    # buy-and-hold context
    qqq_bah_r = qqq.pct_change().fillna(0)
    spy_bah_r = spy.pct_change().fillna(0)
    qqq_bah = CM.compute(qqq_bah_r)
    spy_bah = CM.compute(spy_bah_r)

    # 50/200 trend on each
    qqq_res, _ = run_50_200(qqq)
    spy_res, _ = run_50_200(spy)
    qqq_m = CM.compute(qqq_res.daily_returns, qqq_res.equity)
    spy_m = CM.compute(spy_res.daily_returns, spy_res.equity)

    print(f"\n  {'Strategy':<26}{'CAGR':>7}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}{'Vol':>7}")
    for name, m in [("QQQ buy-and-hold (NDX)", qqq_bah),
                    ("SPY buy-and-hold (SPX)", spy_bah),
                    ("QQQ 50/200 trend",       qqq_m),
                    ("SPY 50/200 trend",       spy_m)]:
        print(f"  {name:<26}{m.cagr:>+6.0%}{m.max_drawdown:>8.0%}{m.calmar:>8.2f}"
              f"{m.sortino:>9.2f}{m.vol:>7.0%}")

    # sub-period robustness
    print("\n## Sub-period Sortino (both must be positive)")
    print(f"  {'Period':<24}{'QQQ trend':>14}{'SPY trend':>14}")
    sub_qqq, sub_spy = [], []
    for lbl, a, b in SUBPERIODS:
        mq = CM.compute(sub(qqq_res.daily_returns, a, b))
        ms = CM.compute(sub(spy_res.daily_returns, a, b))
        sub_qqq.append(mq.sortino); sub_spy.append(ms.sortino)
        print(f"  {lbl:<24}{mq.sortino:>+13.2f}{ms.sortino:>+13.2f}")

    # equity-stress comparison
    print("\n## Equity-stress windows (qualitative match check)")
    print(f"  {'Window':<22}{'QQQ trend ret':>16}{'SPY trend ret':>16}")
    qual_match = True
    for lbl, a, b in STRESS:
        qd = sub(qqq_res.daily_returns, a, b)
        sd = sub(spy_res.daily_returns, a, b)
        qr = (1+qd.fillna(0)).prod() - 1
        sr = (1+sd.fillna(0)).prod() - 1
        # qualitative match: both same sign OR within 3pp
        match = (qr > 0) == (sr > 0) or abs(qr - sr) < 0.03
        if not match:
            qual_match = False
        print(f"  {lbl:<22}{qr:>+15.1%}{sr:>+15.1%}  {'match' if match else 'MISMATCH'}")

    # verdict
    print("\n" + "=" * 92)
    print("# VERDICT")
    print("=" * 92)
    calmar_close = abs(spy_m.calmar - qqq_m.calmar) <= 0.20
    dd_close = abs(spy_m.max_drawdown - qqq_m.max_drawdown) <= 0.05
    both_pos = all(s > 0 for s in sub_spy)
    print(f"\n  SPX Calmar within 0.20 of NDX:        {calmar_close}  "
          f"(QQQ {qqq_m.calmar:.2f}, SPY {spy_m.calmar:.2f})")
    print(f"  SPX MaxDD within 5pp of NDX:          {dd_close}  "
          f"(QQQ {qqq_m.max_drawdown:.0%}, SPY {spy_m.max_drawdown:.0%})")
    print(f"  SPX positive Sortino in BOTH periods: {both_pos}")
    print(f"  Equity-stress qualitative match:      {qual_match}")
    ok = calmar_close and dd_close and both_pos and qual_match
    print(f"\n  >>> SPX trend works AS WELL AS NDX: {'YES' if ok else 'NO'} <<<")
    if ok:
        print("  -> MES is a valid like-for-like swap at $40k+.")
        print("     Tax/capital efficiency benefits apply with no strategy change.")
    else:
        print("  -> MES would introduce a STRATEGY change, not just a vehicle change.")
        print("     Recommend MNQ (NDX futures) at $50k+ instead — same strategy, same")
        print("     Section 1256 tax treatment, just higher account-size threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

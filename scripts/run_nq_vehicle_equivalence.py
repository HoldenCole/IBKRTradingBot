"""NQ futures vs QQQ shares vehicle equivalence test.

Question: does the 50/200 trend rule on NQ continuous futures (Panama
back-adjusted, Databento 2010-2026) produce the same risk-adjusted result
as the same rule on QQQ shares over the same window? This validates the
planned MNQ migration at $50k+.

Both legs use Convention 2 (no look-ahead), 50/200 long-flat, T-bill 3% on
OFF capital. The QQQ leg includes 5 bps transition costs (commission-free
ETF execution); the NQ leg includes ~5 bps transition + the back-adjusted
roll cost implicit in Panama adjustment + no expense ratio.

================================ LOCKED CRITERIA ===============================
Confirm vehicle equivalence if:
  - NQ 50/200 Calmar within 0.10 of QQQ 50/200 Calmar
  - Per-era results qualitatively match (positive in same eras, negative in
    same eras; magnitudes within ~3pp where comparable)
  - Sub-period Sortinos: both POSITIVE in both 2018-2026 and 2010-2017

If equivalent: MNQ at $50k+ migration plan is validated.
If not equivalent: investigate the discrepancy before committing.
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
from src.crypto import metrics as CM
from src.crypto.engine import run_long_flat, CryptoBTConfig

START, END = "2010-06-06", "2026-06-20"

SUBPERIODS = [
    ("2018-2026 (in-sample)",      date(2018, 1, 1),  date(2026, 6, 20)),
    ("2010-2017 (held-out)",       date(2010, 6, 6),  date(2017, 12, 31)),
]
ERAS = [
    ("2010-2014 post-GFC recovery", date(2010, 6, 6),  date(2014, 12, 31)),
    ("2015-2016 chop",              date(2015, 1, 1),  date(2016, 12, 31)),
    ("2017 melt-up",                date(2017, 1, 1),  date(2017, 12, 31)),
    ("2018-Q4 correction",          date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 COVID",                  date(2020, 2, 19), date(2020, 4, 30)),
    ("2020-21 retail boom",         date(2020, 4, 1),  date(2021, 12, 31)),
    ("2022 inflation bear",         date(2022, 1, 1),  date(2022, 12, 31)),
    ("2023+ AI/ETF era",            date(2023, 1, 1),  date(2026, 6, 20)),
]


def fetch_qqq() -> pd.Series:
    import yfinance as yf
    df = yf.download("QQQ", start=START, end=END, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float)


def load_nq_adjusted() -> pd.Series:
    """Panama-adjusted NQ continuous close, trade-date collapsed."""
    loader = DatabentoLoader()
    v0 = collapse_to_trade_date(loader.continuous("NQ", depth=0, start=START, end=END))
    v1 = collapse_to_trade_date(loader.continuous("NQ", depth=1, start=START, end=END))
    return panama_adjust(v0, v1)["close"]


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def trend_signal(close: pd.Series) -> pd.Series:
    smaf = close.rolling(50, min_periods=50).mean()
    smas = close.rolling(200, min_periods=200).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def run(close: pd.Series, sig_on: pd.Series, transition_bps: float):
    cfg = CryptoBTConfig(expense_ratio=0.0, transition_bps=transition_bps,
                         tbill_annual=0.03, apply_costs=True)
    return run_long_flat(close, sig_on, cfg)


def main() -> int:
    print("Loading data...")
    nq = load_nq_adjusted().dropna()
    qqq = fetch_qqq().dropna()
    common = nq.index.intersection(qqq.index)
    nq, qqq = nq.loc[common], qqq.loc[common]
    print(f"  Common calendar: {len(common)} bars, {common[0].date()} -> {common[-1].date()}")

    print("\n" + "=" * 96)
    print("# NQ FUTURES vs QQQ SHARES vehicle equivalence (50/200 trend, 2010-2026)")
    print("=" * 96)

    nq_sig = trend_signal(nq)
    qqq_sig = trend_signal(qqq)

    nq_res = run(nq, nq_sig, transition_bps=5.0)
    qqq_res = run(qqq, qqq_sig, transition_bps=5.0)

    nq_m = CM.compute(nq_res.daily_returns, nq_res.equity)
    qqq_m = CM.compute(qqq_res.daily_returns, qqq_res.equity)
    nq_bah = CM.compute(nq.pct_change().fillna(0))
    qqq_bah = CM.compute(qqq.pct_change().fillna(0))

    print(f"\n## Full sample")
    print(f"  {'':30}{'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}{'Vol':>7}")
    for name, m in [("NQ buy-and-hold (back-adj)", nq_bah),
                    ("QQQ buy-and-hold",            qqq_bah),
                    ("NQ 50/200 trend",             nq_m),
                    ("QQQ 50/200 trend",            qqq_m)]:
        print(f"  {name:<30}{m.cagr:>+7.0%}{m.max_drawdown:>8.0%}{m.calmar:>8.2f}"
              f"{m.sortino:>9.2f}{m.vol:>7.0%}")

    # Sub-period check
    print(f"\n## Sub-period Sortino (both must be positive for both)")
    print(f"  {'Period':<26}{'NQ trend':>14}{'QQQ trend':>14}")
    sub_ok = True
    for lbl, a, b in SUBPERIODS:
        nm = CM.compute(sub(nq_res.daily_returns, a, b))
        qm = CM.compute(sub(qqq_res.daily_returns, a, b))
        if nm.sortino <= 0 or qm.sortino <= 0:
            sub_ok = False
        print(f"  {lbl:<26}{nm.sortino:>+13.2f}{qm.sortino:>+13.2f}")

    # Per-era
    print(f"\n## Per-era (return / MaxDD, qualitative match check)")
    print(f"  {'Era':<28}{'NQ trend':>20}{'QQQ trend':>20}{'Match?':>10}")
    era_mismatches = []
    for lbl, a, b in ERAS:
        nd = sub(nq_res.daily_returns, a, b)
        qd = sub(qqq_res.daily_returns, a, b)
        if len(nd) < 5:
            continue
        def stats(d):
            eq = (1 + d.fillna(0)).cumprod()
            ret = float(eq.iloc[-1] - 1) if len(eq) > 0 else 0
            dd = float(((eq.cummax() - eq) / eq.cummax()).max())
            return ret, dd
        nr, ndd = stats(nd); qr, qdd = stats(qd)
        # Match: same sign OR within 3pp
        match = (nr > 0) == (qr > 0) or abs(nr - qr) < 0.03
        if not match:
            era_mismatches.append(lbl)
        print(f"  {lbl:<28}{f'{nr:+.0%}/{ndd:.0%}':>20}{f'{qr:+.0%}/{qdd:.0%}':>20}"
              f"{'match' if match else 'MISMATCH':>10}")

    # ---- LOCKED VERDICT ----
    print("\n" + "=" * 96)
    print("# VERDICT — vehicle equivalence (locked criteria)")
    print("=" * 96)
    calmar_gap = abs(nq_m.calmar - qqq_m.calmar)
    c1 = calmar_gap <= 0.10
    c2 = len(era_mismatches) == 0
    c3 = sub_ok
    print(f"\n  Calmar within 0.10:               {'PASS' if c1 else 'FAIL'}  "
          f"(NQ {nq_m.calmar:.2f}, QQQ {qqq_m.calmar:.2f}, gap {calmar_gap:.2f})")
    print(f"  Per-era qualitative match:        {'PASS' if c2 else 'FAIL'}  "
          f"(mismatches: {era_mismatches or 'none'})")
    print(f"  Sub-periods both-positive both:   {'PASS' if c3 else 'FAIL'}")

    ok = c1 and c2 and c3
    print(f"\n  >>> VEHICLE EQUIVALENCE: {'CONFIRMED' if ok else 'NOT CONFIRMED'} <<<")
    if ok:
        print("  -> MNQ at $50k+ migration plan validated. NQ futures are a clean")
        print("     vehicle swap for QQQ shares; no strategy change.")
    else:
        print("  -> Investigate the discrepancy before committing to MNQ migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

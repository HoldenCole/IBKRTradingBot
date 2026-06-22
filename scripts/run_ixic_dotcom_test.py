"""IXIC dot-com regime validation — does 50/200 trend survive 1999-2002?

The locked deployment uses QQQ 50/200, but QQQ data (free Yahoo) only goes
back to 1999-03 and was thin/lower-quality in the early years. The IXIC
(Nasdaq Composite) is the cleanest free proxy for "the underlying market the
strategy is navigating" — 0.99+ correlation with NDX, deeper history.

This test answers ONE question only: did the 50/200 trend filter survive the
1999-2002 dot-com bear, which is the worst NDX-class drawdown in living memory
and is largely absent from our existing QQQ validation?

Methodology:
  - 50/200 SMA crossover on IXIC spot index, Convention 2 (no look-ahead).
  - Long-flat: capture IXIC return when prior-day signal ON, T-bill (3%) OFF.
  - No costs modeled — IXIC is an index proxy, not a tradeable vehicle. The
    QQQ shares version (with costs) is the deployed reality; this test is
    about regime survival, not P&L.
  - Per-era breakdown across the entire 1999-2026 window, with the 1999-2002
    bear getting specific attention.

Locked criteria (regime survival):
  - During the 1999-2002 dot-com bear, did the filter cut the drawdown to
    <40% (vs IXIC buy-and-hold which lost ~78%)?
  - Did the filter PARTICIPATE in the 1999 melt-up to a meaningful degree
    (>50% of BAH return)?
  - Across the full 27-year window, does the filter improve risk-adjusted
    return vs buy-and-hold (Calmar improvement)?

This is a regime-survival check, not a tier verdict. The deployment vehicle
(QQQ shares now / MNQ later) is set; this test asks "is there hidden regime
risk in our QQQ validation we should know about before going live?"
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.crypto import metrics as CM
from src.crypto.engine import run_long_flat, CryptoBTConfig


ERAS = [
    ("1999 dot-com melt-up",       date(1999, 1, 1),  date(2000, 3, 9)),
    ("2000-2002 dot-com bear",     date(2000, 3, 10), date(2002, 10, 9)),
    ("2003-2007 recovery",         date(2002, 10, 10), date(2007, 10, 31)),
    ("2008 GFC",                   date(2007, 11, 1), date(2009, 3, 9)),
    ("2009-2014 secular bull",     date(2009, 3, 10), date(2014, 12, 31)),
    ("2015-2017 mid-cycle",        date(2015, 1, 1),  date(2017, 12, 31)),
    ("2018-Q4 correction",         date(2018, 10, 1), date(2018, 12, 24)),
    ("2019-2020 chop+COVID",       date(2019, 1, 1),  date(2020, 9, 30)),
    ("2020-21 retail boom",        date(2020, 10, 1), date(2021, 11, 30)),
    ("2022 inflation bear",        date(2022, 1, 1),  date(2022, 12, 31)),
    ("2023+ AI/ETF era",           date(2023, 1, 1),  date(2026, 6, 20)),
]
DOTCOM_BEAR = ERAS[1]


def fetch(tk: str, start="1995-01-01", end="2026-06-21") -> pd.Series:
    import yfinance as yf
    df = yf.download(tk, start=start, end=end, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float)


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def trend_signal(close: pd.Series, fast=50, slow=200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def main() -> int:
    ixic = fetch("^IXIC").dropna()
    print("=" * 96)
    print("# DOT-COM REGIME TEST — ^IXIC 50/200 trend, 1995-2026")
    print(f"# {len(ixic)} bars, {ixic.index[0].date()} -> {ixic.index[-1].date()}")
    print("# Honest proxy for NDX/QQQ regime survival, NOT a P&L claim")
    print("=" * 96)

    signal = trend_signal(ixic)
    cfg = CryptoBTConfig(expense_ratio=0.0, transition_bps=0.0,
                         tbill_annual=0.03, apply_costs=True)
    res = run_long_flat(ixic, signal, cfg)
    bah_r = ixic.pct_change().fillna(0)

    bah_m = CM.compute(bah_r, (1+bah_r).cumprod())
    trend_m = CM.compute(res.daily_returns, res.equity)

    print(f"\n## Full sample (1995-2026)")
    print(f"  {'':30}{'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}{'Vol':>7}")
    print(f"  {'IXIC buy-and-hold':<30}{bah_m.cagr:>+7.0%}{bah_m.max_drawdown:>8.0%}"
          f"{bah_m.calmar:>8.2f}{bah_m.sortino:>9.2f}{bah_m.vol:>7.0%}")
    print(f"  {'IXIC 50/200 trend':<30}{trend_m.cagr:>+7.0%}{trend_m.max_drawdown:>8.0%}"
          f"{trend_m.calmar:>8.2f}{trend_m.sortino:>9.2f}{trend_m.vol:>7.0%}")

    print(f"\n## Per-era (CAGR / MaxDD)")
    print(f"  {'Era':<28}{'IXIC BAH':>20}{'IXIC trend':>20}")
    era_results = {}
    for lbl, a, b in ERAS:
        bd = sub(bah_r, a, b)
        td = sub(res.daily_returns, a, b)
        if len(bd) < 5:
            continue
        def stats(d):
            eq = (1 + d.fillna(0)).cumprod()
            cagr = float(eq.iloc[-1]) ** (252/len(d)) - 1 if len(d) > 0 else 0
            dd = float(((eq.cummax() - eq) / eq.cummax()).max())
            ret = float(eq.iloc[-1] - 1)
            return cagr, dd, ret
        bc, bdd, bret = stats(bd)
        tc, tdd, tret = stats(td)
        era_results[lbl] = (bret, bdd, tret, tdd)
        print(f"  {lbl:<28}{f'{bret:+.0%}/{bdd:.0%}':>20}{f'{tret:+.0%}/{tdd:.0%}':>20}")

    # ---- LOCKED CRITERIA CHECK ----
    print("\n" + "=" * 96)
    print("# DOT-COM REGIME SURVIVAL — locked criteria")
    print("=" * 96)
    dc_ret, dc_dd, dc_t_ret, dc_t_dd = era_results[DOTCOM_BEAR[0]]
    print(f"\n  1999 dot-com melt-up (1999-01 to 2000-03):")
    meltup = era_results["1999 dot-com melt-up"]
    bah_ret_meltup, _, trend_ret_meltup, _ = meltup
    participation = trend_ret_meltup / bah_ret_meltup if bah_ret_meltup > 0 else 0
    print(f"    BAH return: {bah_ret_meltup:+.0%}")
    print(f"    Trend return: {trend_ret_meltup:+.0%}  ({participation:.0%} participation)")

    print(f"\n  2000-2002 dot-com bear (2000-03 to 2002-10):")
    print(f"    BAH: {dc_ret:+.0%} return, {dc_dd:.0%} max drawdown")
    print(f"    Trend: {dc_t_ret:+.0%} return, {dc_t_dd:.0%} max drawdown")
    dd_saved = dc_dd - dc_t_dd
    print(f"    -> Drawdown cut by {dd_saved*100:.0f}pp")

    c1 = dc_t_dd < 0.40
    c2 = participation > 0.50
    c3 = trend_m.calmar > bah_m.calmar
    print(f"\n  Locked criteria:")
    print(f"    Bear DD < 40% (was {dc_t_dd:.0%})           {'PASS' if c1 else 'FAIL'}")
    print(f"    Meltup participation > 50% ({participation:.0%})  {'PASS' if c2 else 'FAIL'}")
    print(f"    Calmar improves vs BAH ({trend_m.calmar:.2f} vs {bah_m.calmar:.2f})  {'PASS' if c3 else 'FAIL'}")

    all_pass = c1 and c2 and c3
    print(f"\n  >>> DOT-COM REGIME SURVIVAL: {'YES' if all_pass else 'NO'} <<<")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

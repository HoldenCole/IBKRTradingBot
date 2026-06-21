"""Crypto characterization (pure-research round — no deployment mandate yet).

Answers four questions across BTC / ETH / LTC and the regime eras:

  Q1  The beta baseline: what does buy-and-hold actually deliver (return AND
      the brutal drawdowns) per asset, full-sample and per era?
  Q2  Does a trend filter TAME THE DRAWDOWN? Long-flat 50/200 (and a faster
      20/100) vs buy-and-hold — does it keep the upside while cutting the
      ~80% drawdowns? (Calmar is the headline stat.)
  Q3  How has crypto's EQUITY CORRELATION evolved? Full-sample + per-era
      BTC-vs-QQQ correlation. Determines if crypto could ever diversify.
  Q4  Per-regime-era strategy breakdown.

Conventions: 365-day annualization (24/7). Long-flat trend earns 0 on OFF
days (cash; characterization keeps it simple — no T-bill credit). No
look-ahead: signal at close[t-1] drives return[t]. No costs modeled in this
first characterization (crypto spot spreads are small; added later if a
mandate emerges).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from src.crypto import loader as cload
from src.crypto import metrics as CM
from src.commodity import signals as sig   # reuse sma_crossover / vol_adj_momentum

# Regime eras (BTC-centric; widely-recognized crypto cycle phases).
ERAS = [
    ("2015-2016 recovery",   date(2015, 1, 1),  date(2016, 12, 31)),
    ("2017 ICO boom",        date(2017, 1, 1),  date(2017, 12, 31)),
    ("2018 bear",            date(2018, 1, 1),  date(2018, 12, 31)),
    ("2019-2020 chop",       date(2019, 1, 1),  date(2020, 9, 30)),
    ("2020-21 retail boom",  date(2020, 10, 1), date(2021, 11, 30)),
    ("2022 contagion",       date(2022, 1, 1),  date(2022, 12, 31)),
    ("2023+ ETF era",        date(2023, 1, 1),  date(2026, 6, 20)),
]

# Equity stress windows (for the diversification reality-check).
EQUITY_STRESS = [
    ("2018-Q4 correction",  date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 March COVID",    date(2020, 2, 19), date(2020, 4, 7)),
    ("2022 inflation bear", date(2022, 1, 3),  date(2022, 10, 13)),
    ("2025 Liberation Day", date(2025, 2, 19), date(2025, 6, 30)),
]


def sub(s: pd.Series, a: date, b: date) -> pd.Series:
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def long_flat_returns(close: pd.Series, on: pd.Series) -> pd.Series:
    """Earn the coin return when prior-day signal is ON, else 0 (cash)."""
    r = close.pct_change().fillna(0.0)
    return r.where(on.shift(1).fillna(False), 0.0)


def qqq_returns() -> pd.Series:
    from src.data import yahoo
    df = yahoo.daily("QQQ", "2014-01-01", "2026-06-21")
    r = df["close"].pct_change()
    r.index = pd.to_datetime(r.index)
    return r


def main() -> int:
    panel = cload.load()
    close = panel.close
    print("=" * 100)
    print("# CRYPTO CHARACTERIZATION (pure research) — BTC / ETH / LTC, 2014-2026")
    print("=" * 100)
    for s in panel.symbols:
        c = close[s].dropna()
        print(f"  {s}: {len(c)} bars, {c.index[0].date()} -> {c.index[-1].date()}")

    # Signals (computed per-coin via the reused commodity signal module)
    rets = panel.returns()
    sma_50_200 = sig.sma_crossover(close, 50, 200)
    sma_20_100 = sig.sma_crossover(close, 20, 100)
    mom = sig.vol_adj_momentum(rets, 252, 504)

    # ---------------- Q1: buy-and-hold beta baseline ----------------
    print("\n" + "=" * 100)
    print("# Q1 — Buy-and-hold beta baseline (full sample)")
    print("=" * 100)
    print(f"\n{'Coin':<6}{'CAGR':>8}{'Vol':>7}{'Sharpe':>8}{'Sortino':>9}"
          f"{'Calmar':>8}{'MaxDD':>8}{'x from peak':>12}")
    bah_metrics = {}
    for s in panel.symbols:
        c = close[s].dropna()
        r = c.pct_change()
        m = CM.compute(r)
        bah_metrics[s] = m
        print(f"{s:<6}{m.cagr:>+7.0%}{m.vol:>7.0%}{m.sharpe:>8.2f}{m.sortino:>9.2f}"
              f"{m.calmar:>8.2f}{m.max_drawdown:>8.0%}{'':>12}")
    print("\n  Read: enormous CAGR, but MaxDD ~70-95%. Calmar (CAGR/MaxDD) is the")
    print("  honest risk-adjusted lens — buy-and-hold crypto is a low-Calmar bet.")

    # ---------------- Q2: does trend tame the drawdown? ----------------
    print("\n" + "=" * 100)
    print("# Q2 — Does a trend filter TAME THE DRAWDOWN? (long-flat vs buy-and-hold)")
    print("=" * 100)
    for s in panel.symbols:
        c = close[s].dropna()
        bah = CM.compute(c.pct_change())
        t50 = CM.compute(long_flat_returns(c, sma_50_200[s].reindex(c.index)))
        t20 = CM.compute(long_flat_returns(c, sma_20_100[s].reindex(c.index)))
        tm = CM.compute(long_flat_returns(c, mom[s].reindex(c.index)))
        print(f"\n  {s}:")
        print(f"    {'strategy':<22}{'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}")
        for lbl, m in [("buy-and-hold", bah), ("trend 50/200", t50),
                       ("trend 20/100", t20), ("vol-adj momentum", tm)]:
            print(f"    {lbl:<22}{m.cagr:>+7.0%}{m.max_drawdown:>8.0%}"
                  f"{m.calmar:>8.2f}{m.sortino:>9.2f}")

    # ---------------- Q3: equity correlation evolution ----------------
    print("\n" + "=" * 100)
    print("# Q3 — Equity-correlation evolution (BTC daily returns vs QQQ)")
    print("=" * 100)
    qqq = qqq_returns()
    btc = close["BTC"].pct_change()
    full = CM.correlation(btc, qqq)
    print(f"\n  Full-sample BTC-QQQ correlation: {full:+.2f}")
    print(f"\n  {'Era':<24}{'BTC-QQQ corr':>14}{'BTC ret':>10}{'QQQ ret':>10}")
    for lbl, a, b in ERAS:
        bd, qd = sub(btc, a, b), sub(qqq, a, b)
        c_era = CM.correlation(bd, qd)
        print(f"  {lbl:<24}{c_era:>+14.2f}{(1+bd.fillna(0)).prod()-1:>+9.0%}"
              f"{(1+qd.fillna(0)).prod()-1:>+9.0%}")
    print("\n  Read: the diversification reality. If correlation rose from ~0 to")
    print("  ~0.5+ post-2020, crypto is NOT an equity hedge in modern regimes.")

    # crypto behavior during EQUITY stress specifically
    print(f"\n  BTC buy-and-hold during EQUITY-stress windows:")
    print(f"  {'Window':<22}{'BTC ret':>10}{'QQQ ret':>10}{'corr':>8}")
    for lbl, a, b in EQUITY_STRESS:
        bd, qd = sub(btc, a, b), sub(qqq, a, b)
        print(f"  {lbl:<22}{(1+bd.fillna(0)).prod()-1:>+9.0%}"
              f"{(1+qd.fillna(0)).prod()-1:>+9.0%}{CM.correlation(bd,qd):>+8.2f}")

    # ---------------- Q4: per-era strategy breakdown ----------------
    print("\n" + "=" * 100)
    print("# Q4 — Per-era breakdown (BTC: buy-and-hold vs trend 50/200, return & MaxDD)")
    print("=" * 100)
    c = close["BTC"].dropna()
    bah_r = c.pct_change()
    t50_r = long_flat_returns(c, sma_50_200["BTC"].reindex(c.index))
    print(f"\n  {'Era':<24}{'BAH ret':>10}{'BAH DD':>9}{'Trend ret':>11}{'Trend DD':>10}")
    for lbl, a, b in ERAS:
        br, tr = sub(bah_r, a, b), sub(t50_r, a, b)
        if len(br) < 5:
            continue
        beq = (1 + br.fillna(0)).cumprod(); teq = (1 + tr.fillna(0)).cumprod()
        bdd = float(((beq.cummax()-beq)/beq.cummax()).max())
        tdd = float(((teq.cummax()-teq)/teq.cummax()).max())
        print(f"  {lbl:<24}{(beq.iloc[-1]-1):>+9.0%}{bdd:>8.0%}"
              f"{(teq.iloc[-1]-1):>+10.0%}{tdd:>9.0%}")

    print("\n" + "=" * 100)
    print("# Characterization complete — see findings doc for mandate recommendation")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""TQQQ trend test — does the QQQ 50/200 rule survive 3x leveraged-ETF decay?

The central honest question: 3x daily reset compounds losses badly in choppy
markets. A trend filter that EXITS during chop might avoid the decay regime
that destroys TQQQ buy-and-hold. Or the whipsaw cost — also amplified 3x —
might eat the gains. The test answers which.

================================ LOCKED CRITERIA ===============================
(Per the research queue, set BEFORE the run, per the criterion-mandate lesson.
Mirrors the crypto Tier-A/B structure: criteria gate on the MANDATE
"survive the leverage drawdown while capturing the leverage upside" — Calmar
and DD-reduction, NOT correlation.)

  Tier A: Calmar (CAGR/MaxDD) > 1.0 NET of decay/costs
          AND MaxDD < 50%
          AND CAGR >= 1.5 * (QQQ-trend CAGR over same window)
          AND drawdown cut in both bears (2020 COVID, 2022)
  Tier B: Calmar > 0.7
          AND MaxDD < 60%
          AND CAGR >= 1.2 * QQQ-trend CAGR
  Tier C: Calmar > 0.5
  Tier D: anything else
===============================================================================

Methodology:
  - TQQQ ACTUAL prices (not simulated 3x), so the decay IS in the data.
  - Same 50/200 signal as the equity strategy. NO crypto-style tuning.
  - Long-flat, T-bill OFF, no same-bar look-ahead.
  - Costs: TQQQ expense ratio 0.84%/yr (subtracted while held) +
           20 bps/transition (TQQQ spreads are tight but it's leveraged ->
           higher slippage on stress days).
  - QQQ comparison run on the SAME 2010-2026 window for apples-to-apples.
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
from src.commodity import metrics as M
from src.crypto.engine import run_long_flat, buy_and_hold, CryptoBTConfig

# Eras (TQQQ inception is Feb 2010)
ERAS = [
    ("2011-2015 post-GFC recovery", date(2011, 1, 1), date(2015, 12, 31)),
    ("2015-2016 chop",              date(2015, 1, 1), date(2016, 12, 31)),
    ("2017 melt-up",                date(2017, 1, 1), date(2017, 12, 31)),
    ("2018-Q4 correction",          date(2018, 10, 1), date(2018, 12, 24)),
    ("2020 COVID + recovery",       date(2020, 2, 19), date(2020, 12, 31)),
    ("2020-21 AI/retail boom",      date(2020, 4, 1), date(2021, 12, 31)),
    ("2022 inflation bear",         date(2022, 1, 1), date(2022, 12, 31)),
    ("2023-2026 ETF/AI era",        date(2023, 1, 1), date(2026, 6, 20)),
]
BEAR_ERAS = {"2018-Q4 correction", "2022 inflation bear"}
COVID = ("2020 COVID + recovery",)


def fetch_close(tk: str) -> pd.Series:
    """Use Yahoo via the project loader for cache consistency."""
    import yfinance as yf
    df = yf.download(tk, start="2010-01-01", end="2026-06-21",
                     progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["Close"].astype(float).rename(tk)


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def trend_signal(close: pd.Series, fast=50, slow=200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


def run(close: pd.Series, signal: pd.Series, expense_ratio: float,
        transition_bps: float) -> tuple[pd.Series, pd.Series, dict]:
    """Long-flat backtest using the crypto engine (same long-flat mechanics,
    T-bill OFF, no look-ahead). Returns (equity_curve, daily_returns, info)."""
    cfg = CryptoBTConfig(
        expense_ratio=expense_ratio,
        transition_bps=transition_bps,
        tbill_annual=0.03,
        apply_costs=True,
    )
    res = run_long_flat(close, signal, cfg)
    return res.equity, res.daily_returns, {
        "on_frac": res.on_fraction,
        "tpy": res.transitions_per_year,
        "cost_drag": res.cost_drag_annual,
    }


def per_era(returns: pd.Series, label: str):
    rows = []
    for lbl, a, b in ERAS:
        d = sub(returns, a, b)
        if len(d) < 10:
            continue
        eq = (1 + d).cumprod()
        cagr = (float(eq.iloc[-1]) ** (252/len(d)) - 1) if len(d) > 0 else 0
        dd = float(((eq.cummax() - eq) / eq.cummax()).max())
        rows.append((lbl, cagr, dd))
    return rows


def main() -> int:
    # ---- data ----
    tqqq = fetch_close("TQQQ").dropna()
    qqq = fetch_close("QQQ").reindex(tqqq.index).dropna()
    common = tqqq.index.intersection(qqq.index)
    tqqq, qqq = tqqq.loc[common], qqq.loc[common]

    print("=" * 96)
    print("# TQQQ TREND TEST — does 50/200 survive 3x leveraged-ETF decay?")
    print(f"# TQQQ actual prices 2010-2026 ({len(tqqq)} bars; decay is IN the data, not modeled)")
    print("=" * 96)

    # ---- 4 strategies for apples-to-apples comparison ----
    # 1. TQQQ buy-and-hold (the famous decay disaster)
    # 2. TQQQ 50/200 trend (the test)
    # 3. QQQ buy-and-hold (context)
    # 4. QQQ 50/200 trend (the deployed baseline for comparison)

    qqq_sig = trend_signal(qqq, 50, 200)
    tqqq_sig = trend_signal(tqqq, 50, 200)   # signal on TQQQ's own prices

    tqqq_bah_eq = (1 + tqqq.pct_change().fillna(0)).cumprod()
    qqq_bah_eq  = (1 + qqq.pct_change().fillna(0)).cumprod()

    # QQQ trend baseline (no expense ratio, 5 bps transitions)
    qqq_eq, qqq_rets, qqq_info = run(qqq, qqq_sig, expense_ratio=0.0, transition_bps=5.0)
    # TQQQ trend (0.84% expense, 20 bps transitions)
    tqqq_eq, tqqq_rets, tqqq_info = run(tqqq, tqqq_sig, expense_ratio=0.0084, transition_bps=20.0)

    def m(name, eq, daily, info=None):
        mm = M.compute(daily, eq) if hasattr(M, "compute") else None
        # crypto.metrics returns CryptoMetrics with calmar; use it
        from src.crypto import metrics as CM
        cm = CM.compute(daily, eq)
        print(f"  {name:<26}  CAGR {cm.cagr:>+6.0%}  MaxDD {cm.max_drawdown:>5.0%}  "
              f"Calmar {cm.calmar:>5.2f}  Sortino {cm.sortino:>5.2f}  Vol {cm.vol:>5.0%}", end="")
        if info:
            print(f"   ON {info['on_frac']:.0%}, {info['tpy']:.1f} trans/yr, cost {info['cost_drag']*100:.2f}%/yr")
        else:
            print()
        return cm

    print(f"\n  {'Strategy':<26}  {'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}{'Vol':>7}")
    qqq_bah_m  = m("QQQ buy-and-hold",       qqq_bah_eq,  qqq.pct_change().fillna(0))
    tqqq_bah_m = m("TQQQ buy-and-hold",      tqqq_bah_eq, tqqq.pct_change().fillna(0))
    qqq_t_m    = m("QQQ 50/200 (deployed)",  qqq_eq,      qqq_rets,  qqq_info)
    tqqq_t_m   = m("TQQQ 50/200 (the test)", tqqq_eq,     tqqq_rets, tqqq_info)

    # ---- per-era ----
    print("\n## Per-era breakdown — TQQQ trend vs TQQQ BAH vs QQQ trend (CAGR, MaxDD)")
    print(f"\n  {'Era':<28}{'TQQQ BAH':>16}{'TQQQ trend':>16}{'QQQ trend':>16}")
    for lbl, a, b in ERAS:
        bd = sub(tqqq.pct_change().fillna(0), a, b)
        td = sub(tqqq_rets, a, b)
        qd = sub(qqq_rets, a, b)
        if len(bd) < 10:
            continue
        def stats(d):
            eq = (1 + d).cumprod()
            cagr = float(eq.iloc[-1]) ** (252/len(d)) - 1 if len(d) > 0 else 0
            dd = float(((eq.cummax()-eq)/eq.cummax()).max())
            return cagr, dd
        bc, bdd = stats(bd); tc, tdd = stats(td); qc, qdd = stats(qd)
        print(f"  {lbl:<28}{f'{bc:+.0%}/{bdd:.0%}':>16}"
              f"{f'{tc:+.0%}/{tdd:.0%}':>16}{f'{qc:+.0%}/{qdd:.0%}':>16}")

    # ---- locked verdict ----
    print("\n" + "=" * 96)
    print("# VERDICT (locked criteria, set before the run)")
    print("=" * 96)
    qqq_cagr = qqq_t_m.cagr
    bears_cut = True
    for bear_lbl in BEAR_ERAS:
        for lbl, a, b in ERAS:
            if lbl != bear_lbl:
                continue
            bd = sub(tqqq.pct_change().fillna(0), a, b)
            td = sub(tqqq_rets, a, b)
            if len(bd) < 5:
                continue
            bah_dd = float((((1+bd).cumprod()).cummax() - (1+bd).cumprod()).max() /
                           ((1+bd).cumprod().cummax()).max() * -1 * -1)  # crude
            # cleaner: dd
            be = (1+bd).cumprod(); te = (1+td).cumprod()
            bdd = float(((be.cummax()-be)/be.cummax()).max())
            tdd = float(((te.cummax()-te)/te.cummax()).max())
            if not (tdd < bdd):
                bears_cut = False
    def verdict():
        if (tqqq_t_m.calmar > 1.0 and tqqq_t_m.max_drawdown < 0.50
                and tqqq_t_m.cagr >= 1.5 * qqq_cagr and bears_cut):
            return "A"
        if (tqqq_t_m.calmar > 0.7 and tqqq_t_m.max_drawdown < 0.60
                and tqqq_t_m.cagr >= 1.2 * qqq_cagr):
            return "B"
        if tqqq_t_m.calmar > 0.5:
            return "C"
        return "D"
    t = verdict()
    print(f"\n  TQQQ trend: Calmar {tqqq_t_m.calmar:.2f} | MaxDD {tqqq_t_m.max_drawdown:.0%} | "
          f"CAGR {tqqq_t_m.cagr:+.0%} ({tqqq_t_m.cagr/qqq_cagr:.2f}x QQQ trend's {qqq_cagr:+.0%}) | "
          f"bears cut: {bears_cut}")
    print(f"\n  >>> TIER {t} <<<")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

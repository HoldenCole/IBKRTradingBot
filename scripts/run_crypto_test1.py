"""Crypto Test 1 (locked criteria) — 'tame-the-drawdown beta' mandate.

Tests the equity-validated 50/200 trend rule transferred to crypto (NO
crypto-specific parameter tuning — one-look discipline). Long-flat, T-bill
on OFF capital, costs modeled (IBIT/ETHA expense + transition slippage),
no same-bar look-ahead. BTC primary, ETH secondary, LTC dropped per the
characterization mandate.

================================ LOCKED CRITERIA ===============================
Mandate = tame the drawdown: capture crypto upside, cut the ~80% drawdowns.
Criteria are gated on the MANDATE (Calmar / drawdown / return-retention),
NOT on equity correlation (per the methodological lesson: gate on the metric
the mandate emphasizes, not the de-emphasized one). Correlation is REPORTED,
never gated.

  Tier A:
    - Calmar (CAGR/MaxDD) > 1.0
    - Max drawdown < 50%        (vs buy-and-hold ~83%)
    - CAGR >= buy-and-hold CAGR (keeps the upside while cutting risk)
    - Robust: trend improves Calmar over buy-and-hold in >= 5 of 7 regime eras
    - Drawdown cut in EVERY bear era (2018, 2022)
  Tier B:
    - Calmar > 0.7
    - Max drawdown < 60%
    - CAGR >= 0.8 * buy-and-hold CAGR
    - Robust: improves Calmar in >= 4 of 7 eras
  Tier C:
    - Calmar > 0.5, marginal otherwise
  Tier D: anything else
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

from src.crypto import loader as cload
from src.crypto import metrics as CM
from src.crypto.engine import run_long_flat, buy_and_hold, CryptoBTConfig
from src.commodity import signals as sig

ERAS = [
    ("2015-2016 recovery",  date(2015, 1, 1),  date(2016, 12, 31)),
    ("2017 ICO boom",       date(2017, 1, 1),  date(2017, 12, 31)),
    ("2018 bear",           date(2018, 1, 1),  date(2018, 12, 31)),
    ("2019-2020 chop",      date(2019, 1, 1),  date(2020, 9, 30)),
    ("2020-21 retail boom", date(2020, 10, 1), date(2021, 11, 30)),
    ("2022 contagion",      date(2022, 1, 1),  date(2022, 12, 31)),
    ("2023+ ETF era",       date(2023, 1, 1),  date(2026, 6, 20)),
]
BEAR_ERAS = {"2018 bear", "2022 contagion"}


def sub(s, a, b):
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def era_calmar(returns: pd.Series, a, b) -> tuple[float, float, float]:
    d = sub(returns, a, b)
    if len(d) < 20:
        return float("nan"), float("nan"), float("nan")
    m = CM.compute(d)
    return m.cagr, m.max_drawdown, m.calmar


def after_tax_cagr(equity: pd.Series, st_rate=0.37, days=365) -> float:
    """Crude after-tax on total gain at the short-term (ordinary) rate — a
    conservative bound; spot crypto held >1yr would get LTCG and has NO
    wash-sale rule (a real advantage vs the ETF). Reported as a floor."""
    final = float(equity.iloc[-1]); gain = final - 1.0
    at = 1.0 + gain * (1 - st_rate) if gain > 0 else final
    yrs = len(equity) / days
    return at ** (1 / yrs) - 1 if at > 0 and yrs > 0 else -1.0


def verdict(calmar, maxdd, cagr, bah_cagr, n_eras_improve, bears_cut) -> str:
    if (calmar > 1.0 and maxdd < 0.50 and cagr >= bah_cagr
            and n_eras_improve >= 5 and bears_cut):
        return "A"
    if (calmar > 0.7 and maxdd < 0.60 and cagr >= 0.8 * bah_cagr
            and n_eras_improve >= 4):
        return "B"
    if calmar > 0.5:
        return "C"
    return "D"


def main() -> int:
    panel = cload.load(["BTC", "ETH"])
    cfg = CryptoBTConfig(expense_ratio=0.0025, transition_bps=10.0,
                         tbill_annual=0.03, apply_costs=True)

    print("=" * 96)
    print("# CRYPTO TEST 1 — tame-the-drawdown beta, 50/200 trend (equity-validated rule)")
    print("# Costs: IBIT/ETHA 0.25% expense + 10bps/transition; T-bill 3% OFF; no look-ahead")
    print("=" * 96)

    for coin in panel.symbols:
        c = panel.close[coin].dropna()
        on = sig.sma_crossover(panel.close[[coin]], 50, 200)[coin]
        res = run_long_flat(c, on, cfg)
        m = CM.compute(res.daily_returns, res.equity)
        bah_r = buy_and_hold(c)
        bah = CM.compute(bah_r)

        print(f"\n{'='*96}\n# {coin}\n{'='*96}")
        print(f"  {'':22}{'CAGR':>8}{'MaxDD':>8}{'Calmar':>8}{'Sortino':>9}{'Vol':>7}")
        print(f"  {'buy-and-hold':22}{bah.cagr:>+7.0%}{bah.max_drawdown:>8.0%}"
              f"{bah.calmar:>8.2f}{bah.sortino:>9.2f}{bah.vol:>7.0%}")
        print(f"  {'trend 50/200 (net)':22}{m.cagr:>+7.0%}{m.max_drawdown:>8.0%}"
              f"{m.calmar:>8.2f}{m.sortino:>9.2f}{m.vol:>7.0%}")
        bah_eq = (1 + bah_r).cumprod()
        print(f"  ON {res.on_fraction:.0%} of days | {res.transitions_per_year:.1f} "
              f"transitions/yr | cost drag ~{res.cost_drag_annual*100:.2f}%/yr")
        print(f"  After-tax CAGR (37% ST floor): trend {after_tax_cagr(res.equity):+.0%} "
              f"vs BAH {after_tax_cagr(bah_eq):+.0%}")

        # per-era robustness
        print(f"\n  {'Era':<22}{'BAH Calmar':>11}{'Trend Calmar':>14}{'Trend MaxDD':>13}{'improve?':>10}")
        n_improve = 0; bears_cut = True
        for lbl, a, b in ERAS:
            _, bdd, bcal = era_calmar(bah_r, a, b)
            tcagr, tdd, tcal = era_calmar(res.daily_returns, a, b)
            if np.isnan(tcal):
                continue
            imp = (tcal > bcal) if not np.isnan(bcal) else (tcal > 0)
            n_improve += int(imp)
            if lbl in BEAR_ERAS:
                # bear era: require trend DD < BAH DD
                if not (tdd < bdd):
                    bears_cut = False
            print(f"  {lbl:<22}{bcal:>11.2f}{tcal:>14.2f}{tdd:>12.0%}{'  yes' if imp else '   no':>10}")

        t = verdict(m.calmar, m.max_drawdown, m.cagr, bah.cagr, n_improve, bears_cut)
        print(f"\n  Robustness: improved Calmar in {n_improve}/7 eras; bears cut: {bears_cut}")
        print(f"  >>> {coin} TIER {t} <<<  "
              f"(Calmar {m.calmar:.2f}, MaxDD {m.max_drawdown:.0%}, "
              f"CAGR {m.cagr:+.0%} vs BAH {bah.cagr:+.0%})")

    # correlation REPORTED (never gated)
    print(f"\n{'='*96}\n# Equity correlation (REPORTED, not gated — crypto's job here isn't diversification)")
    print('='*96)
    try:
        from src.data import yahoo
        qqq = yahoo.daily("QQQ", "2014-01-01", "2026-06-21")["close"].pct_change()
        qqq.index = pd.to_datetime(qqq.index)
        for coin in panel.symbols:
            on = sig.sma_crossover(panel.close[[coin]], 50, 200)[coin]
            res = run_long_flat(panel.close[coin].dropna(), on, cfg)
            print(f"  {coin} trend strategy vs QQQ: {CM.correlation(res.daily_returns, qqq):+.2f}")
    except Exception as e:
        print(f"  (unavailable: {e!r})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Futures BAH-on-trend test — does the rule generalize beyond shares?

Tests the same SMA(50)>SMA(200) AND close>SMA(50) rule on:
  - SPX cash index signal -> ES/MES futures trade
  - NDX cash index signal -> NQ/MNQ futures trade

Compares to the share-vehicle baseline (SPY/QQQ shares) at the same
underlying. Models futures-specific costs:

  - Continuous-contract daily returns from cash-index returns (futures
    track cash index basis-adjusted; we model returns from cash and
    deduct quarterly roll costs).
  - Roll cost: 8 bps/year (4 quarterly rolls × 2 bps each), applied
    continuously on ON-days as ~0.0317 bps/trading-day drag.
  - Section 1256 tax: 60% LTCG (15%) + 40% STCG (30%) = 21% effective.
  - Shares tax (conservative, all short-term): 30% effective.

Sizing scenarios (per user spec):
  A. Cash-1x: hold cash-index-equivalent return, no leverage. Baseline
     for "does the rule work in any form."
  B. 1-contract MNQ/MES: hold one micro contract throughout ON regime.
     ~5x leverage on $8k account for MNQ; ~3.6x for MES.
  C. Max-margin compounding: rebalance contracts as equity grows;
     50% margin utilization to leave buffer.

Decision criteria (locked):
  - Futures lift comparable to share lift (within 50%): generalizes
  - Futures lift higher after taxes/rolls: deploy on futures
  - Futures lift lower: deploy on shares, keep futures for tax-deferred
  - No lift on futures: edge may be share-specific, investigate

Periods: 2018-2026 / 2010-2017 / 2000-2009. Same train/test split.
"""
from __future__ import annotations

import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics


# Futures contract specs (from CME, current as of 2026)
SPECS = {
    "MES": {"multiplier": 5.0,  "margin_init": 1500,  "index": "^GSPC"},
    "ES":  {"multiplier": 50.0, "margin_init": 13000, "index": "^GSPC"},
    "MNQ": {"multiplier": 2.0,  "margin_init": 2200,  "index": "^NDX"},
    "NQ":  {"multiplier": 20.0, "margin_init": 22000, "index": "^NDX"},
}

# Tax rates (effective)
SHARES_TAX_RATE = 0.30        # all-short-term assumption (conservative)
FUTURES_TAX_RATE = 0.21       # Section 1256: 0.6*0.15 + 0.4*0.30
ROLL_COST_BPS_PER_YEAR = 8    # ~2 bps × 4 quarterly rolls
ROLL_COST_PER_DAY = (ROLL_COST_BPS_PER_YEAR / 10_000) / 252


def fetch_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, progress=False,
                     auto_adjust=False, group_by="column")
    if df.empty:
        return pd.DataFrame()
    if hasattr(df.columns, "get_level_values"):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    return df[["open", "high", "low", "close", "volume"]]


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    sma_fast = close.rolling(fast, min_periods=fast).mean()
    sma_slow = close.rolling(slow, min_periods=slow).mean()
    return ((close > sma_fast) & (sma_fast > sma_slow)).fillna(False)


def cash_strategy_equity(close: pd.Series, start_capital: float) -> pd.Series:
    """Scenario A: hold cash-index-equivalent (1x, no leverage), no roll cost.
    This is the same as the share BAH-on-trend test."""
    rets = close.pct_change().fillna(0.0)
    flags = filter_on_flags(close)
    masked = rets.where(flags, 0.0)
    return (1 + masked).cumprod() * start_capital


def futures_one_contract_equity(
    close: pd.Series, start_capital: float, multiplier: float,
) -> pd.Series:
    """Scenario B: hold 1 contract during ON regime.
    Daily P&L = (close_today - close_yesterday) * multiplier - roll_cost_per_day * notional.
    """
    flags = filter_on_flags(close)
    daily_change = close.diff().fillna(0.0)
    # P&L per day: index_change * multiplier when ON, else 0
    pnl = (daily_change * multiplier).where(flags, 0.0)
    # Roll cost on ON days: bps per day * notional held
    notional = close * multiplier
    roll_drag = (notional * ROLL_COST_PER_DAY).where(flags, 0.0)
    pnl_net = pnl - roll_drag
    equity = start_capital + pnl_net.cumsum()
    return equity


def futures_max_margin_equity(
    close: pd.Series, start_capital: float, multiplier: float,
    margin_per_contract: float, margin_use_pct: float = 0.50,
) -> pd.Series:
    """Scenario C: max contracts the equity supports at margin_use_pct.
    Rebalance contract count weekly (Mondays only) to limit churn.
    """
    flags = filter_on_flags(close)
    daily_change = close.diff().fillna(0.0)
    equity = pd.Series(start_capital, index=close.index, dtype=float)
    contracts = 0
    last_rebalance_week = -1

    for i in range(1, len(close)):
        prev_eq = equity.iloc[i - 1]
        # Rebalance on Mondays (weekday 0)
        idx_date = close.index[i]
        week = idx_date.isocalendar()[1] if hasattr(idx_date, "isocalendar") else 0
        if week != last_rebalance_week and flags.iloc[i]:
            new_contracts = int((prev_eq * margin_use_pct) // margin_per_contract)
            contracts = max(0, new_contracts)
            last_rebalance_week = week
        if not flags.iloc[i]:
            contracts = 0

        # P&L for today
        d_change = daily_change.iloc[i]
        pnl = d_change * multiplier * contracts
        notional = close.iloc[i] * multiplier * contracts
        roll = notional * ROLL_COST_PER_DAY if contracts > 0 else 0.0
        equity.iloc[i] = prev_eq + pnl - roll

    return equity


def after_tax_metrics(equity: pd.Series, start_capital: float, tax_rate: float) -> dict:
    """Apply flat tax rate to gains. Realized P&L = final - initial for
    a buy-and-hold style strategy that only realizes at the end. For
    BAH-on-trend with SMA crosses, every cross is a realization, so
    actual after-tax is worse than this (we'd need to model each leg).
    Simplification: apply tax to TOTAL gain at end of period.
    """
    gross = equity.iloc[-1] - start_capital
    tax = max(0, gross) * tax_rate
    after_tax_equity = start_capital + (gross - tax)
    after_tax_return = (after_tax_equity - start_capital) / start_capital
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    after_tax_cagr = ((after_tax_equity / start_capital) ** (1.0 / max(years, 1e-9)) - 1.0) \
                     if years > 0 else 0.0
    m = equity_metrics(equity, start_capital)
    m["after_tax_equity"] = float(after_tax_equity)
    m["after_tax_return"] = float(after_tax_return)
    m["after_tax_cagr"] = float(after_tax_cagr)
    m["tax_paid"] = float(tax)
    return m


def report_period(label: str, start: date, end: date, contract: str,
                  start_capital: float = 8000.0):
    spec = SPECS[contract]
    index_sym = spec["index"]

    print(f"\n{'='*92}")
    print(f"PERIOD {label}: {start} -> {end}  |  contract: {contract}  "
          f"(mult ${spec['multiplier']}, margin ${spec['margin_init']})")
    print(f"{'='*92}")

    idx = fetch_yahoo(index_sym, start.isoformat(), end.isoformat())
    if idx.empty:
        print(f"  ERROR: no data for {index_sym}")
        return None

    # Slice to exact period (yfinance includes some adjacent days)
    mask = (idx.index >= pd.Timestamp(start)) & (idx.index <= pd.Timestamp(end))
    idx = idx.loc[mask]
    close = idx["close"]

    # Benchmark: cash index buy-and-hold
    bah = buy_and_hold_metrics(close, start_capital, index_sym)

    # Three sizing scenarios on the same SMA(50)/(200) rule
    eq_cash = cash_strategy_equity(close, start_capital)
    eq_one = futures_one_contract_equity(close, start_capital, spec["multiplier"])
    eq_max = futures_max_margin_equity(
        close, start_capital, spec["multiplier"], spec["margin_init"]
    )

    # Pre-tax metrics
    m_cash = equity_metrics(eq_cash, start_capital)
    m_one = equity_metrics(eq_one, start_capital)
    m_max = equity_metrics(eq_max, start_capital)

    # After-tax (shares rate for cash, futures rate for futures)
    at_cash = after_tax_metrics(eq_cash, start_capital, SHARES_TAX_RATE)
    at_one = after_tax_metrics(eq_one, start_capital, FUTURES_TAX_RATE)
    at_max = after_tax_metrics(eq_max, start_capital, FUTURES_TAX_RATE)
    at_bah = (bah.final_equity - start_capital) * (1 - SHARES_TAX_RATE) + start_capital

    print(f"\n  Filter ON days: {int(filter_on_flags(close).sum())}/{len(close)} "
          f"({filter_on_flags(close).sum()/len(close):.0%})")

    print(f"\n  {'Vehicle':32s}  {'Sortino':>7s}  {'Return':>9s}  {'CAGR':>6s}  "
          f"{'Max DD':>7s}  {'Final $':>10s}  {'After-tax':>10s}")
    print(f"  {'BAH cash index (no rule)':32s}  {bah.sortino:>7.2f}  "
          f"{bah.total_return:>+8.1%}  {bah.cagr:>+5.1%}  "
          f"{bah.max_drawdown:>+6.1%}  ${bah.final_equity:>8,.0f}  ${at_bah:>8,.0f}")
    print(f"  {'A. Cash-rule (shares-equiv)':32s}  {m_cash['sortino']:>7.2f}  "
          f"{m_cash['total_return']:>+8.1%}  {m_cash['cagr']:>+5.1%}  "
          f"{m_cash['max_drawdown']:>+6.1%}  ${m_cash['final_equity']:>8,.0f}  "
          f"${at_cash['after_tax_equity']:>8,.0f}")
    print(f"  {'B. 1 contract '+contract:32s}  {m_one['sortino']:>7.2f}  "
          f"{m_one['total_return']:>+8.1%}  {m_one['cagr']:>+5.1%}  "
          f"{m_one['max_drawdown']:>+6.1%}  ${m_one['final_equity']:>8,.0f}  "
          f"${at_one['after_tax_equity']:>8,.0f}")
    print(f"  {'C. Max-margin '+contract+' (compound)':32s}  {m_max['sortino']:>7.2f}  "
          f"{m_max['total_return']:>+8.1%}  {m_max['cagr']:>+5.1%}  "
          f"{m_max['max_drawdown']:>+6.1%}  ${m_max['final_equity']:>8,.0f}  "
          f"${at_max['after_tax_equity']:>8,.0f}")

    print(f"\n  Sortino lift over BAH:  cash-rule {m_cash['sortino']-bah.sortino:+.2f}  |  "
          f"1-{contract} {m_one['sortino']-bah.sortino:+.2f}  |  "
          f"max-margin {m_max['sortino']-bah.sortino:+.2f}")

    return {
        "label": label, "bah": bah,
        "m_cash": m_cash, "m_one": m_one, "m_max": m_max,
        "at_cash": at_cash, "at_one": at_one, "at_max": at_max,
        "after_tax_bah": at_bah,
    }


def main() -> int:
    print("# BAH-on-trend FUTURES test — does the rule generalize beyond shares?")
    print("# Signal: cash index SMA(50)/(200). Trade: ES/MES (S&P) and NQ/MNQ (NDX).")
    print("# Roll cost: 8 bps/yr (~2 bps × 4 quarterly rolls).")
    print("# Tax: shares 30% STCG; futures 21% via Section 1256 (60%/40%).")
    print("# No MA window tuning; same 50/200 as locked.\n")

    periods = [
        ("2018-2026 (in-sample)", date(2018, 1, 1), date(2026, 4, 15)),
        ("2010-2017 (held-out)",  date(2010, 1, 1), date(2017, 12, 31)),
        ("2000-2009 (regime shift)", date(2000, 9, 18), date(2009, 12, 31)),
        # 2000-2009 starts when ES/NQ data starts (Sep 18, 2000)
    ]

    print("\n" + "#" * 92)
    print("# SECTION 1: NQ / MNQ on NDX")
    print("#" * 92)
    nq_results = {}
    for label, s, e in periods:
        nq_results[label] = report_period(label, s, e, "MNQ")

    print("\n" + "#" * 92)
    print("# SECTION 2: ES / MES on SPX")
    print("#" * 92)
    es_results = {}
    for label, s, e in periods:
        es_results[label] = report_period(label, s, e, "MES")

    # Apply decision rules
    print("\n" + "=" * 92)
    print("DECISION RULE APPLICATION")
    print("=" * 92)
    print("\nUser-locked criteria:")
    print("  - Futures lift within 50% of share lift -> generalizes, deploy candidate")
    print("  - Futures lift higher after taxes/rolls -> deploy on futures")
    print("  - Futures lift lower -> deploy on shares")
    print("  - Futures break the rule (no lift) -> share-specific edge\n")

    # Compare cash-rule (=share-equivalent) lift to 1-MNQ lift across periods
    for label in [p[0] for p in periods]:
        r = nq_results.get(label)
        if r is None:
            continue
        share_sortino_lift = r["m_cash"]["sortino"] - r["bah"].sortino
        futures1_sortino_lift = r["m_one"]["sortino"] - r["bah"].sortino
        futures_max_sortino_lift = r["m_max"]["sortino"] - r["bah"].sortino
        share_after_tax_ret = r["at_cash"]["after_tax_return"]
        futures1_after_tax_ret = r["at_one"]["after_tax_return"]
        max_after_tax_ret = r["at_max"]["after_tax_return"]
        bah_after_tax_ret = (r["after_tax_bah"] - 8000) / 8000

        print(f"\n[{label}] NDX/MNQ:")
        print(f"  Sortino lift over BAH:")
        print(f"    Shares-equiv:  {share_sortino_lift:+.2f}")
        print(f"    1-MNQ:         {futures1_sortino_lift:+.2f}  "
              f"({'comparable' if abs(futures1_sortino_lift - share_sortino_lift) < 0.5 * abs(share_sortino_lift) else 'different'})")
        print(f"    Max-margin:    {futures_max_sortino_lift:+.2f}")
        print(f"  After-tax return:")
        print(f"    BAH cash:      {bah_after_tax_ret:+.1%}")
        print(f"    Shares-equiv:  {share_after_tax_ret:+.1%}")
        print(f"    1-MNQ:         {futures1_after_tax_ret:+.1%}")
        print(f"    Max-margin:    {max_after_tax_ret:+.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

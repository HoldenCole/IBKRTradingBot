"""Leverage-targeted BAH-on-trend with tax bracket sensitivity.

Replaces the prior "1 contract constant" and "max-margin compounding"
sizing with a proper target-leverage approach:

  Target leverage L (e.g., 1.5 or 2.0):
    daily_leveraged_return = L * (cash_rule_return - roll_cost_per_day)
    equity_t+1 = equity_t * (1 + daily_leveraged_return)

This abstracts away contract granularity (whole-contract rounding is
addressed in the deployment notes — at $8k the smallest viable MNQ
position is already 5x; targets below that aren't feasible until
account size grows). The theoretical-leverage analysis answers the
question "what does 1.5x or 2.0x leverage on the rule produce?" and
the deployment notes address what's actually executable at given
account sizes.

Tax model: four scenarios crossed (lower vs higher federal bracket ×
with vs without NIIT). Texas user, federal only.

  Federal rates used (rough):
    Lower (~24% bracket): STCG 24%, LTCG 15%
    Higher (37% bracket): STCG 37%, LTCG 20%
    NIIT: +3.8% on investment income for AGI > $200k single

  Effective rate by vehicle:
    Shares (assumed all-STCG in this strategy): 24% / 27.8% / 37% / 40.8%
    Futures (Section 1256 60% LTCG / 40% STCG):
      Lower: 0.6*15 + 0.4*24 = 18.6%
      Lower+NIIT: 0.6*18.8 + 0.4*27.8 = 22.4%
      Higher: 0.6*20 + 0.4*37 = 26.8%
      Higher+NIIT: 0.6*23.8 + 0.4*40.8 = 30.6%

Operational complexity (modeled where possible, noted where not):
  - Roll cost: 8 bps/yr (4 quarterly rolls × 2 bps); MODELED.
  - Daily mark-to-market: implicit in equity curve; MODELED.
  - Margin variation with vol: backtest uses fixed 50% margin buffer;
    real margin requirements rise in high-vol periods. NOTED.
  - Year-end Section 1256 mark-to-market: tax owed on unrealized gains
    Dec 31. Affects cash flow but not total equity in the long run.
    NOTED, not modeled.
  - Margin call risk: backtest has no force-liquidation. In real
    deployment, leverage > 2x has measurable margin-call probability
    in fast moves. NOTED.
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import buy_and_hold_metrics, equity_metrics


SPECS = {
    "MES": {"multiplier": 5.0,  "margin": 1500,  "index": "^GSPC"},
    "MNQ": {"multiplier": 2.0,  "margin": 2200,  "index": "^NDX"},
}

# Roll cost: 8 bps/yr -> per-day on ON regime
ROLL_COST_PER_DAY_OF_NOTIONAL = (8.0 / 10_000) / 252  # ~0.0317 bps/day


@dataclass(frozen=True)
class TaxScenario:
    label: str
    stcg_rate: float       # short-term capital gains incl any NIIT
    ltcg_rate: float       # long-term capital gains incl any NIIT
    @property
    def shares_rate(self) -> float:
        # Conservative: assume all shares trades are short-term
        return self.stcg_rate
    @property
    def futures_rate(self) -> float:
        # Section 1256: 60% LTCG, 40% STCG
        return 0.6 * self.ltcg_rate + 0.4 * self.stcg_rate


TAX_SCENARIOS = [
    TaxScenario("Lower bracket (24% STCG, 15% LTCG)",
                stcg_rate=0.24, ltcg_rate=0.15),
    TaxScenario("Lower bracket + NIIT 3.8%",
                stcg_rate=0.24 + 0.038, ltcg_rate=0.15 + 0.038),
    TaxScenario("Higher bracket (37% STCG, 20% LTCG)",
                stcg_rate=0.37, ltcg_rate=0.20),
    TaxScenario("Higher bracket + NIIT 3.8%",
                stcg_rate=0.37 + 0.038, ltcg_rate=0.20 + 0.038),
]


def fetch_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, start=start, end=end, progress=False,
                     auto_adjust=False, group_by="column")
    if df.empty:
        return pd.DataFrame()
    if hasattr(df.columns, "get_level_values"):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                            "Close": "close", "Volume": "volume"})
    return df[["open", "high", "low", "close", "volume"]]


def filter_on_flags(close: pd.Series, fast=50, slow=200) -> pd.Series:
    sma_fast = close.rolling(fast, min_periods=fast).mean()
    sma_slow = close.rolling(slow, min_periods=slow).mean()
    return ((close > sma_fast) & (sma_fast > sma_slow)).fillna(False)


def cash_rule_returns(close: pd.Series) -> pd.Series:
    """Daily returns of the cash-rule strategy (1x leverage, no roll cost)."""
    rets = close.pct_change().fillna(0.0)
    flags = filter_on_flags(close)
    return rets.where(flags, 0.0)


def leveraged_strategy_equity(
    close: pd.Series,
    target_leverage: float,
    start_capital: float = 8000.0,
) -> pd.Series:
    """Apply target leverage to cash-rule returns. Subtract roll cost
    proportional to leverage (more contracts -> more roll cost).
    Returns the equity curve.
    """
    cash_rets = cash_rule_returns(close)
    flags = filter_on_flags(close)
    # Roll cost is paid on notional held during ON regime
    # Per-day per-1x-leverage roll cost = ROLL_COST_PER_DAY_OF_NOTIONAL
    # Per-day at L leverage = L * ROLL_COST_PER_DAY_OF_NOTIONAL
    roll_drag = pd.Series(0.0, index=close.index)
    roll_drag[flags] = target_leverage * ROLL_COST_PER_DAY_OF_NOTIONAL
    leveraged_rets = target_leverage * cash_rets - roll_drag
    return (1 + leveraged_rets).cumprod() * start_capital


def shares_strategy_equity(close: pd.Series, start_capital: float = 8000.0) -> pd.Series:
    """Cash-rule applied as shares (1x, no roll cost) — for tax comparison."""
    cash_rets = cash_rule_returns(close)
    return (1 + cash_rets).cumprod() * start_capital


def after_tax_final(final_equity: float, start_capital: float, rate: float) -> float:
    """Apply flat tax rate to total gain (positive only)."""
    gain = final_equity - start_capital
    tax = max(0, gain) * rate
    return start_capital + (gain - tax)


def cagr(final_equity: float, start_capital: float, years: float) -> float:
    if final_equity <= 0 or years <= 0:
        return 0.0
    return (final_equity / start_capital) ** (1.0 / years) - 1.0


def run_period(label: str, start: date, end: date, contract: str,
               start_capital: float = 8000.0):
    spec = SPECS[contract]
    print(f"\n{'='*100}")
    print(f"PERIOD {label}  |  {start} -> {end}  |  contract: {contract}")
    print(f"{'='*100}")

    idx = fetch_yahoo(spec["index"], start.isoformat(), end.isoformat())
    if idx.empty:
        print(f"  ERROR: no data for {spec['index']}")
        return None

    mask = (idx.index >= pd.Timestamp(start)) & (idx.index <= pd.Timestamp(end))
    close = idx.loc[mask]["close"]
    years = (close.index[-1] - close.index[0]).days / 365.25

    bah = buy_and_hold_metrics(close, start_capital, spec["index"])
    eq_shares = shares_strategy_equity(close, start_capital)
    eq_lev_15 = leveraged_strategy_equity(close, 1.5, start_capital)
    eq_lev_20 = leveraged_strategy_equity(close, 2.0, start_capital)
    # Deployable-at-$8k variants (whole-contract realities)
    if contract == "MES":
        eq_lev_actual = leveraged_strategy_equity(close, 3.6, start_capital)
        actual_label = "Futures 3.6x (1 MES on $8k)"
    else:
        eq_lev_actual = leveraged_strategy_equity(close, 5.0, start_capital)
        actual_label = "Futures 5.0x (1 MNQ on $8k)"

    m_shares = equity_metrics(eq_shares, start_capital)
    m_15 = equity_metrics(eq_lev_15, start_capital)
    m_20 = equity_metrics(eq_lev_20, start_capital)
    m_actual = equity_metrics(eq_lev_actual, start_capital)

    print(f"\n  BAH cash index:    Sortino {bah.sortino:>+5.2f}  return {bah.total_return:>+7.1%}  "
          f"DD {bah.max_drawdown:>+6.1%}  final ${bah.final_equity:>9,.0f}")
    print(f"  Shares (1x):       Sortino {m_shares['sortino']:>+5.2f}  "
          f"return {m_shares['total_return']:>+7.1%}  DD {m_shares['max_drawdown']:>+6.1%}  "
          f"final ${m_shares['final_equity']:>9,.0f}")
    print(f"  Futures 1.5x:      Sortino {m_15['sortino']:>+5.2f}  "
          f"return {m_15['total_return']:>+7.1%}  DD {m_15['max_drawdown']:>+6.1%}  "
          f"final ${m_15['final_equity']:>9,.0f}")
    print(f"  Futures 2.0x:      Sortino {m_20['sortino']:>+5.2f}  "
          f"return {m_20['total_return']:>+7.1%}  DD {m_20['max_drawdown']:>+6.1%}  "
          f"final ${m_20['final_equity']:>9,.0f}")
    print(f"  {actual_label:18s} Sortino {m_actual['sortino']:>+5.2f}  "
          f"return {m_actual['total_return']:>+7.1%}  DD {m_actual['max_drawdown']:>+6.1%}  "
          f"final ${m_actual['final_equity']:>9,.0f}")

    print(f"\n  After-tax final equity ($) by tax scenario:")
    print(f"  {'Scenario':40s}  {'Shares':>10s}  {'Fut 1.5x':>10s}  "
          f"{'Fut 2.0x':>10s}  {'Actual':>10s}")

    results = {}
    for tax in TAX_SCENARIOS:
        at_shares = after_tax_final(m_shares["final_equity"], start_capital, tax.shares_rate)
        at_15 = after_tax_final(m_15["final_equity"], start_capital, tax.futures_rate)
        at_20 = after_tax_final(m_20["final_equity"], start_capital, tax.futures_rate)
        at_actual = after_tax_final(m_actual["final_equity"], start_capital, tax.futures_rate)
        print(f"  {tax.label:40s}  ${at_shares:>8,.0f}  ${at_15:>8,.0f}  "
              f"${at_20:>8,.0f}  ${at_actual:>8,.0f}")
        results[tax.label] = {
            "shares": at_shares, "fut_15": at_15, "fut_20": at_20,
            "actual": at_actual,
        }

    base = TAX_SCENARIOS[0]
    print(f"\n  After-tax CAGR ({base.label}):")
    print(f"    Shares (1x):       {cagr(after_tax_final(m_shares['final_equity'], start_capital, base.shares_rate), start_capital, years):>+5.1%}")
    print(f"    Futures 1.5x:      {cagr(after_tax_final(m_15['final_equity'], start_capital, base.futures_rate), start_capital, years):>+5.1%}")
    print(f"    Futures 2.0x:      {cagr(after_tax_final(m_20['final_equity'], start_capital, base.futures_rate), start_capital, years):>+5.1%}")
    print(f"    {actual_label}: {cagr(after_tax_final(m_actual['final_equity'], start_capital, base.futures_rate), start_capital, years):>+5.1%}")

    return {
        "label": label, "years": years, "bah": bah,
        "m_shares": m_shares, "m_15": m_15, "m_20": m_20,
        "tax_results": results,
    }


def deployment_feasibility_note(start_capital: float, contract: str,
                                target_leverage: float, current_index_level: float):
    spec = SPECS[contract]
    target_notional = start_capital * target_leverage
    one_contract_notional = current_index_level * spec["multiplier"]
    contracts_at_target = target_notional / one_contract_notional
    one_contract_leverage = one_contract_notional / start_capital
    return {
        "target_notional": target_notional,
        "one_contract_notional": one_contract_notional,
        "contracts_at_target": contracts_at_target,
        "one_contract_leverage": one_contract_leverage,
    }


def main() -> int:
    start_capital = 8000.0
    print(f"# Leverage-targeted BAH-on-trend  —  $${start_capital:,.0f} starting capital")
    print("# Vehicles: shares (1x), MNQ futures (1.5x and 2.0x targets), MES futures (1.5x and 2.0x)")
    print("# Roll cost: 8 bps/yr scaled by leverage. Sortino: standard formula.")
    print("# Tax: federal only (Texas, no state). 4 scenarios.\n")

    periods = [
        ("2018-2026 (in-sample)",     date(2018, 1, 1), date(2026, 4, 15)),
        ("2010-2017 (held-out)",      date(2010, 1, 1), date(2017, 12, 31)),
        ("2000-2009 (regime shift)",  date(2000, 9, 18), date(2009, 12, 31)),
    ]

    print("\n" + "#" * 100)
    print("# NDX / MNQ analysis")
    print("#" * 100)
    nq_results = {}
    for label, s, e in periods:
        nq_results[label] = run_period(label, s, e, "MNQ", start_capital)

    print("\n" + "#" * 100)
    print("# SPX / MES analysis")
    print("#" * 100)
    es_results = {}
    for label, s, e in periods:
        es_results[label] = run_period(label, s, e, "MES", start_capital)

    # Deployment feasibility at $8k
    print("\n" + "=" * 100)
    print("DEPLOYMENT FEASIBILITY AT $8K (current index levels ~April 2026)")
    print("=" * 100)

    for contract, idx_level in [("MNQ", 20000), ("MES", 5800)]:
        print(f"\n{contract} (index ~${idx_level}):")
        for L in (1.5, 2.0):
            f = deployment_feasibility_note(start_capital, contract, L, idx_level)
            print(f"  {L}x target:  notional ${f['target_notional']:,.0f}  |  "
                  f"1 {contract} = ${f['one_contract_notional']:,.0f} notional  |  "
                  f"contracts to target: {f['contracts_at_target']:.2f}  |  "
                  f"1-contract leverage: {f['one_contract_leverage']:.1f}x")
        print(f"  Note: smallest whole-contract position = 1 = "
              f"{(idx_level * SPECS[contract]['multiplier'] / start_capital):.1f}x leverage")

    return 0


if __name__ == "__main__":
    sys.exit(main())

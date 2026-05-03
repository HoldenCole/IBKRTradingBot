"""Wash-sale risk analyzer for the BAH-on-trend strategy.

Simulates the historical QQQ trades produced by the 50/200 SMA + Convention 2
(MOC) strategy and identifies which sells trigger the IRS wash-sale rule.

Wash-sale rule (IRC §1091):
  If a security is sold at a loss AND a "substantially identical" security
  is bought within 30 days before OR after the sale (a 61-day window
  centered on the sale), the loss is DISALLOWED for current-year tax
  purposes. The disallowed loss is added to the cost basis of the
  replacement shares.

Long-term economic effect:
  The loss is deferred, not eliminated. When the replacement shares are
  eventually sold (without another wash-sale trigger), the previously-
  disallowed loss is realized via the higher cost basis.

  Material concerns are:
    1. Tax-year boundary crossings — a wash sale in December that defers
       a loss into next year shifts $X of deduction by one year.
    2. Long-term holding-period extension — disallowed wash-sale losses
       inherit the holding period of the prior lot, potentially flipping
       what would have been STCL into LTCL.
    3. Record-keeping burden — basis adjustments must be tracked.

For our strategy:
  - On a signal flip OFF→ON within 30 days (i.e., during a whipsaw),
    the exit-day sale + re-entry constitutes a wash sale IF the exit was
    at a loss.
  - Round trips in profit don't trigger wash-sale rules (rule applies
    only to losses).

This analyzer:
  - Reconstructs the historical trade ledger
  - Computes per-trade P&L (Conv 2 timing)
  - Detects wash-sale triggers
  - Quantifies the dollar impact and tax-year-crossing risk
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.data import yahoo


def filter_on_flags(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    smaf = close.rolling(fast, min_periods=fast).mean()
    smas = close.rolling(slow, min_periods=slow).mean()
    return ((close > smaf) & (smaf > smas)).fillna(False)


@dataclass
class Trade:
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_dollars: float
    hold_days: int

    @property
    def is_loss(self) -> bool:
        return self.pnl_dollars < 0


def reconstruct_trades(close: pd.Series, flags: pd.Series,
                       start_capital: float = 8000.0) -> list[Trade]:
    """Reconstruct the trade ledger using Convention 2 (MOC) timing.

    Position is held from close[t-1] (when signal flipped ON) to close[t]
    (when signal flipped OFF). One ON segment = one trade.
    """
    trades: list[Trade] = []
    in_pos = False
    entry_date = None
    entry_price = None
    capital = start_capital
    shares = 0.0

    shifted = flags.shift(1).fillna(False).astype(bool)
    rets = close.pct_change().fillna(0.0)

    # State transitions: when shifted[t] differs from shifted[t-1]
    prev = False
    for ts, sig in shifted.items():
        sig = bool(sig)
        c = float(close.loc[ts])
        if sig and not prev:
            # Just entered (signal flipped ON yesterday — we're long since today)
            in_pos = True
            entry_date = ts.date()
            entry_price = c
            shares = capital / c
        elif not sig and prev:
            # Just exited (signal flipped OFF — we sell at today's close per Conv 2)
            exit_date = ts.date()
            exit_price = c
            pnl_pct = (exit_price / entry_price - 1.0)
            pnl_dollars = shares * (exit_price - entry_price)
            hold_days = (exit_date - entry_date).days
            trades.append(Trade(
                entry_date=entry_date, exit_date=exit_date,
                entry_price=entry_price, exit_price=exit_price,
                pnl_pct=pnl_pct, pnl_dollars=pnl_dollars,
                hold_days=hold_days,
            ))
            capital = shares * exit_price
            shares = 0.0
            in_pos = False
        prev = sig

    return trades


def detect_wash_sales(trades: list[Trade]) -> list[dict]:
    """Apply the wash-sale rule: a sell at a loss that has a buy of the
    same security within 30 days (before or after) is a wash sale.

    For our strategy, the only buys are the strategy's own re-entries.
    So we check: for each loss trade, was there another entry within
    30 days after the exit (or 30 days before the entry, but that's the
    same trade so not relevant)?
    """
    findings = []
    for i, t in enumerate(trades):
        if not t.is_loss:
            continue
        # Look for next entry within 30 days after exit
        for j in range(i + 1, len(trades)):
            next_entry = trades[j].entry_date
            days_to_next = (next_entry - t.exit_date).days
            if days_to_next > 30:
                break
            if 0 <= days_to_next <= 30:
                findings.append({
                    "loss_trade_idx": i,
                    "exit_date": t.exit_date,
                    "loss_dollars": t.pnl_dollars,
                    "loss_pct": t.pnl_pct,
                    "rebuy_date": next_entry,
                    "days_between": days_to_next,
                    "rebuy_trade_idx": j,
                    "tax_year_crossing": (t.exit_date.year != next_entry.year),
                })
                break
    return findings


def main() -> int:
    print("Fetching QQQ for wash-sale analysis...")
    df = yahoo.daily("QQQ", "2000-01-01", "2026-04-15")
    close = df["close"]
    flags = filter_on_flags(close)

    trades = reconstruct_trades(close, flags, start_capital=8000.0)
    print(f"\nTotal trades reconstructed: {len(trades)}")
    n_loss = sum(1 for t in trades if t.is_loss)
    n_win = len(trades) - n_loss
    avg_win = sum(t.pnl_dollars for t in trades if not t.is_loss) / max(1, n_win)
    avg_loss = sum(t.pnl_dollars for t in trades if t.is_loss) / max(1, n_loss)
    avg_hold = sum(t.hold_days for t in trades) / max(1, len(trades))
    print(f"  Wins: {n_win} (avg ${avg_win:+.0f})")
    print(f"  Losses: {n_loss} (avg ${avg_loss:+.0f})")
    print(f"  Avg hold: {avg_hold:.0f} calendar days")

    findings = detect_wash_sales(trades)
    print(f"\nWash-sale candidates detected: {len(findings)} of {n_loss} loss trades")
    print(f"  ({len(findings) / max(1, n_loss) * 100:.0f}% of all loss trades)")

    if findings:
        print(f"\n{'#':>2s}  {'Exit date':>10s}  {'Re-buy date':>11s}  "
              f"{'Days':>4s}  {'Loss $':>10s}  {'Loss %':>7s}  {'Cross yr?':>9s}")
        for i, f in enumerate(findings):
            yr = "YES" if f["tax_year_crossing"] else "no"
            print(f"  {i:>2d}  {f['exit_date'].isoformat():>10s}  "
                  f"{f['rebuy_date'].isoformat():>11s}  "
                  f"{f['days_between']:>4d}  ${f['loss_dollars']:>+8,.0f}  "
                  f"{f['loss_pct'] * 100:>+5.1f}%   {yr:>9s}")

    # ----- Aggregate impact -----
    print("\n" + "=" * 80)
    print("# Wash-sale impact analysis")
    print("=" * 80)

    total_loss_dollars = sum(t.pnl_dollars for t in trades if t.is_loss)
    total_wash_loss_dollars = sum(f["loss_dollars"] for f in findings)
    cross_yr_count = sum(1 for f in findings if f["tax_year_crossing"])
    cross_yr_dollars = sum(f["loss_dollars"] for f in findings if f["tax_year_crossing"])

    print(f"\n  Total realized losses (all trades): ${total_loss_dollars:+,.0f}")
    print(f"  Of which subject to wash-sale rule: ${total_wash_loss_dollars:+,.0f}")
    if total_loss_dollars < 0:
        pct = total_wash_loss_dollars / total_loss_dollars * 100
        print(f"  → {pct:.0f}% of all loss dollars are wash-sale-affected")
    print(f"\n  Tax-year-crossing wash sales: {cross_yr_count} ({cross_yr_dollars:+,.0f} dollars)")
    print(f"    These defer the loss recognition by 1+ year.")
    print(f"  Same-year wash sales: {len(findings) - cross_yr_count}")
    print(f"    These have no NET tax impact (loss recognized when basis adjusts).")

    # ----- Whipsaw clusters -----
    print("\n" + "=" * 80)
    print("# Whipsaw periods (≥ 2 wash sales within 90 days)")
    print("=" * 80)

    if len(findings) >= 2:
        clusters = []
        cur_cluster = [findings[0]]
        for f in findings[1:]:
            if (f["exit_date"] - cur_cluster[-1]["exit_date"]).days <= 90:
                cur_cluster.append(f)
            else:
                if len(cur_cluster) >= 2:
                    clusters.append(cur_cluster)
                cur_cluster = [f]
        if len(cur_cluster) >= 2:
            clusters.append(cur_cluster)

        if clusters:
            for cl in clusters:
                start_d = cl[0]["exit_date"]
                end_d = cl[-1]["exit_date"]
                total = sum(c["loss_dollars"] for c in cl)
                print(f"  {start_d} → {end_d}  ({len(cl)} wash sales, total ${total:+,.0f})")
        else:
            print("  No clustered wash-sale periods detected.")
    else:
        print("  Insufficient wash sales to cluster.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Turn the latest ledger row into a shopping list for a given account size.

The matrix outputs percent weights, so the system scales to any equity:
dollar target = weight x account value. This CLI does that multiplication
and adds share quantities from the latest close, so a monthly rotation or
contribution deploy is copy-paste instead of mental math.

Usage:
    python -m src.portfolio.order_calc --tier VAGG --equity 11000
    python -m src.portfolio.order_calc --tier VAGG --equity 12500 \
        --held TQQQ=3300 --held ERX=3465 --held GDX=1733 --held DBC=2503

With --held positions (current market value per ticker), the output is the
DELTA to trade per ticker (contribution-first rebalancing: positive = buy,
negative = sell only if drift exceeds the 5pp band).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.data.yahoo import fetch_yahoo_daily
from src.portfolio.paper_logger import LEDGER_PATH, load_ledger

DRIFT_BAND = 0.05  # sell-to-rebalance only beyond this (DEPLOYMENT.md)


def latest_allocations(path: Path = LEDGER_PATH) -> tuple[str, str, dict]:
    ledger = load_ledger(path)
    if ledger.empty:
        raise SystemExit("ledger is empty — run the paper logger first")
    row = ledger.iloc[-1]
    return str(row["month"]), str(row["quadrant"]), json.loads(row["allocations"])


def build_orders(
    weights: dict[str, float],
    equity: float,
    held: dict[str, float] | None = None,
) -> list[dict]:
    held = held or {}
    orders = []
    for ticker in sorted(set(weights) | set(held), key=lambda t: -weights.get(t, 0.0)):
        target = round(weights.get(ticker, 0.0) * equity, 2)
        current = held.get(ticker, 0.0)
        delta = round(target - current, 2)
        drift = (current - target) / equity if equity else 0.0
        action = "BUY" if delta > 0 else "SELL" if delta < 0 else "HOLD"
        # inside the band, never sell — contribution-first rebalancing
        if action == "SELL" and abs(drift) < DRIFT_BAND and weights.get(ticker, 0.0) > 0:
            action, delta = "HOLD", 0.0
        orders.append(
            {"ticker": ticker, "weight": weights.get(ticker, 0.0),
             "target": target, "current": current, "delta": delta, "action": action}
        )
    return orders


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", required=True, choices=["CONS", "MOD", "AGG", "VAGG"])
    ap.add_argument("--equity", type=float, required=True,
                    help="total account value in dollars (cash + positions)")
    ap.add_argument("--held", action="append", default=[], metavar="TICKER=DOLLARS",
                    help="current market value of a held position; repeatable")
    ap.add_argument("--no-prices", action="store_true",
                    help="skip price fetch (dollar amounts only)")
    args = ap.parse_args()

    held = {}
    for spec in args.held:
        ticker, _, val = spec.partition("=")
        held[ticker.upper()] = float(val)

    month, quadrant, allocs = latest_allocations()
    weights = allocs[args.tier]
    orders = build_orders(weights, args.equity, held)

    print(f"{month} · {quadrant} · {args.tier} · equity ${args.equity:,.2f}")
    for o in orders:
        line = (f"  {o['action']:<4} {o['ticker']:<5} target {o['weight']:>6.2%}"
                f" = ${o['target']:>10,.2f}")
        if held:
            line += f"  (held ${o['current']:>10,.2f}, trade ${o['delta']:>+10,.2f})"
        if not args.no_prices and o["action"] != "HOLD":
            try:
                px = float(fetch_yahoo_daily(o["ticker"], rng="1mo").iloc[-1])
                line += f"  ~{abs(o['delta']) / px:.4f} sh @ ${px:,.2f}"
            except Exception:
                line += "  (price unavailable — use dollar amount)"
        print(line)
    invested = sum(o["target"] for o in orders)
    print(f"  cash remainder: ${args.equity - invested:,.2f}")


if __name__ == "__main__":
    main()

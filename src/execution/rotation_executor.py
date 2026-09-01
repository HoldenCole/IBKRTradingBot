"""Hands-off execution loop for the monthly quadrant rotation.

Flow (one run, state-based and therefore idempotent):
  1. Safety gates: HALT file, ledger row for the current month (runs the
     paper logger if the Routine hasn't yet), no open orders in the
     rotation universe.
  2. Read live account state (cash + positions) from the broker.
  3. Diff against the latest ledger row's tier weights via
     order_calc.build_orders — the same math as the manual runbook:
     contribution-first, 5pp drift band, full exit for departed tickers.
  4. Execute SELLs first (frees cash), then BUYs. Limit at mid, repriced
     through the spread if unfilled. Every order appended to
     paper/executions.csv.

Safety model:
  - Dry-run is the default; --execute is required to send orders, and a
    live (non-paper) session additionally requires MODE=live plus
    --i-understand-the-risk, mirroring src/main.py.
  - Only tickers in matrix.all_tickers() plus historical ledger holdings
    are ever traded. Anything else in the account is ignored and does
    not count toward rotation equity — the rotation manages its own
    sleeve only.
  - A HALT file in the repo root (or EXECUTION_HALT=1) stops everything.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from loguru import logger

from src.portfolio import matrix
from src.portfolio.order_calc import build_orders
from src.portfolio.paper_logger import LEDGER_PATH, load_ledger, run_paper_log

REPO_ROOT = Path(__file__).resolve().parents[2]
HALT_FILE = REPO_ROOT / "HALT"
EXECUTIONS_PATH = REPO_ROOT / "paper" / "executions.csv"

MIN_ORDER_USD = 50.0        # skip dust trades (except full exits)
FILL_TIMEOUT_S = 120.0      # per order, before repricing through the spread
CROSS_PCT = 0.001           # marketable-limit cushion when repricing


class ExecutionAborted(Exception):
    """A safety gate failed — nothing was traded after this point."""


@dataclass
class Position:
    quantity: float
    market_value: float


@dataclass
class OrderResult:
    ticker: str
    action: str
    dollars: float
    quantity: float
    limit: float
    status: str          # "filled" | "partial" | "unfilled" | "dry_run"
    fill_avg: float = 0.0


class Broker(Protocol):
    """What the executor needs from any broker implementation."""

    def cash(self) -> float: ...
    def positions(self) -> dict[str, Position]: ...
    def quote(self, ticker: str) -> tuple[float, float]:
        """(bid, ask); implementations may fall back to (last, last)."""
        ...
    def open_order_tickers(self) -> set[str]: ...
    def execute_limit(
        self, ticker: str, action: str, quantity: float, limit: float,
        timeout_s: float,
    ) -> OrderResult: ...


def rotation_universe(ledger_path: Path = LEDGER_PATH) -> set[str]:
    """Everything the system may ever hold: the matrix's concrete tickers
    plus anything a historical ledger row allocated (covers rotations out
    of tickers that later matrix versions dropped)."""
    universe = set(matrix.all_tickers())
    ledger = load_ledger(ledger_path)
    for allocs in ledger.get("allocations", []):
        for weights in json.loads(allocs).values():
            universe.update(weights)
    return universe


def current_month_row(today: date, ledger_path: Path = LEDGER_PATH):
    """Return the ledger row for today's month, running the logger once
    if the scheduled Routine hasn't produced it yet."""
    month = f"{today.year:04d}-{today.month:02d}"
    ledger = load_ledger(ledger_path)
    if ledger.empty or str(ledger.iloc[-1]["month"]) != month:
        logger.info(f"No ledger row for {month} yet — running the paper logger")
        run_paper_log(ledger_path)
        ledger = load_ledger(ledger_path)
    if ledger.empty or str(ledger.iloc[-1]["month"]) != month:
        raise ExecutionAborted(f"could not produce a ledger row for {month}")
    return ledger.iloc[-1]


def check_halt() -> None:
    if HALT_FILE.exists():
        raise ExecutionAborted(f"HALT file present at {HALT_FILE} — remove it to resume")
    if os.getenv("EXECUTION_HALT", "").strip() in ("1", "true", "yes"):
        raise ExecutionAborted("EXECUTION_HALT is set — unset it to resume")


def log_execution(mode: str, month: str, result: OrderResult,
                  path: Path = EXECUTIONS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.writer(fh)
        if is_new:
            writer.writerow(["logged_at", "month", "mode", "ticker", "action",
                             "dollars", "quantity", "limit", "status", "fill_avg"])
        writer.writerow([
            datetime.now(timezone.utc).isoformat(timespec="seconds"), month, mode,
            result.ticker, result.action, f"{result.dollars:.2f}",
            f"{result.quantity:.4f}", f"{result.limit:.2f}",
            result.status, f"{result.fill_avg:.2f}",
        ])


@dataclass
class RunReport:
    month: str
    tier: str
    mode: str
    equity: float
    results: list[OrderResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def run_rotation(
    broker: Broker,
    tier: str,
    *,
    execute: bool = False,
    today: date | None = None,
    ledger_path: Path = LEDGER_PATH,
    executions_path: Path = EXECUTIONS_PATH,
) -> RunReport:
    today = today or date.today()
    mode = "execute" if execute else "dry_run"

    check_halt()
    row = current_month_row(today, ledger_path)
    month = str(row["month"])
    weights: dict[str, float] = json.loads(row["allocations"])[tier]
    universe = rotation_universe(ledger_path)

    pending = broker.open_order_tickers() & universe
    if pending:
        raise ExecutionAborted(f"open orders already working for {sorted(pending)} — "
                               "resolve them before running")

    all_positions = broker.positions()
    held = {t: p.market_value for t, p in all_positions.items() if t in universe}
    foreign = sorted(set(all_positions) - set(held))
    if foreign:
        logger.warning(f"Ignoring non-rotation positions (not traded, not counted): {foreign}")
    equity = broker.cash() + sum(held.values())
    if equity <= 0:
        raise ExecutionAborted(f"rotation equity is ${equity:,.2f} — nothing to do")

    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.005:
        raise ExecutionAborted(f"{tier} weights sum to {weight_sum:.4f}, not 1.0 — bad ledger row?")

    report = RunReport(month=month, tier=tier, mode=mode, equity=equity)
    orders = build_orders(weights, equity, held)

    executable = []
    for o in orders:
        if o["action"] == "HOLD":
            continue
        full_exit = o["ticker"] not in weights
        if abs(o["delta"]) < MIN_ORDER_USD and not full_exit:
            report.skipped.append(f"{o['ticker']}: ${o['delta']:+,.2f} below ${MIN_ORDER_USD:.0f} minimum")
            continue
        executable.append(o)

    total_buys = sum(o["delta"] for o in executable if o["action"] == "BUY")
    total_sells = sum(-o["delta"] for o in executable if o["action"] == "SELL")
    if total_buys > equity * 1.001:
        raise ExecutionAborted(f"total buys ${total_buys:,.2f} exceed equity ${equity:,.2f}")
    if total_sells > sum(held.values()) * 1.001:
        raise ExecutionAborted(f"total sells ${total_sells:,.2f} exceed held value "
                               f"${sum(held.values()):,.2f}")

    # sells first: rotation exits fund the buys
    for phase in ("SELL", "BUY"):
        for o in (x for x in executable if x["action"] == phase):
            bid, ask = broker.quote(o["ticker"])
            mid = round((bid + ask) / 2, 2)
            if mid <= 0:
                raise ExecutionAborted(f"bad quote for {o['ticker']}: bid={bid} ask={ask}")
            if phase == "SELL" and o["ticker"] not in weights:
                qty = all_positions[o["ticker"]].quantity  # full exit by shares
            else:
                qty = round(abs(o["delta"]) / mid, 4)
            if not execute:
                result = OrderResult(o["ticker"], phase, abs(o["delta"]), qty, mid, "dry_run")
                logger.info(f"DRY-RUN {phase} {qty} {o['ticker']} @ ~{mid:.2f} (${abs(o['delta']):,.2f})")
            else:
                result = broker.execute_limit(o["ticker"], phase, qty, mid, FILL_TIMEOUT_S)
            report.results.append(result)
            log_execution(mode, month, result, executions_path)

    unfilled = [r for r in report.results if r.status in ("unfilled", "partial")]
    if unfilled:
        logger.warning(f"{len(unfilled)} orders not fully filled: "
                       f"{[(r.ticker, r.status) for r in unfilled]} — "
                       "the next run recomputes from live state and finishes the job")
    logger.info(f"{month} {tier} [{mode}] equity ${equity:,.2f}: "
                f"{len(report.results)} orders, {len(report.skipped)} skipped")
    return report


# --------------------------------------------------------------------------
# IB implementation — thin adapter over the existing broker plumbing.
# --------------------------------------------------------------------------

class IBBroker:
    """Adapter over src.broker.connection.IBConnection for the executor."""

    def __init__(self, settings):
        from src.broker.connection import IBConnection

        self.conn = IBConnection(settings)
        self.conn.connect()
        self.ib = self.conn.ib
        self._contracts: dict[str, object] = {}

    def _contract(self, ticker: str):
        from ib_insync import Stock

        if ticker not in self._contracts:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)
            self._contracts[ticker] = contract
        return self._contracts[ticker]

    def cash(self) -> float:
        for value in self.ib.accountValues():
            if value.tag == "TotalCashValue" and value.currency == "USD":
                return float(value.value)
        raise ExecutionAborted("could not read TotalCashValue from account")

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for item in self.ib.portfolio():
            out[item.contract.symbol] = Position(
                quantity=float(item.position), market_value=float(item.marketValue))
        return out

    def quote(self, ticker: str) -> tuple[float, float]:
        contract = self._contract(ticker)
        tick = self.ib.reqMktData(contract, "", snapshot=True)
        self.ib.sleep(2)
        bid, ask = float(tick.bid or 0), float(tick.ask or 0)
        if bid <= 0 or ask <= 0:
            last = float(tick.last or tick.close or 0)
            bid = ask = last
        self.ib.cancelMktData(contract)
        return bid, ask

    def open_order_tickers(self) -> set[str]:
        return {t.contract.symbol for t in self.ib.openTrades()}

    def execute_limit(self, ticker: str, action: str, quantity: float,
                      limit: float, timeout_s: float) -> OrderResult:
        from ib_insync import LimitOrder

        contract = self._contract(ticker)
        dollars = quantity * limit
        trade = self.ib.placeOrder(contract, LimitOrder(action, quantity, limit, tif="DAY"))
        logger.info(f"ORDER {action} {quantity} {ticker} @ {limit:.2f}")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not trade.isDone():
            self.ib.sleep(1)
        if not trade.isDone():
            # reprice through the spread once, then give the remainder up
            self.ib.cancelOrder(trade.order)
            self.ib.sleep(2)
            bid, ask = self.quote(ticker)
            cross = round(ask * (1 + CROSS_PCT) if action == "BUY"
                          else bid * (1 - CROSS_PCT), 2)
            remaining = quantity - float(trade.orderStatus.filled or 0)
            if remaining > 0:
                logger.warning(f"Repricing {ticker} {action} through spread @ {cross:.2f}")
                trade = self.ib.placeOrder(
                    contract, LimitOrder(action, remaining, cross, tif="DAY"))
                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline and not trade.isDone():
                    self.ib.sleep(1)
        filled = float(trade.orderStatus.filled or 0)
        status = ("filled" if trade.orderStatus.status == "Filled"
                  else "partial" if filled > 0 else "unfilled")
        return OrderResult(ticker, action, dollars, quantity, limit, status,
                           float(trade.orderStatus.avgFillPrice or 0))

    def disconnect(self) -> None:
        self.conn.disconnect()


def main() -> None:
    import argparse

    from src.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", required=True, choices=matrix.TIERS)
    ap.add_argument("--execute", action="store_true",
                    help="actually place orders (default: dry-run against the live account)")
    ap.add_argument("--i-understand-the-risk", action="store_true", dest="risk_ack")
    args = ap.parse_args()

    settings = load_settings()
    if args.execute and settings.is_live and not args.risk_ack:
        ap.error("MODE=live with --execute requires --i-understand-the-risk")

    broker = IBBroker(settings)
    try:
        run_rotation(broker, args.tier, execute=args.execute)
    finally:
        broker.disconnect()


if __name__ == "__main__":
    main()

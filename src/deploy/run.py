"""Daily-check orchestrator — `python -m src.deploy.run`.

Wires the deployment stack together for one daily run:

  1. Load config (baskets), state store (signal state), ledger (tax lots).
  2. Construct broker (Sim or IBKR) and alerter (SMTP from env or Capturing).
  3. Reconcile broker reality against the ledger. If discrepancies are
     found, halt: do not run signals, do not place trades.
  4. Run the daily check: pull closes, compute signals, detect flips.
  5. Pick the trading path:
     - --first-run: target-driven `plan_positioning` (initial allocation).
     - default:     flip-driven `plan_orders` (steady-state daily loop).
  6. Submit orders and immediately record any FILLED tickets into the
     ledger (MKT fills now; MOO fills are deferred — see KL-5).
  7. Build the per-basket portfolio report, append the equity-curve
     history, compute drawdown, and emit a daily-summary alert.
  8. Save state + ledger atomically.

Designed so the meaningful logic is testable WITHOUT the CLI: build an
`OrchestratorConfig` directly, call `run_once`, inspect the
`OrchestratorResult`. The CLI is a thin argparse wrapper.

KL-5 (known limitation, documented): for MOO orders against IBKR, the
fill lands at next-session open — after this orchestrator returns. The
current implementation records only tickets that are FILLED at the moment
we look. A pending-orders persistence layer (drain-on-startup) is needed
before the IBKR/MOO production path is safe; see reports/deployment/
QA_PASS_01.md when that gets added.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from src.deploy.alerts import (
    Alert, AlertSeverity, Alerter, CapturingAlerter, SmtpAlerter,
    alert_critical, alert_daily_summary, alert_for_order,
    alert_for_state_change,
)
from src.deploy.baskets import BasketConfig
from src.deploy.broker import (
    OrderState, OrderTicket, OrderType, StockBroker,
)
from src.deploy.daily_check import (
    CloseSeriesProvider, DailyCheckResult, run_daily_check,
)
from src.deploy.orders import (
    OFF_VEHICLE_SYMBOL, execute_plans, plan_orders, resolve_risk_symbol,
)
from src.deploy.pending import (
    DrainResult, PendingOrder, PendingOrderStore, drain_pending,
)
from src.deploy.portfolio import Ledger
from src.deploy.positioning import execute_positioning, plan_positioning
from src.deploy.reconcile import Reconciliation, reconcile_startup
from src.deploy.reporting import (
    EquityHistoryRow, PortfolioReport, append_daily_history,
    build_portfolio_report, compute_drawdown, format_report,
)
from src.deploy.signal_state import SignalState
from src.deploy.store import StateStore

_log = logging.getLogger(__name__)


# =====================================================================
# Result + config
# =====================================================================
@dataclass
class OrchestratorResult:
    """The outcome of one orchestrator run. The CLI converts this to an
    exit code; tests assert against its fields."""
    trading_date: date
    reconciliation: Reconciliation
    drain: DrainResult | None = None
    drained_fills: list[OrderTicket] = field(default_factory=list)
    daily_check: DailyCheckResult | None = None
    placed_tickets: list[OrderTicket] = field(default_factory=list)
    recorded_fills: list[OrderTicket] = field(default_factory=list)
    newly_pending: list[PendingOrder] = field(default_factory=list)
    report: PortfolioReport | None = None
    report_path: Path | None = None
    history_path: Path | None = None
    alerts: list[Alert] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""

    @property
    def exit_code(self) -> int:
        if self.errors or self.halted:
            return 1
        return 0


@dataclass
class OrchestratorConfig:
    """Everything `run_once` needs. Decoupled from argparse so the
    function is unit-testable."""
    cfg: BasketConfig
    store: StateStore
    ledger: Ledger
    broker: StockBroker
    provider: CloseSeriesProvider
    alerter: Alerter
    trading_date: date
    ledger_path: Path
    history_path: Path
    reports_dir: Path
    pending_store: PendingOrderStore | None = None
    first_run: bool = False
    order_type: OrderType = OrderType.MOO
    now_utc: datetime | None = None


# =====================================================================
# Helpers
# =====================================================================
def _strategy_to_basket(cfg: BasketConfig) -> dict[str, str]:
    out: dict[str, str] = {}
    for bid, b in cfg.baskets.items():
        for s in b.strategies:
            out[s.id] = bid
    return out


def _signal_states_now(store: StateStore) -> dict[str, SignalState]:
    return {sid: snap.state for sid, snap in store.all_snapshots().items()}


def _quotes_for_run(
    cfg: BasketConfig, daily: DailyCheckResult, nav: float,
    sgov_quote: float,
) -> dict[str, float]:
    """Quotes for sizing. The risk-asset price comes from the close used
    by the signal (so sizing and signal agree); SGOV is passed in
    (production reads it once at startup, the test sets it explicitly).
    """
    quotes: dict[str, float] = {OFF_VEHICLE_SYMBOL: sgov_quote}
    for basket in cfg.baskets.values():
        if not basket.enabled:
            continue
        for spec in basket.strategies:
            symbol = resolve_risk_symbol(spec, nav)
            snap = daily.snapshots.get(spec.id)
            if snap is None:
                continue
            quotes[symbol] = snap.close
    return quotes


def _record_fills_into_ledger(
    ledger: Ledger, tickets: Sequence[OrderTicket], trading_date: date,
) -> tuple[list[OrderTicket], list[OrderTicket]]:
    """Apply each FILLED ticket to the ledger. Returns (recorded, deferred)
    where deferred = tickets we couldn't apply (still SUBMITTED, REJECTED,
    or missing a strategy_id / fill price).

    Deferred MOO/SUBMITTED tickets are reported back; the orchestrator
    today does not persist them across runs (KL-5). The next-day startup's
    reconcile will catch any positions that materialize but weren't
    recorded — operator addresses them then.
    """
    recorded: list[OrderTicket] = []
    deferred: list[OrderTicket] = []
    for t in tickets:
        if t.state != OrderState.FILLED or t.avg_fill_price is None:
            deferred.append(t)
            continue
        if not t.strategy_id:
            _log.warning("ticket %s has no strategy_id; skipping ledger "
                         "record", t.order_id)
            deferred.append(t)
            continue
        if t.side == "BUY":
            ledger.record_buy(
                strategy_id=t.strategy_id, symbol=t.symbol,
                quantity=t.filled_quantity, price=t.avg_fill_price,
                trade_date=trading_date)
        else:
            ledger.record_sell(
                strategy_id=t.strategy_id, symbol=t.symbol,
                quantity=t.filled_quantity, price=t.avg_fill_price,
                trade_date=trading_date)
        recorded.append(t)
    return recorded, deferred


def _equity_history_row(
    report: PortfolioReport, trading_date: date,
) -> EquityHistoryRow:
    basket_mv = {b.basket_id: b.market_value for b in report.baskets}
    basket_mv["cash"] = report.cash
    return EquityHistoryRow(
        trading_date=trading_date, nav=report.nav, basket_mv=basket_mv)


def _save_report(report: PortfolioReport, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    p = reports_dir / f"report_{report.as_of.isoformat()}.txt"
    p.write_text(format_report(report))
    return p


# =====================================================================
# Core orchestrator
# =====================================================================
async def run_once(c: OrchestratorConfig) -> OrchestratorResult:
    """One end-to-end run. Pure async; all I/O via injected collaborators."""
    result = OrchestratorResult(trading_date=c.trading_date,
                                reconciliation=Reconciliation())

    # --- Step 0: drain pending orders (BEFORE reconcile) ---
    # Overnight MOO orders placed by a prior run fill at this session's open.
    # Recording those fills into the ledger now means reconcile compares a
    # consistent picture instead of halting on the expected settlement.
    if c.pending_store is not None:
        drain = await drain_pending(
            c.pending_store, c.broker, c.ledger, c.trading_date)
        result.drain = drain
        result.drained_fills = drain.recorded
        result.errors.extend(drain.errors)
        # Surface terminal (rejected/cancelled overnight) and unknown orders.
        for t in drain.terminal:
            if t.state == OrderState.REJECTED:
                a = alert_critical(
                    f"Overnight order REJECTED: {t.side} {t.quantity:g} {t.symbol}",
                    f"order_id={t.order_id} strategy={t.strategy_id} "
                    f"note={t.note}")
                c.alerter.send(a)
                result.alerts.append(a)
        for po in drain.unknown:
            a = alert_critical(
                f"Pending order unknown to broker: {po.order_id}",
                f"{po.side} {po.quantity:g} {po.symbol} "
                f"(strategy={po.strategy_id}, placed {po.placed_trading_date}). "
                f"Broker has no record — investigate before next run.")
            c.alerter.send(a)
            result.alerts.append(a)
        # Persist the ledger (overnight fills) and the trimmed pending set
        # so reconcile and any crash-after-this see the resolved state.
        c.ledger.save(c.ledger_path)
        c.pending_store.save()

    # --- Step 1: reconcile broker vs ledger ---
    reconciliation = await reconcile_startup(c.broker, c.ledger)
    result.reconciliation = reconciliation
    if not reconciliation.safe_to_trade and not c.first_run:
        # On first run, the ledger is empty and the broker may already
        # hold residual positions — that's normal. We tolerate it. After
        # first run, any drift is a real discrepancy that halts trading.
        result.halted = True
        result.halt_reason = reconciliation.summary
        alert = alert_critical(
            "Reconciliation halt — trading paused",
            f"{reconciliation.summary}\n\nFindings:\n" +
            "\n".join(f"  - {f.detail}" for f in reconciliation.findings))
        c.alerter.send(alert)
        result.alerts.append(alert)
        return result

    # --- Step 2: daily check ---
    daily = run_daily_check(
        cfg=c.cfg, store=c.store, provider=c.provider,
        trading_date=c.trading_date, now_utc=c.now_utc, persist=True)
    result.daily_check = daily

    # State-change alerts (one per flip)
    for change in daily.changes:
        if not change.is_flip:
            continue
        snap = daily.snapshots.get(change.strategy_id)
        if snap is None:
            continue
        a = alert_for_state_change(change, snap)
        c.alerter.send(a)
        result.alerts.append(a)

    # --- Step 3: build quotes for sizing ---
    nav = await c.broker.nav()
    sgov_quote = await _get_sgov_quote(c.broker)
    quotes = _quotes_for_run(c.cfg, daily, nav=nav, sgov_quote=sgov_quote)

    # --- Step 4: plan + execute orders ---
    placed: list[OrderTicket] = []
    if c.first_run:
        states = {sid: snap.state for sid, snap in daily.snapshots.items()}
        pplan = plan_positioning(c.cfg, c.ledger, nav, quotes, states)
        if not pplan.is_empty:
            ex = await execute_positioning(pplan, c.broker, c.order_type)
            placed = ex.submitted
            result.errors.extend(ex.errors)
    else:
        oplans = await plan_orders(daily.changes, c.cfg, c.broker, quotes,
                                   ledger=c.ledger)
        if oplans:
            ex = await execute_plans(oplans, c.broker, c.order_type)
            placed = ex.submitted
            result.errors.extend(ex.errors)
    result.placed_tickets = placed

    # Per-order alerts (rejected -> CRITICAL, others -> INFO)
    for t in placed:
        a = alert_for_order(t)
        c.alerter.send(a)
        result.alerts.append(a)

    # --- Step 5: record synchronous fills; persist deferred as pending ---
    recorded, deferred = _record_fills_into_ledger(
        c.ledger, placed, c.trading_date)
    result.recorded_fills = recorded
    # Deferred SUBMITTED orders (MOO awaiting next-session open) are
    # persisted so the next run's drain (Step 0) can resolve them. Without
    # a pending store they're lost and would surface as ORPHAN_POSITIONs.
    if c.pending_store is not None:
        for t in deferred:
            if t.state == OrderState.SUBMITTED and t.strategy_id:
                po = PendingOrder.from_ticket(t, c.trading_date, c.now_utc)
                c.pending_store.add(po)
                result.newly_pending.append(po)
        c.pending_store.save()
    elif any(t.state == OrderState.SUBMITTED for t in deferred):
        _log.warning("%d order(s) left SUBMITTED but no pending_store "
                     "configured; they will not be drained next run",
                     sum(1 for t in deferred if t.state == OrderState.SUBMITTED))
    c.ledger.save(c.ledger_path)

    # --- Step 6: portfolio report + history + drawdown ---
    fresh_nav = await c.broker.nav()
    report = build_portfolio_report(
        c.cfg, c.ledger, quotes, fresh_nav, c.trading_date)
    result.report = report
    result.report_path = _save_report(report, c.reports_dir)
    append_daily_history(
        c.history_path, _equity_history_row(report, c.trading_date),
        basket_ids=sorted(c.cfg.baskets.keys()))
    result.history_path = c.history_path

    # --- Step 7: daily summary alert ---
    summary = alert_daily_summary(
        c.trading_date, daily.snapshots,
        flip_count=sum(1 for ch in daily.changes if ch.is_flip),
        warnings=daily.warnings)
    c.alerter.send(summary)
    result.alerts.append(summary)
    return result


def _seed_sim_broker_quotes(
    broker, cfg: BasketConfig, provider: CloseSeriesProvider,
    trading_date: date, nominal_equity: float,
) -> None:
    """The SimStockBroker is a test double with no market data. For the
    `--broker sim` CLI path to be runnable (smoke-testing the wiring against
    live Yahoo closes), seed it with the latest close per risk symbol plus a
    fixed SGOV quote. The production path uses `--broker ibkr`, which sources
    quotes from the market and needs no seeding."""
    for basket in cfg.baskets.values():
        if not basket.enabled:
            continue
        for spec in basket.strategies:
            symbol = resolve_risk_symbol(spec, nominal_equity)
            try:
                closes = provider.closes(spec.asset, trading_date, 5)
                if closes is None or closes.empty:
                    continue
                px = float(closes.iloc[-1])
            except Exception as exc:
                _log.warning("could not seed sim quote for %s: %r", symbol, exc)
                continue
            broker.set_quote(symbol, px)
            broker.set_open_price(symbol, px)
    broker.set_quote(OFF_VEHICLE_SYMBOL, 100.0)
    broker.set_open_price(OFF_VEHICLE_SYMBOL, 100.0)


async def _get_sgov_quote(broker: StockBroker) -> float:
    """SGOV trades in a tight band near $100. The Sim broker stores quotes
    directly; the IBKR adapter will need a separate `last_price` call once
    the integration is built — for now we fall back to $100 if the broker
    can't tell us, with a warning."""
    sim_quotes = getattr(broker, "_quotes", None)
    if isinstance(sim_quotes, dict) and OFF_VEHICLE_SYMBOL in sim_quotes:
        return float(sim_quotes[OFF_VEHICLE_SYMBOL])
    _log.warning("broker did not expose SGOV quote; defaulting to 100.0")
    return 100.0


# =====================================================================
# CLI
# =====================================================================
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m src.deploy.run",
        description="Daily-check orchestrator for the IBKR trading bot.")
    p.add_argument("--config", type=Path,
                   default=Path("config/baskets.json"))
    p.add_argument("--state", type=Path, default=Path("state/signal_state.json"))
    p.add_argument("--ledger", type=Path, default=Path("state/ledger.json"))
    p.add_argument("--pending", type=Path, default=Path("state/pending.json"))
    p.add_argument("--history", type=Path, default=Path("state/history.csv"))
    p.add_argument("--reports-dir", type=Path, default=Path("state/reports"))
    p.add_argument("--trading-date", type=date.fromisoformat, default=None,
                   help="YYYY-MM-DD; default = today in US/Eastern")
    p.add_argument("--first-run", action="store_true",
                   help="Use target-driven positioning instead of flip-driven orders")
    p.add_argument("--broker", choices=["sim", "ibkr"], default="sim")
    p.add_argument("--sim-cash", type=float, default=8000.0,
                   help="Starting cash for the sim broker")
    p.add_argument("--order-type", choices=["MOO", "MKT"], default="MOO")
    p.add_argument("--dry-run", action="store_true",
                   help="Use CapturingAlerter instead of SMTP")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def _default_trading_date() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = BasketConfig.load(args.config)
    store = StateStore(args.state)
    store.load()
    ledger = Ledger.load(args.ledger)
    pending_store = PendingOrderStore(args.pending)
    pending_store.load()

    trading_date = args.trading_date or _default_trading_date()

    from src.deploy.providers import YahooCloseProvider
    provider: CloseSeriesProvider = YahooCloseProvider()

    if args.broker == "sim":
        from src.deploy.broker import SimStockBroker
        broker: StockBroker = SimStockBroker(starting_cash=args.sim_cash)
        _seed_sim_broker_quotes(broker, cfg, provider, trading_date,
                                nominal_equity=args.sim_cash)
    else:
        # ib_insync connect lives here (and not in IBKRStockBroker) so the
        # adapter itself stays test-importable without the package.
        from ib_insync import IB
        from src.deploy.broker import IBKRStockBroker
        ib = IB()
        ib.connect("127.0.0.1", 7497, clientId=1)
        broker = IBKRStockBroker(ib=ib)

    if args.dry_run:
        alerter: Alerter = CapturingAlerter()
    else:
        alerter = SmtpAlerter.from_env() or CapturingAlerter()

    cfg_obj = OrchestratorConfig(
        cfg=cfg, store=store, ledger=ledger, broker=broker,
        provider=provider, alerter=alerter,
        trading_date=trading_date,
        ledger_path=args.ledger, history_path=args.history,
        reports_dir=args.reports_dir, pending_store=pending_store,
        first_run=args.first_run, order_type=OrderType(args.order_type),
    )
    result = asyncio.run(run_once(cfg_obj))

    drained = len(result.drained_fills)
    print(f"[{result.trading_date}] reconcile={result.reconciliation.summary}; "
          f"drained={drained} placed={len(result.placed_tickets)} "
          f"recorded={len(result.recorded_fills)} "
          f"pending={len(result.newly_pending)} "
          f"alerts={len(result.alerts)} errors={len(result.errors)} "
          f"halted={result.halted}")
    if result.report_path:
        print(f"report: {result.report_path}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

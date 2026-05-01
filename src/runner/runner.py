"""LiveRunner — the orchestrator.

Wires together strategies, broker, data feed, position manager, guardrails,
weekly budget, blackout/regime, and persistence.

Phases (all driven from the outside — usually by an asyncio scheduler;
a test can call them directly to step through a trading day):

  on_startup()                  Load state from disk; seed indicators.
  on_daily_close(today)         16:05 ET. Run EWO + IBS strategies on
                                today's bars; queue any signals as
                                DeferredEntry to fire at next-day open.
  on_session_open(today)        09:31 ET. Drain DeferredEntry queue:
                                guardrail-check each, place entry orders,
                                construct Positions on fill.
  on_intraday_bar(symbol, bar)  Per 5-min bar during RTH. Drives
                                AfternoonReversion entries (11:00-11:30)
                                and exit evaluation on every open
                                position.
  on_session_close(today)       16:00 ET. Daily-close pass: evaluate
                                exits on every open position using the
                                fresh daily bar; print weekly budget
                                snapshot; mark survivors as overnight.

Each phase is idempotent against state on disk so a crash + restart
mid-day resumes correctly. State is rewritten after every mutation.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from src.broker.orders import FillChase, OrderStatus, Quote
from src.indicators import atr
from src.logging_setup import order_logger
from src.positions.exits import ExitKind, MarketState
from src.positions.manager import PositionManager
from src.positions.position import Position
from src.risk.blackout import BlackoutChecker
from src.risk.guardrails import EntryRequest, Guardrails
from src.risk.weekly_budget import WeeklyBudget
from src.runner.broker import Broker, OptionContract
from src.runner.feed import DataFeed
from src.runner.store import DeferredEntry, PositionStore
from src.strategies.afternoon import AfternoonReversionStrategy, attach_daily_atr
from src.strategies.base import Signal, SignalAction, Strategy

ET = ZoneInfo("America/New_York")
SIGNAL_UNIVERSE = ("SPY", "QQQ")


@dataclass
class LiveRunner:
    broker: Broker
    feed: DataFeed
    pm: PositionManager
    budget: WeeklyBudget
    guardrails: Guardrails
    blackout: BlackoutChecker
    daily_strategies: list[Strategy]                 # EWO, IBS
    intraday_strategy: AfternoonReversionStrategy    # exactly one
    store: PositionStore
    deferred: list[DeferredEntry] = field(default_factory=list)

    # FillChase tunables (overridable by tests for fast runs)
    ladder_interval_sec: float = 15.0
    poll_interval_sec: float = 0.5

    # --- Lifecycle -------------------------------------------------------

    async def on_startup(self) -> None:
        logger.info(
            f"runner startup: {self.pm.open_count()} open positions, "
            f"{len(self.deferred)} deferred entries"
        )
        self._persist()

    # --- Phase 1: daily-close signal pass --------------------------------

    async def on_daily_close(self, today: date) -> None:
        """16:05 ET. Run EWO + IBS on today's daily bars. Defer entries to
        next-day open. Per spec: if EWO and IBS both fire on the same
        underlying same day, prefer EWO (log IBS as suppressed)."""
        next_open = datetime.combine(self._next_session_date(today),
                                     time(9, 31), tzinfo=ET)
        for sym in SIGNAL_UNIVERSE:
            daily = await self.feed.daily_bars(sym, lookback_days=400)
            if daily.empty:
                continue
            signals_for_sym: list[tuple[Strategy, Signal]] = []
            for strat in self.daily_strategies:
                sig = strat.on_daily_close(sym, daily)
                if sig is not None:
                    signals_for_sym.append((strat, sig))

            # Co-signal de-dupe: prefer EWO over IBS
            chosen = self._dedupe_co_signals(signals_for_sym)
            for strat, sig in chosen:
                self._enqueue_deferred(sig, fire_at=next_open)

        self._persist()

    @staticmethod
    def _dedupe_co_signals(pairs: list[tuple[Strategy, Signal]]) -> list[tuple[Strategy, Signal]]:
        if len(pairs) <= 1:
            return pairs
        names = [p[0].name for p in pairs]
        if "ewo" in names and "ibs" in names:
            ewo = next(p for p in pairs if p[0].name == "ewo")
            ibs = next(p for p in pairs if p[0].name == "ibs")
            logger.info(
                f"co-signal: EWO + IBS on {ewo[1].underlying} same day; "
                f"taking EWO. Suppressed IBS: {ibs[1].reason}"
            )
            return [ewo]
        return pairs

    def _enqueue_deferred(self, sig: Signal, fire_at: datetime) -> None:
        d = DeferredEntry(
            fire_at=fire_at,
            strategy_name=sig.strategy_name,
            strategy_family=sig.strategy_family,
            underlying=sig.underlying,
            option_etf=sig.option.underlying_etf,
            right=sig.option.right,
            strike_offset=sig.option.strike_offset,
            target_dte_min=sig.option.target_dte_days[0],
            target_dte_max=sig.option.target_dte_days[1],
            contracts=sig.contracts,
            reason=sig.reason,
        )
        self.deferred.append(d)
        logger.info(f"deferred entry queued for {fire_at:%Y-%m-%d %H:%M %Z}: {sig.reason}")

    @staticmethod
    def _next_session_date(today: date) -> date:
        """Naive: skip weekends. Holiday calendars are out of scope; the
        runner re-checks via blackout/guardrails at execution time anyway.
        """
        d = today + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    # --- Phase 2: next-session-open execution ----------------------------

    async def on_session_open(self, today: date) -> None:
        """09:31 ET. Execute every deferred entry whose fire_at <= now."""
        now = datetime.now(tz=ET)
        ready = [d for d in self.deferred if d.fire_at <= now]
        if not ready:
            return

        nav = await self.broker.nav()
        for d in ready:
            try:
                await self._execute_deferred(d, today, nav)
            except Exception as exc:
                logger.exception(f"failed to execute deferred entry: {exc!r}")
            finally:
                self.deferred.remove(d)
                self._persist()

    async def _execute_deferred(self, d: DeferredEntry, today: date, nav: float) -> None:
        # 1. Resolve a tradable option contract
        contract = await self.broker.select_option(
            underlying_etf=d.option_etf,
            right=d.right,
            strike_offset=d.strike_offset,
            target_dte_min=d.target_dte_min,
            target_dte_max=d.target_dte_max,
        )
        # 2. Quote the option for the spread + price guardrails
        q = await self.broker.quote(contract.id)
        # 3. Build EntryRequest and check guardrails
        req = EntryRequest(
            strategy_name=d.strategy_name,
            strategy_family=d.strategy_family,
            underlying=d.underlying,
            contracts=d.contracts,
            entry_premium=q.mid,
            bid=q.bid,
            ask=q.ask,
            nav=nav,
        )
        decision = self.guardrails.check_entry(
            req,
            now_et=datetime.now(tz=ET),
            open_positions_count=self.pm.open_count(),
            open_positions_in_family=self.pm.open_in_family(d.strategy_family),
            gross_open_premium=self.pm.gross_open_premium(),
        )
        if not decision.allowed:
            order_logger().warning(
                f"REJECT {d.strategy_name} {d.underlying}->{d.option_etf}: "
                f"reason={decision.reason.value} detail={decision.detail}"
            )
            return

        # 4. Apply soft-gate sizing if needed
        contracts = max(1, int(d.contracts * decision.sizing_multiplier))
        # 5. Run fill-chase
        chase = FillChase(
            router=_BrokerToRouter(self.broker),
            contract_id=contract.id,
            side="buy",
            contracts=contracts,
            ladder_interval_sec=self.ladder_interval_sec,
            poll_interval_sec=self.poll_interval_sec,
        )
        result = await chase.run()
        if result.status is not OrderStatus.FILLED or result.fill_price is None:
            order_logger().warning(
                f"entry chase did not fill: {d.strategy_name} {d.option_etf} "
                f"status={result.status.value}"
            )
            return

        # 6. Build Position and open it
        spot = await self.broker.underlying_price(d.underlying)
        daily = await self.feed.daily_bars(d.underlying, lookback_days=60)
        atr20 = float(atr(daily["high"], daily["low"], daily["close"]).iloc[-1]) \
            if not daily.empty else 0.0
        pos = Position(
            trade_id=str(uuid.uuid4()),
            strategy_name=d.strategy_name,
            strategy_family=d.strategy_family,
            underlying=d.underlying,
            option_etf=d.option_etf,
            option_contract_id=contract.id,
            direction=SignalAction.SHORT_FADE if d.option_etf == "SQQQ" else SignalAction.LONG,
            entry_time=datetime.now(tz=ET),
            entry_premium=result.fill_price,
            entry_underlying=spot,
            entry_atr20=atr20,
            expiry=contract.expiry,
            initial_contracts=contracts,
            contracts_remaining=contracts,
        )
        self.pm.open(pos)

    # --- Phase 3: intraday bars ------------------------------------------

    async def on_intraday_bar(self, symbol: str, bar: dict) -> None:
        """Called once per 5-min RTH bar for a signal-universe symbol."""
        session = await self.feed.session_bars(symbol)
        if session.empty:
            return
        # Attach daily ATR once per call (cheap; also avoids stale)
        daily = await self.feed.daily_bars(symbol, lookback_days=60)
        if not daily.empty:
            session = attach_daily_atr(session, daily)

        # Afternoon Reversion entry signal
        sig = self.intraday_strategy.on_intraday_bar(symbol, bar, session)
        if sig is not None:
            await self._fire_intraday_entry(sig, session)

        # Exit evaluation on every open position
        await self._evaluate_and_act_on_exits(intraday_session_by_sym={symbol: session})

    async def _fire_intraday_entry(self, sig: Signal, session: pd.DataFrame) -> None:
        nav = await self.broker.nav()
        contract = await self.broker.select_option(
            underlying_etf=sig.option.underlying_etf,
            right=sig.option.right,
            strike_offset=sig.option.strike_offset,
            target_dte_min=sig.option.target_dte_days[0],
            target_dte_max=sig.option.target_dte_days[1],
        )
        q = await self.broker.quote(contract.id)
        req = EntryRequest(
            strategy_name=sig.strategy_name,
            strategy_family=sig.strategy_family,
            underlying=sig.underlying,
            contracts=sig.contracts,
            entry_premium=q.mid,
            bid=q.bid,
            ask=q.ask,
            nav=nav,
        )
        decision = self.guardrails.check_entry(
            req,
            now_et=datetime.now(tz=ET),
            open_positions_count=self.pm.open_count(),
            open_positions_in_family=self.pm.open_in_family(sig.strategy_family),
            gross_open_premium=self.pm.gross_open_premium(),
        )
        if not decision.allowed:
            order_logger().warning(
                f"REJECT intraday {sig.strategy_name} {sig.underlying}->"
                f"{sig.option.underlying_etf}: {decision.reason.value} {decision.detail}"
            )
            return
        contracts = max(1, int(sig.contracts * decision.sizing_multiplier))

        chase = FillChase(
            router=_BrokerToRouter(self.broker),
            contract_id=contract.id,
            side="buy",
            contracts=contracts,
            invalidation_price=sig.invalidation_price,
            ladder_interval_sec=self.ladder_interval_sec,
            poll_interval_sec=self.poll_interval_sec,
        )
        result = await chase.run()
        if result.status is not OrderStatus.FILLED or result.fill_price is None:
            return

        # Capture morning range for afternoon-specific exits
        obs = session.between_time(time(9, 30), time(11, 0), inclusive="left")
        morning_low = float(obs["low"].min()) if not obs.empty else None
        morning_high = float(obs["high"].max()) if not obs.empty else None

        spot = await self.broker.underlying_price(sig.underlying)
        daily = await self.feed.daily_bars(sig.underlying, lookback_days=60)
        atr20 = float(atr(daily["high"], daily["low"], daily["close"]).iloc[-1]) \
            if not daily.empty else 0.0
        pos = Position(
            trade_id=str(uuid.uuid4()),
            strategy_name=sig.strategy_name,
            strategy_family=sig.strategy_family,
            underlying=sig.underlying,
            option_etf=sig.option.underlying_etf,
            option_contract_id=contract.id,
            direction=sig.action,
            entry_time=datetime.now(tz=ET),
            entry_premium=result.fill_price,
            entry_underlying=spot,
            entry_atr20=atr20,
            expiry=contract.expiry,
            initial_contracts=contracts,
            contracts_remaining=contracts,
            morning_low=morning_low,
            morning_high=morning_high,
        )
        self.pm.open(pos)
        self._persist()

    # --- Phase 4: session close ------------------------------------------

    async def on_session_close(self, today: date) -> None:
        """16:00 ET. Final exit pass against the day's daily close, then mark
        survivors as overnight, advance the trading-day counter, snapshot
        the weekly budget."""
        await self._evaluate_and_act_on_exits(intraday_session_by_sym={})
        # Mark survivors overnight
        for pos in list(self.pm.open_positions()):
            self.pm.mark_overnight(pos.trade_id)
        self.pm.advance_trading_day(today)
        snap = self.budget.snapshot(datetime.now(tz=ET))
        logger.info(
            f"=== Weekly Risk Budget === week_of={snap['week_of']} "
            f"realized_pnl=${snap['realized_pnl']:.2f} "
            f"open_risk=${snap['open_risk']:.2f} "
            f"used=${snap['risk_used']:.2f}/${snap['budget']:.0f} "
            f"({snap['pct_used']:.0%}) gate={snap['gate']}"
        )
        self._persist()

    # --- Exit evaluation core --------------------------------------------

    async def _evaluate_and_act_on_exits(
        self, intraday_session_by_sym: dict[str, pd.DataFrame],
    ) -> None:
        if self.pm.open_count() == 0:
            return
        # Build market state once per underlying
        states: dict[str, MarketState] = {}
        for sym in {p.underlying for p in self.pm.open_positions()}:
            daily = await self.feed.daily_bars(sym, lookback_days=400)
            if daily.empty:
                continue
            spot = await self.broker.underlying_price(sym)
            states[sym] = MarketState(
                now=datetime.now(tz=ET),
                today=datetime.now(tz=ET).date(),
                option_premium=0.0,  # filled per-position below
                underlying_price=spot,
                daily_bars=daily,
                blackout=self.blackout,
                intraday_session=intraday_session_by_sym.get(sym),
            )

        actions = []
        for pos in list(self.pm.open_positions()):
            state = states.get(pos.underlying)
            if state is None:
                continue
            q = await self.broker.quote(pos.option_contract_id)
            # Per-position MarketState clone with this option's premium
            per_state = MarketState(
                now=state.now,
                today=state.today,
                option_premium=q.mid,
                underlying_price=state.underlying_price,
                daily_bars=state.daily_bars,
                blackout=state.blackout,
                intraday_session=state.intraday_session,
            )
            # We rebuild MarketState per-position (cheap; daily_bars is shared)
            actions.append((pos, per_state))

        for pos, st in actions:
            # Re-run evaluate_exit for THIS pos against ITS state
            from src.positions.exits import evaluate_exit  # local import avoids cycle
            action = evaluate_exit(pos, st)
            if action.kind is ExitKind.NONE:
                continue
            await self._execute_exit(pos, action)

        if actions:
            self._persist()

    async def _execute_exit(self, pos: Position, action) -> None:
        chase = FillChase(
            router=_BrokerToRouter(self.broker),
            contract_id=pos.option_contract_id,
            side="sell",
            contracts=action.contracts_to_close,
            is_stop_loss_exit=action.use_stop_loss_path,
            ladder_interval_sec=self.ladder_interval_sec,
            poll_interval_sec=self.poll_interval_sec,
        )
        result = await chase.run()
        if result.status is not OrderStatus.FILLED or result.fill_price is None:
            order_logger().warning(
                f"exit chase did not fill for {pos.trade_id} reason={action.reason}: "
                f"status={result.status.value}"
            )
            return
        self.pm.apply_fill(pos, action, fill_price=result.fill_price,
                           now_et=datetime.now(tz=ET))

    # --- Persistence -----------------------------------------------------

    def _persist(self) -> None:
        self.store.save(self.pm, self.budget, self.deferred)


# --- Adapter so a Broker can drive a FillChase ---------------------------

class _BrokerToRouter:
    """FillChase wants an OrderRouter; Broker is a superset of it."""

    def __init__(self, broker: Broker):
        self._b = broker

    async def quote(self, contract_id: str) -> Quote:
        return await self._b.quote(contract_id)

    async def place_limit(self, contract_id, side, contracts, limit_price):
        return await self._b.place_limit(contract_id, side, contracts, limit_price)

    async def cancel(self, order_id):
        await self._b.cancel(order_id)

    async def status(self, order_id):
        return await self._b.order_status(order_id)

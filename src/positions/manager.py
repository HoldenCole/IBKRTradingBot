"""PositionManager: opens, tracks, evaluates exits, applies fills.

This module owns position lifecycle. The runner (live or backtest) drives
the manager by calling:

    pm.open(...)         # after entry fill
    pm.evaluate_exits()  # per intraday tick / per daily close
    pm.apply_fill(...)   # after a partial or full close fills
    pm.mark_overnight()  # at session close on positions still open

It updates `WeeklyBudget` so accounting (open risk, realized loss) stays in
sync as positions move through their lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from loguru import logger

from src.logging_setup import order_logger
from src.positions.exits import ExitAction, ExitKind, MarketState, evaluate_exit
from src.positions.position import Position, PositionStatus
from src.risk.weekly_budget import OpenPosition, WeeklyBudget


@dataclass
class PositionManager:
    budget: WeeklyBudget
    positions: dict[str, Position] = field(default_factory=dict)

    # --- Lifecycle -------------------------------------------------------

    def open(self, pos: Position) -> None:
        if pos.trade_id in self.positions:
            raise ValueError(f"trade_id {pos.trade_id} already open")
        self.positions[pos.trade_id] = pos
        # Sync to weekly budget
        self.budget.record_open(OpenPosition(
            trade_id=pos.trade_id,
            contracts=pos.contracts_remaining,
            entry_premium=pos.entry_premium,
            held_overnight=pos.held_overnight,
        ))
        order_logger().info(
            f"OPEN {pos.strategy_name} {pos.underlying} via {pos.option_etf} "
            f"x{pos.contracts_remaining} @ ${pos.entry_premium:.2f} "
            f"underlying=${pos.entry_underlying:.2f} expiry={pos.expiry} "
            f"trade_id={pos.trade_id}"
        )

    def open_count(self) -> int:
        return sum(1 for p in self.positions.values() if p.status is PositionStatus.OPEN)

    def open_in_family(self, family: str) -> int:
        return sum(
            1 for p in self.positions.values()
            if p.status is PositionStatus.OPEN and p.strategy_family == family
        )

    def gross_open_premium(self) -> float:
        return sum(
            p.contracts_remaining * p.entry_premium * 100.0
            for p in self.positions.values() if p.status is PositionStatus.OPEN
        )

    def open_positions(self) -> Iterable[Position]:
        return (p for p in self.positions.values() if p.status is PositionStatus.OPEN)

    # --- Per-bar driving --------------------------------------------------

    def evaluate_exits(
        self, market_by_underlying: dict[str, MarketState]
    ) -> list[tuple[Position, ExitAction]]:
        """Walk all open positions, return (position, exit-action) for any
        that fire. Caller is responsible for placing exit orders.
        """
        out: list[tuple[Position, ExitAction]] = []
        for pos in list(self.open_positions()):
            market = market_by_underlying.get(pos.underlying)
            if market is None:
                continue
            action = evaluate_exit(pos, market)
            if action.kind is not ExitKind.NONE:
                out.append((pos, action))
        return out

    def apply_fill(
        self,
        pos: Position,
        action: ExitAction,
        fill_price: float,
        now_et: datetime,
    ) -> float:
        """Update Position + WeeklyBudget after a close fills. Returns the
        realized PnL from this fill (so the runner can log it).
        """
        contracts = action.contracts_to_close
        if contracts <= 0 or contracts > pos.contracts_remaining:
            raise ValueError(
                f"invalid close size {contracts} (remaining={pos.contracts_remaining})"
            )

        # PnL on a long-call leg: (exit_premium - entry_premium) * contracts * 100.
        # Both LONG and SHORT_FADE positions hold long calls (UPRO/TQQQ for longs,
        # SQQQ for shorts), so PnL math is the same.
        pnl = (fill_price - pos.entry_premium) * contracts * 100.0
        pos.realized_pnl += pnl
        pos.contracts_remaining -= contracts
        pos.closes.append({
            "ts": now_et.isoformat(),
            "contracts": contracts,
            "fill_price": fill_price,
            "reason": action.reason.value if action.reason else "n/a",
            "pnl": pnl,
        })

        # Update scale flags by reason
        if action.reason and action.reason.value == "scale_out_+50pct":
            pos.scaled_50pct = True
        elif action.reason and action.reason.value == "scale_out_+100pct":
            pos.scaled_100pct = True
        elif action.reason and action.reason.value == "afternoon_vwap_reclaim":
            # afternoon's VWAP-reclaim scale also sets the +50% flag so we
            # don't try to fire the premium-target scale on the same trade.
            pos.scaled_50pct = True

        order_logger().info(
            f"CLOSE {pos.strategy_name} {pos.option_etf} x{contracts} "
            f"@ ${fill_price:.2f} reason={action.reason.value if action.reason else '?'} "
            f"pnl=${pnl:.2f} remaining={pos.contracts_remaining} trade_id={pos.trade_id}"
        )

        if pos.contracts_remaining == 0:
            pos.status = PositionStatus.CLOSED
            self.budget.record_close(pos.trade_id, pos.realized_pnl, now_et)
            logger.info(
                f"position {pos.trade_id} fully closed, realized=${pos.realized_pnl:.2f}"
            )
        else:
            # Partial: rewrite the budget's OpenPosition with the new size.
            self.budget.record_open(OpenPosition(
                trade_id=pos.trade_id,
                contracts=pos.contracts_remaining,
                entry_premium=pos.entry_premium,
                held_overnight=pos.held_overnight,
            ))
        return pnl

    # --- End-of-session housekeeping -------------------------------------

    def mark_overnight(self, trade_id: str) -> None:
        if trade_id in self.positions:
            self.positions[trade_id].held_overnight = True
            self.budget.mark_overnight(trade_id)

    def advance_trading_day(self, today: date) -> None:
        """Bump the trading_days_held counter on every open position."""
        for p in self.open_positions():
            if p.entry_time.date() < today:
                p.trading_days_held += 1

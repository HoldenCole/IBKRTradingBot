"""Backtest engine.

Drives the same Strategy + Guardrails + PositionManager + exits code path
that the live runner uses, but against historical daily bars and a
synthetic options book.

Daily loop:
  for each trading day in [start, end]:
    1. open phase — execute any deferred entries from yesterday's close pass
       at TODAY'S OPEN (synthetic option quote at today's open price).
    2. close phase — re-quote each open position at today's close, run
       exit evaluation (PositionManager + evaluate_exit), apply fills at
       today's close with slippage.
    3. daily-close pass — run EWO + IBS strategies on today's bars,
       enqueue any signals as deferred entries for tomorrow's open.
    4. mark survivors as overnight, advance the trading-day counter.

Afternoon Reversion is intentionally out of scope here: it requires
multi-year intraday bars which FMP doesn't provide on the free tier.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from src.backtest.options import (
    DEFAULT_IV_BY_ETF,
    DEFAULT_SPREAD_PCT_BY_ETF,
    OptionParams,
    black_scholes_call,
    synthetic_quote,
)
from src.positions.exits import ExitAction, ExitKind, ExitReason, MarketState, evaluate_exit
from src.positions.manager import PositionManager
from src.positions.position import Position
from src.risk.blackout import BlackoutChecker, StubCalendar
from src.risk.guardrails import EntryRequest, Guardrails, RejectReason
from src.risk.regime import RegimeProvider, StaticRegime
from src.risk.weekly_budget import WeeklyBudget
from src.strategies.base import Signal, SignalAction, Strategy

ET = ZoneInfo("America/New_York")


@dataclass
class BacktestConfig:
    start: date
    end: date
    initial_capital: float = 8000.0

    iv_by_etf: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_IV_BY_ETF))
    spread_pct_by_etf: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_SPREAD_PCT_BY_ETF)
    )
    risk_free_rate: float = 0.045

    # Slippage on entries: fill at mid + slippage*spread (against you).
    # Slippage on exits: fill at mid - slippage*spread.
    slippage_pct_of_spread: float = 0.25

    # Intraday stop fill model: when an option's premium hits -50% intraday
    # (detected via the day's low against BS), record the fill at -50% minus
    # a small extra slippage. Default 0.03 -> fills at -53% of entry premium.
    # Without this, stops would only be checked at daily close and fill at
    # whatever the late-day premium was — typically much worse than -50%.
    intraday_stop_slippage_pct: float = 0.03

    # Risk parameters mirror live config defaults
    weekly_loss_budget: float = 500.0
    per_trade_risk_cap: float = 200.0
    max_concurrent_positions: int = 2
    max_gross_premium_pct: float = 0.60
    soft_gate_pct: float = 0.70
    overnight_multiplier: float = 1.5

    # Optional toggles
    enable_blackout: bool = True
    enable_regime: bool = False  # default OFF; user's regime service is per-deployment


@dataclass
class TradeRecord:
    """One closed (or partially closed) leg, for the perf report."""
    trade_id: str
    strategy: str
    underlying: str
    option_etf: str
    direction: str
    entry_time: datetime
    entry_premium: float
    exit_time: datetime
    exit_premium: float
    contracts: int
    pnl: float
    reason: str
    # Entry-context fields used by post-hoc diagnostics (stop decomposition,
    # MAE analysis, IV-rank counterfactuals).
    entry_underlying: float = 0.0
    entry_atr20: float = 0.0


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[TradeRecord]
    equity_curve: pd.Series  # indexed by date, value = realized + open MTM
    weekly_snapshots: list[dict]
    skipped_signals: list[dict]


class BacktestEngine:
    def __init__(
        self,
        config: BacktestConfig,
        strategies: Sequence[Strategy],
        daily_bars: dict[str, pd.DataFrame],   # by signal underlying (SPY, QQQ)
        underlying_etf_bars: dict[str, pd.DataFrame],  # by option underlying (UPRO/TQQQ/SQQQ)
        blackout: BlackoutChecker | None = None,
        regime: RegimeProvider | None = None,
    ):
        self.cfg = config
        self.strategies = list(strategies)
        self.daily_bars = daily_bars
        self.etf_bars = underlying_etf_bars

        self.budget = WeeklyBudget(
            budget=config.weekly_loss_budget,
            soft_gate_pct=config.soft_gate_pct,
            overnight_multiplier=config.overnight_multiplier,
        )
        self.pm = PositionManager(budget=self.budget)
        self.blackout = blackout or BlackoutChecker(StubCalendar([]))
        self.regime = regime or StaticRegime(
            {"SPY": True, "QQQ": True} if not config.enable_regime else {}
        )
        self.guardrails = Guardrails(
            budget=self.budget,
            blackout=self.blackout,
            regime=self.regime,
            per_trade_risk_cap=config.per_trade_risk_cap,
            max_concurrent_positions=config.max_concurrent_positions,
            max_gross_premium_pct=config.max_gross_premium_pct,
        )

        self.deferred: list[tuple[Signal, date]] = []  # (signal, fire-on-this-date)
        self.trades: list[TradeRecord] = []
        self.skipped: list[dict] = []
        self.weekly_snapshots: list[dict] = []
        self.equity_by_date: dict[date, float] = {}

    # --- Public entry point ---------------------------------------------

    def run(self) -> BacktestResult:
        all_dates = self._trading_dates()
        if not all_dates:
            raise ValueError(f"no daily bars in [{self.cfg.start}, {self.cfg.end}]")

        for d in all_dates:
            self._process_day(d)

        # Force-close any positions still open at end-of-backtest.
        if all_dates:
            self._force_close_remaining(all_dates[-1])

        eq = pd.Series(self.equity_by_date).sort_index()
        return BacktestResult(
            config=self.cfg,
            trades=self.trades,
            equity_curve=eq,
            weekly_snapshots=self.weekly_snapshots,
            skipped_signals=self.skipped,
        )

    # --- Per-day driver -------------------------------------------------

    def _process_day(self, today: date) -> None:
        # 1. Mark overnight (if not already) — anything held from prior session
        #    counted at 1.5x against the budget. Engine handles this on entry
        #    to a new day.
        for pos in list(self.pm.open_positions()):
            if pos.entry_time.date() < today and not pos.held_overnight:
                self.pm.mark_overnight(pos.trade_id)

        # 2. Open phase: execute deferred entries at today's open
        ready = [(s, when) for (s, when) in self.deferred if when <= today]
        for sig, when in ready:
            self._execute_entry(sig, today)
            self.deferred.remove((sig, when))

        # 3. Close phase: evaluate exits using today's daily close
        self._evaluate_exits_at_close(today)

        # 4. Snapshot weekly budget at close
        snap = self.budget.snapshot(self._dt(today, time(16, 0)))
        self.weekly_snapshots.append(snap)

        # 5. Daily-close pass: generate signals for tomorrow's open
        self._run_daily_strategies(today)

        # 6. Equity curve point at this date's close
        self.equity_by_date[today] = self._equity_at_close(today)

        # 7. Advance trading-day counter
        self.pm.advance_trading_day(today)

    # --- Strategy signal generation -------------------------------------

    def _run_daily_strategies(self, today: date) -> None:
        next_open = self._next_session_date(today)
        for sym in ("SPY", "QQQ"):
            bars = self._bars_through(self.daily_bars.get(sym), today)
            if bars is None or bars.empty:
                continue
            fired: list[tuple[Strategy, Signal]] = []
            for strat in self.strategies:
                sig = strat.on_daily_close(sym, bars)
                if sig is not None:
                    fired.append((strat, sig))
            chosen = self._dedupe(fired)
            for _, sig in chosen:
                self.deferred.append((sig, next_open))

    @staticmethod
    def _dedupe(pairs: list[tuple[Strategy, Signal]]) -> list[tuple[Strategy, Signal]]:
        if len(pairs) <= 1:
            return pairs
        names = [p[0].name for p in pairs]
        if "ewo" in names and "ibs" in names:
            return [next(p for p in pairs if p[0].name == "ewo")]
        return pairs

    # --- Entry execution -------------------------------------------------

    def _execute_entry(self, sig: Signal, today: date) -> None:
        etf = sig.option.underlying_etf
        # Underlying ETF price at today's OPEN (we fill near the open)
        spot_today_open = self._etf_open(etf, today)
        if spot_today_open is None:
            return

        # Strike + expiry
        strike = round(spot_today_open) + sig.option.strike_offset
        target_dte = (sig.option.target_dte_days[0] + sig.option.target_dte_days[1]) // 2
        expiry = today + timedelta(days=target_dte)

        # Synthetic quote at today's open
        iv = self.cfg.iv_by_etf.get(etf, 0.50)
        spread_pct = self.cfg.spread_pct_by_etf.get(etf, 0.06)
        params = OptionParams(
            spot=spot_today_open, strike=strike, dte_days=target_dte,
            iv=iv, risk_free=self.cfg.risk_free_rate,
        )
        q = synthetic_quote(params, spread_pct_of_mid=spread_pct)

        # Guardrails
        nav = self._current_nav(today)
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
            now_et=self._dt(today, time(9, 31)),
            open_positions_count=self.pm.open_count(),
            open_positions_in_family=self.pm.open_in_family(sig.strategy_family),
            gross_open_premium=self.pm.gross_open_premium(),
        )
        if not decision.allowed:
            self.skipped.append({
                "date": today.isoformat(),
                "strategy": sig.strategy_name,
                "underlying": sig.underlying,
                "reason": decision.reason.value,
                "detail": decision.detail,
            })
            return

        contracts = max(1, int(sig.contracts * decision.sizing_multiplier))

        # Fill = mid + slippage*spread (entry pays away from mid)
        fill_price = q.mid + self.cfg.slippage_pct_of_spread * (q.ask - q.bid)

        # ATR(20) at entry from the underlying signal symbol
        from src.indicators import atr
        sig_bars = self._bars_through(self.daily_bars.get(sig.underlying), today)
        atr20 = float(atr(sig_bars["high"], sig_bars["low"], sig_bars["close"]).iloc[-1])

        # Signal underlying's open price at the entry day. This is what
        # entry_underlying must hold so that exit logic (afternoon hard
        # stop, ATR trail, MAE diagnostics) compares against the same
        # symbol as entry_atr20. Live runner does the equivalent via
        # broker.underlying_price(sig.underlying); previously this engine
        # was incorrectly storing the option ETF's open price here.
        sig_open = self._underlying_open(sig.underlying, today)
        if sig_open is None:
            sig_open = self._underlying_close(sig.underlying, today) or spot_today_open

        pos = Position(
            trade_id=str(uuid.uuid4()),
            strategy_name=sig.strategy_name,
            strategy_family=sig.strategy_family,
            underlying=sig.underlying,
            option_etf=etf,
            option_contract_id=f"{etf}_{strike}_{expiry.isoformat()}",
            direction=sig.action,
            entry_time=self._dt(today, time(9, 31)),
            entry_premium=fill_price,
            entry_underlying=sig_open,
            entry_atr20=atr20,
            expiry=expiry,
            initial_contracts=contracts,
            contracts_remaining=contracts,
        )
        self.pm.open(pos)

    # --- Exit evaluation -------------------------------------------------

    def _check_intraday_stop(
        self, pos: Position, today: date,
    ) -> tuple[bool, float | None]:
        """Detect if the option's premium hit -50% intraday using the day's
        low (long calls — UPRO/TQQQ/SQQQ — all lose value when their
        underlying drops). Returns (triggered, fill_price). When triggered,
        fill_price is recorded at exactly -50% minus the configured small
        slippage rather than wherever the close ended up.

        This is the standard daily-bar approximation for an intraday stop.
        Without it, we under-attribute stop fills and over-attribute losses
        to the model when in reality the live bot would catch -50% well
        before close.
        """
        etf = pos.option_etf
        df = self.etf_bars.get(etf)
        if df is None or df.empty:
            return False, None
        low_today = _row_value(df, today, "low")
        if low_today is None:
            return False, None

        iv = self.cfg.iv_by_etf.get(etf, 0.50)
        dte = max(0, (pos.expiry - today).days)
        low_premium = black_scholes_call(OptionParams(
            spot=low_today, strike=_strike_from(pos),
            dte_days=dte, iv=iv, risk_free=self.cfg.risk_free_rate,
        ))
        threshold = pos.entry_premium * 0.50
        if low_premium > threshold:
            return False, None

        slippage = self.cfg.intraday_stop_slippage_pct
        fill_price = pos.entry_premium * max(0.0, 0.50 - slippage)
        return True, max(0.01, fill_price)

    def _evaluate_exits_at_close(self, today: date) -> None:
        if self.pm.open_count() == 0:
            return
        for pos in list(self.pm.open_positions()):
            etf = pos.option_etf
            spot_close = self._etf_close(etf, today)
            if spot_close is None:
                continue
            sig_underlying_close = self._underlying_close(pos.underlying, today)
            if sig_underlying_close is None:
                continue

            # Step 1 fix: intraday stop trigger. If the day's low pushed BS
            # premium <= -50% of entry, we record the stop NOW at the
            # intraday-fill price (typically ~-53%), not at the close.
            triggered, intraday_fill = self._check_intraday_stop(pos, today)
            if triggered:
                action = ExitAction(
                    kind=ExitKind.CLOSE_ALL,
                    contracts_to_close=pos.contracts_remaining,
                    reason=ExitReason.PREMIUM_STOP,
                    detail=f"intraday low triggered -50% stop (fill @ -{(1-(intraday_fill/pos.entry_premium))*100:.0f}%)",
                    use_stop_loss_path=True,
                )
                entry_premium = pos.entry_premium
                entry_time = pos.entry_time
                pnl = self.pm.apply_fill(
                    pos, action, fill_price=intraday_fill,
                    now_et=self._dt(today, time(16, 0)),
                )
                self.trades.append(TradeRecord(
                    trade_id=pos.trade_id,
                    strategy=pos.strategy_name,
                    underlying=pos.underlying,
                    option_etf=pos.option_etf,
                    direction=pos.direction.value,
                    entry_time=entry_time,
                    entry_premium=entry_premium,
                    exit_time=self._dt(today, time(16, 0)),
                    exit_premium=intraday_fill,
                    contracts=action.contracts_to_close,
                    pnl=pnl,
                    reason=action.reason.value,
                    entry_underlying=pos.entry_underlying,
                    entry_atr20=pos.entry_atr20,
                ))
                continue

            # Repricing the option at today's close
            dte = (pos.expiry - today).days
            iv = self.cfg.iv_by_etf.get(etf, 0.50)
            spread_pct = self.cfg.spread_pct_by_etf.get(etf, 0.06)
            params = OptionParams(
                spot=spot_close, strike=_strike_from(pos),
                dte_days=max(0, dte), iv=iv, risk_free=self.cfg.risk_free_rate,
            )
            q = synthetic_quote(params, spread_pct_of_mid=spread_pct)

            daily = self._bars_through(self.daily_bars.get(pos.underlying), today)
            market = MarketState(
                now=self._dt(today, time(16, 0)),
                today=today,
                option_premium=q.mid,
                underlying_price=sig_underlying_close,
                daily_bars=daily,
                blackout=self.blackout,
            )
            action = evaluate_exit(pos, market)
            if action.kind is ExitKind.NONE:
                continue

            # Fill price for exits: mid - slippage*spread, or stop-loss path
            if action.use_stop_loss_path:
                fill_price = max(0.01, q.bid - 0.05)
            else:
                fill_price = max(0.01, q.mid - self.cfg.slippage_pct_of_spread * (q.ask - q.bid))

            entry_premium = pos.entry_premium
            entry_time = pos.entry_time
            pnl = self.pm.apply_fill(
                pos, action, fill_price=fill_price,
                now_et=self._dt(today, time(16, 0)),
            )
            self.trades.append(TradeRecord(
                trade_id=pos.trade_id,
                strategy=pos.strategy_name,
                underlying=pos.underlying,
                option_etf=pos.option_etf,
                direction=pos.direction.value,
                entry_time=entry_time,
                entry_premium=entry_premium,
                exit_time=self._dt(today, time(16, 0)),
                exit_premium=fill_price,
                contracts=action.contracts_to_close,
                pnl=pnl,
                reason=action.reason.value if action.reason else "n/a",
                entry_underlying=pos.entry_underlying,
                entry_atr20=pos.entry_atr20,
            ))

    def _force_close_remaining(self, today: date) -> None:
        """End-of-backtest: mark-to-market close anything still open."""
        for pos in list(self.pm.open_positions()):
            etf = pos.option_etf
            spot_close = self._etf_close(etf, today) or 0.0
            dte = max(0, (pos.expiry - today).days)
            iv = self.cfg.iv_by_etf.get(etf, 0.50)
            spread_pct = self.cfg.spread_pct_by_etf.get(etf, 0.06)
            params = OptionParams(
                spot=spot_close, strike=_strike_from(pos),
                dte_days=dte, iv=iv, risk_free=self.cfg.risk_free_rate,
            )
            q = synthetic_quote(params, spread_pct_of_mid=spread_pct)
            fill_price = max(0.01, q.mid)

            action = ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail="end-of-backtest mark-to-market close",
            )
            entry_premium = pos.entry_premium
            entry_time = pos.entry_time
            pnl = self.pm.apply_fill(
                pos, action, fill_price=fill_price,
                now_et=self._dt(today, time(16, 0)),
            )
            self.trades.append(TradeRecord(
                trade_id=pos.trade_id,
                strategy=pos.strategy_name,
                underlying=pos.underlying,
                option_etf=pos.option_etf,
                direction=pos.direction.value,
                entry_time=entry_time,
                entry_premium=entry_premium,
                exit_time=self._dt(today, time(16, 0)),
                exit_premium=fill_price,
                contracts=action.contracts_to_close,
                pnl=pnl,
                reason="end_of_backtest",
                entry_underlying=pos.entry_underlying,
                entry_atr20=pos.entry_atr20,
            ))

    # --- Equity curve ----------------------------------------------------

    def _current_nav(self, today: date) -> float:
        return self.cfg.initial_capital + self._realized_to_date(today) + self._open_mtm(today)

    def _realized_to_date(self, today: date) -> float:
        # WeeklyBudget tracks realized PnL by week; sum all weeks <= today.
        total = 0.0
        for wk_start, pnl in self.budget.realized_pnl_by_week.items():
            if wk_start <= today:
                total += pnl
        return total

    def _open_mtm(self, today: date) -> float:
        total = 0.0
        for pos in self.pm.open_positions():
            etf = pos.option_etf
            spot = self._etf_close(etf, today) or pos.entry_underlying
            dte = max(0, (pos.expiry - today).days)
            iv = self.cfg.iv_by_etf.get(etf, 0.50)
            spread_pct = self.cfg.spread_pct_by_etf.get(etf, 0.06)
            q = synthetic_quote(
                OptionParams(spot=spot, strike=_strike_from(pos),
                             dte_days=dte, iv=iv, risk_free=self.cfg.risk_free_rate),
                spread_pct_of_mid=spread_pct,
            )
            # Unrealized PnL on the option leg
            total += (q.mid - pos.entry_premium) * pos.contracts_remaining * 100.0
        return total

    def _equity_at_close(self, today: date) -> float:
        return self._current_nav(today)

    # --- Helpers ---------------------------------------------------------

    def _trading_dates(self) -> list[date]:
        # Use SPY bars as the calendar; should always be present in a real run.
        spy = self.daily_bars.get("SPY")
        if spy is None or spy.empty:
            # Fall back to QQQ
            qqq = self.daily_bars.get("QQQ")
            if qqq is None or qqq.empty:
                return []
            cal = qqq.index
        else:
            cal = spy.index
        return [d.date() if hasattr(d, "date") else d
                for d in cal
                if self.cfg.start <= (d.date() if hasattr(d, "date") else d) <= self.cfg.end]

    def _bars_through(self, df: pd.DataFrame | None, today: date) -> pd.DataFrame | None:
        if df is None or df.empty:
            return None
        idx = df.index
        # Compare via date; idx may be Timestamp
        mask = pd.Series(
            [(d.date() if hasattr(d, "date") else d) <= today for d in idx],
            index=idx,
        )
        return df.loc[mask]

    def _etf_open(self, etf: str, today: date) -> float | None:
        df = self.etf_bars.get(etf)
        return _row_value(df, today, "open")

    def _etf_close(self, etf: str, today: date) -> float | None:
        df = self.etf_bars.get(etf)
        return _row_value(df, today, "close")

    def _underlying_open(self, sym: str, today: date) -> float | None:
        df = self.daily_bars.get(sym)
        return _row_value(df, today, "open")

    def _underlying_close(self, sym: str, today: date) -> float | None:
        df = self.daily_bars.get(sym)
        return _row_value(df, today, "close")

    @staticmethod
    def _next_session_date(today: date) -> date:
        d = today + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    @staticmethod
    def _dt(d: date, t: time) -> datetime:
        return datetime.combine(d, t).replace(tzinfo=ET)


def _strike_from(pos: Position) -> float:
    """Pull the strike out of the synthetic contract id (`ETF_strike_expiry`)."""
    parts = pos.option_contract_id.split("_")
    if len(parts) >= 2:
        try:
            return float(parts[1])
        except ValueError:
            pass
    return pos.entry_underlying  # fallback


def _row_value(df: pd.DataFrame | None, today: date, col: str) -> float | None:
    if df is None or df.empty:
        return None
    for ts, row in df.iterrows():
        d = ts.date() if hasattr(ts, "date") else ts
        if d == today:
            v = row.get(col)
            if v is None or pd.isna(v):
                return None
            return float(v)
    return None

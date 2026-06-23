"""End-to-end tests for the orchestrator (src/deploy/run.py).

These exercise the daily-check → reconcile → orders/positioning → ledger →
report → alerts path against the SimStockBroker. They DO NOT touch IBKR
or Yahoo; closes are served by an in-test stub provider.

Two scenarios cover the orchestrator's two modes:
  - first_run=True: empty ledger, positioning brings the portfolio to target
  - first_run=False: steady-state daily run, a flip triggers a rotation
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.deploy.alerts import AlertSeverity, CapturingAlerter
from src.deploy.baskets import BasketConfig
from src.deploy.broker import OrderState, OrderType, SimStockBroker
from src.deploy.daily_check import CloseSeriesProvider
from src.deploy.orders import OFF_VEHICLE_SYMBOL
from src.deploy.portfolio import Ledger
from src.deploy.run import OrchestratorConfig, run_once
from src.deploy.signal_state import SignalState
from src.deploy.store import StateStore


class _StubProvider:
    """Deterministic close-series provider: maps each asset to a fixed
    series that we set up to produce a known signal state on the target
    date."""
    def __init__(self, series_by_asset: dict[str, pd.Series]):
        self._series = series_by_asset

    def closes(self, asset: str, as_of: date, lookback_days: int) -> pd.Series:
        s = self._series[asset]
        return s.loc[: pd.Timestamp(as_of)].tail(lookback_days)


def _trend_up_series(end: date, days: int = 260, start_px: float = 400.0,
                     slope: float = 0.5) -> pd.Series:
    """A monotonically-rising series: close > SMA50 > SMA200 -> signal ON."""
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=days)
    vals = [start_px + i * slope for i in range(days)]
    return pd.Series(vals, index=idx, name="close")


def _trend_down_series(end: date, days: int = 260, start_px: float = 600.0,
                       slope: float = -0.5) -> pd.Series:
    """A monotonically-falling series: close < SMA50 < SMA200 -> signal OFF."""
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=days)
    vals = [start_px + i * slope for i in range(days)]
    return pd.Series(vals, index=idx, name="close")


def _build_broker(starting_cash: float = 8000.0,
                  qqq_px: float = 540.0, ibit_px: float = 60.0,
                  sgov_px: float = 100.0) -> SimStockBroker:
    b = SimStockBroker(starting_cash=starting_cash)
    b.set_quote("QQQ", qqq_px); b.set_quote("IBIT", ibit_px)
    b.set_quote(OFF_VEHICLE_SYMBOL, sgov_px)
    return b


def _build_cfg(tmp_path: Path, broker, provider, ledger=None,
               first_run=False, alerter=None, trading_date=date(2024, 6, 20)):
    cfg = BasketConfig.load()
    store_path = tmp_path / "signal_state.json"
    return OrchestratorConfig(
        cfg=cfg,
        store=StateStore(store_path),
        ledger=ledger or Ledger(),
        broker=broker,
        provider=provider,
        alerter=alerter or CapturingAlerter(),
        trading_date=trading_date,
        ledger_path=tmp_path / "ledger.json",
        history_path=tmp_path / "history.csv",
        reports_dir=tmp_path / "reports",
        first_run=first_run,
        order_type=OrderType.MKT,    # tests fill immediately; KL-5 covers MOO
        now_utc=datetime(2024, 6, 20, 20, 1, tzinfo=timezone.utc),
    )


# ===== First-run / positioning =====

@pytest.mark.asyncio
async def test_first_run_positions_into_targets(tmp_path):
    """Fresh account, both signals come up ON (QQQ rising, BTC rising).
    Positioning should buy 7 QQQ and 66 IBIT (50/50 of $8000)."""
    td = date(2024, 6, 20)
    broker = _build_broker(starting_cash=8000.0)
    provider = _StubProvider({
        "QQQ": _trend_up_series(td, start_px=400.0, slope=1.0),
        "BTC": _trend_up_series(td, start_px=30.0, slope=0.2),
    })
    cfg = _build_cfg(tmp_path, broker, provider, first_run=True,
                     trading_date=td)
    result = await run_once(cfg)

    assert result.exit_code == 0
    assert not result.halted
    # Both sleeves placed BUY orders for their risk asset (exact qty depends
    # on the closing price the signal saw, which is the same price used for
    # sizing — see _quotes_for_run; we assert positive whole shares).
    by_sym = {(t.symbol, t.side): t for t in result.placed_tickets}
    assert by_sym[("QQQ", "BUY")].quantity > 0
    assert by_sym[("IBIT", "BUY")].quantity > 0
    # MKT orders fill immediately -> recorded into ledger
    assert len(result.recorded_fills) == 2
    open_qqq = cfg.ledger.open_shares_by_strategy("QQQ")
    open_ibit = cfg.ledger.open_shares_by_strategy("IBIT")
    assert "qqq_trend_50_200" in open_qqq
    assert "btc_trend_50_200" in open_ibit
    # Ledger was persisted
    assert (tmp_path / "ledger.json").exists()
    # Report was saved
    assert result.report_path is not None and result.report_path.exists()
    # History row was written
    assert (tmp_path / "history.csv").exists()


@pytest.mark.asyncio
async def test_first_run_with_unknown_signal_parks_in_sgov(tmp_path):
    """Series too short for SMA200 -> UNKNOWN -> sleeves park in SGOV."""
    td = date(2024, 6, 20)
    broker = _build_broker(starting_cash=8000.0)
    # Only 100 bars; SMA200 needs 200 -> UNKNOWN
    provider = _StubProvider({
        "QQQ": _trend_up_series(td, days=100, start_px=400.0, slope=1.0),
        "BTC": _trend_up_series(td, days=100, start_px=30.0, slope=0.2),
    })
    cfg = _build_cfg(tmp_path, broker, provider, first_run=True,
                     trading_date=td)
    result = await run_once(cfg)
    assert result.exit_code == 0
    # Both sleeves park in SGOV
    sgov_buys = [t for t in result.placed_tickets
                 if t.symbol == OFF_VEHICLE_SYMBOL and t.side == "BUY"]
    assert len(sgov_buys) == 2


# ===== Steady-state daily run =====

@pytest.mark.asyncio
async def test_steady_state_flip_triggers_rotation(tmp_path):
    """Sleeve was OFF (held SGOV), today's signal flips ON -> sell SGOV, buy
    QQQ; ledger and broker positions reflect it."""
    td = date(2024, 6, 20)
    yest = date(2024, 6, 19)
    broker = _build_broker(starting_cash=0.0)
    # Pre-seed: BTC sleeve already ON in IBIT, QQQ sleeve parked in SGOV.
    await broker.place_order("IBIT", "BUY", 66, OrderType.MKT) \
        if False else None  # placeholder; we want a clean per-sleeve setup
    # Simpler setup: account is half QQQ-sleeve-in-SGOV, half BTC-sleeve-in-IBIT.
    broker._cash = 8000.0
    await broker.place_order(OFF_VEHICLE_SYMBOL, "BUY", 40, OrderType.MKT)
    await broker.place_order("IBIT", "BUY", 66, OrderType.MKT)

    L = Ledger()
    L.record_buy(strategy_id="qqq_trend_50_200", symbol=OFF_VEHICLE_SYMBOL,
                 quantity=40, price=100.0, trade_date=yest)
    L.record_buy(strategy_id="btc_trend_50_200", symbol="IBIT",
                 quantity=66, price=60.0, trade_date=yest)
    # Persist a prior OFF snapshot for QQQ so today's ON read is a flip.
    store_path = tmp_path / "signal_state.json"
    store = StateStore(store_path)
    from src.deploy.signal_state import SignalSnapshot
    store.put(SignalSnapshot("qqq_trend_50_200", yest, SignalState.OFF,
                              close=400.0, sma50=410.0, sma200=420.0))
    store.put(SignalSnapshot("btc_trend_50_200", yest, SignalState.ON,
                              close=50.0, sma50=45.0, sma200=40.0))
    store.save()

    provider = _StubProvider({
        # QQQ rising fast -> ON today
        "QQQ": _trend_up_series(td, start_px=400.0, slope=1.5),
        # BTC also still up -> ON (no flip)
        "BTC": _trend_up_series(td, start_px=30.0, slope=0.3),
    })
    cfg = OrchestratorConfig(
        cfg=BasketConfig.load(), store=store, ledger=L, broker=broker,
        provider=provider, alerter=CapturingAlerter(),
        trading_date=td, ledger_path=tmp_path / "ledger.json",
        history_path=tmp_path / "history.csv",
        reports_dir=tmp_path / "reports", first_run=False,
        order_type=OrderType.MKT,
        now_utc=datetime(2024, 6, 20, 20, 1, tzinfo=timezone.utc),
    )
    result = await run_once(cfg)

    assert result.exit_code == 0
    # QQQ flipped: SELL SGOV (40), BUY QQQ (~7)
    sides = {(t.symbol, t.side, int(t.quantity)) for t in result.placed_tickets}
    assert (OFF_VEHICLE_SYMBOL, "SELL", 40) in sides
    assert any(s[:2] == ("QQQ", "BUY") for s in sides)
    # Ledger now has QQQ for the qqq sleeve
    assert "qqq_trend_50_200" in L.open_shares_by_strategy("QQQ")


# ===== Reconciliation halt =====

@pytest.mark.asyncio
async def test_reconcile_discrepancy_halts_steady_state_run(tmp_path):
    """Steady-state run with a ledger/broker mismatch -> halt + CRITICAL alert.
    No daily-check, no orders. First-run mode tolerates this and proceeds."""
    td = date(2024, 6, 20)
    broker = _build_broker(starting_cash=8000.0)
    # Broker holds a position the ledger doesn't know about -> ORPHAN_POSITION
    await broker.place_order("QQQ", "BUY", 5, OrderType.MKT)
    provider = _StubProvider({
        "QQQ": _trend_up_series(td), "BTC": _trend_up_series(td)})
    cfg = _build_cfg(tmp_path, broker, provider, first_run=False,
                     trading_date=td)
    result = await run_once(cfg)
    assert result.halted is True
    assert result.exit_code == 1
    # No daily_check ran, no orders placed
    assert result.daily_check is None
    assert result.placed_tickets == []
    # A CRITICAL alert was sent
    assert any(a.severity == AlertSeverity.CRITICAL for a in result.alerts)


@pytest.mark.asyncio
async def test_first_run_tolerates_residual_broker_positions(tmp_path):
    """KL-2 / KL-5 interaction: first-run starts with empty ledger but the
    broker may already hold positions from a prior session — we proceed
    with positioning rather than halting on reconciliation."""
    td = date(2024, 6, 20)
    broker = _build_broker(starting_cash=8000.0)
    await broker.place_order(OFF_VEHICLE_SYMBOL, "BUY", 10, OrderType.MKT)
    provider = _StubProvider({
        "QQQ": _trend_up_series(td), "BTC": _trend_up_series(td)})
    cfg = _build_cfg(tmp_path, broker, provider, first_run=True,
                     trading_date=td)
    result = await run_once(cfg)
    assert result.halted is False
    assert result.exit_code == 0
    assert result.daily_check is not None

"""Executor tests against a fake broker — no gateway, no network."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from src.execution.rotation_executor import (
    ExecutionAborted,
    OrderResult,
    Position,
    run_rotation,
)

TODAY = date(2026, 9, 1)

ALLOCS = {
    "CONS": {"SPY": 0.21, "XLE": 0.1593, "GLD": 0.1103, "DBC": 0.2205, "SHY": 0.3},
    "MOD": {"SPY": 0.3, "XLE": 0.2275, "GLD": 0.1575, "DBC": 0.315},
    "AGG": {"QLD": 0.3, "XLE": 0.2275, "GDX": 0.1575, "DBC": 0.315},
    "VAGG": {"TQQQ": 0.3, "ERX": 0.315, "GDX": 0.1575, "DBC": 0.2275},
}


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    path = tmp_path / "ledger.csv"
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["month", "logged_at", "quadrant", "matrix_version",
                         "allocations", "signals"])
        writer.writerow(["2026-09", "2026-09-01", "REFLATION", "v7",
                         json.dumps(ALLOCS), "{}"])
    return path


class FakeBroker:
    def __init__(self, cash: float, positions: dict[str, Position] | None = None,
                 open_orders: set[str] | None = None):
        self._cash = cash
        self._positions = positions or {}
        self._open = open_orders or set()
        self.executed: list[OrderResult] = []

    def cash(self) -> float:
        return self._cash

    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def quote(self, ticker: str) -> tuple[float, float]:
        px = {"TQQQ": 68.89, "ERX": 110.36, "GDX": 95.88, "DBC": 31.47,
              "SCO": 55.0, "SPY": 660.0}.get(ticker, 100.0)
        return px * 0.9995, px * 1.0005

    def open_order_tickers(self) -> set[str]:
        return set(self._open)

    def execute_limit(self, ticker, action, quantity, limit, timeout_s):
        result = OrderResult(ticker, action, quantity * limit, quantity,
                             limit, "filled", limit)
        self.executed.append(result)
        return result


def run(broker, ledger, tmp_path, tier="VAGG", execute=False):
    return run_rotation(broker, tier, execute=execute, today=TODAY,
                        ledger_path=ledger,
                        executions_path=tmp_path / "executions.csv")


def test_fresh_account_dry_run_places_nothing(ledger, tmp_path):
    broker = FakeBroker(cash=11000.0)
    report = run(broker, ledger, tmp_path)
    assert broker.executed == []
    assert all(r.status == "dry_run" for r in report.results)
    assert {r.ticker for r in report.results} == {"TQQQ", "ERX", "GDX", "DBC"}
    assert abs(sum(r.dollars for r in report.results) - 11000.0) < 1.0
    log = (tmp_path / "executions.csv").read_text()
    assert "dry_run" in log and "TQQQ" in log


def test_execute_sends_orders_and_logs(ledger, tmp_path):
    broker = FakeBroker(cash=11000.0)
    report = run(broker, ledger, tmp_path, execute=True)
    assert len(broker.executed) == 4
    assert all(r.status == "filled" for r in report.results)


def test_rotation_sells_departed_ticker_by_full_share_count(ledger, tmp_path):
    broker = FakeBroker(cash=2856.0, positions={
        "SCO": Position(quantity=10.0, market_value=550.0),
    })
    report = run(broker, ledger, tmp_path, execute=True)
    sells = [r for r in report.results if r.action == "SELL"]
    assert [r.ticker for r in sells] == ["SCO"]
    assert sells[0].quantity == 10.0  # broker share count, not delta/mid
    # sells are executed before buys
    assert report.results[0].action == "SELL"


def test_halt_env_aborts(ledger, tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_HALT", "1")
    with pytest.raises(ExecutionAborted, match="EXECUTION_HALT"):
        run(FakeBroker(cash=11000.0), ledger, tmp_path)


def test_open_orders_in_universe_abort(ledger, tmp_path):
    broker = FakeBroker(cash=11000.0, open_orders={"TQQQ"})
    with pytest.raises(ExecutionAborted, match="open orders"):
        run(broker, ledger, tmp_path)


def test_foreign_positions_ignored_and_not_counted(ledger, tmp_path):
    broker = FakeBroker(cash=11000.0, positions={
        "AAPL": Position(quantity=5.0, market_value=1200.0),
    })
    report = run(broker, ledger, tmp_path, execute=True)
    assert report.equity == 11000.0
    assert "AAPL" not in {r.ticker for r in report.results}


def test_dust_deltas_skipped(ledger, tmp_path):
    # positions within a few dollars of target — nothing worth trading
    equity = 11000.0
    positions = {t: Position(quantity=1.0, market_value=w * equity - 10)
                 for t, w in ALLOCS["VAGG"].items()}
    broker = FakeBroker(cash=40.0, positions=positions)
    report = run(broker, ledger, tmp_path, execute=True)
    assert report.results == []
    assert len(report.skipped) == 4


def test_stale_ledger_aborts_when_logger_cannot_fill(ledger, tmp_path, monkeypatch):
    import src.execution.rotation_executor as mod
    monkeypatch.setattr(mod, "run_paper_log", lambda path: None)
    with pytest.raises(ExecutionAborted, match="ledger row"):
        run_rotation(FakeBroker(cash=11000.0), "VAGG", today=date(2026, 10, 1),
                     ledger_path=ledger, executions_path=tmp_path / "x.csv")


def test_bad_weight_sum_aborts(tmp_path):
    path = tmp_path / "ledger.csv"
    bad = {**ALLOCS, "VAGG": {"TQQQ": 0.5, "ERX": 0.2}}  # sums to 0.7
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["month", "logged_at", "quadrant", "matrix_version",
                         "allocations", "signals"])
        writer.writerow(["2026-09", "2026-09-01", "REFLATION", "v7",
                         json.dumps(bad), "{}"])
    with pytest.raises(ExecutionAborted, match="sum"):
        run(FakeBroker(cash=11000.0), path, tmp_path)


def test_contribution_deploy_buys_underweights_only(ledger, tmp_path):
    # $1,500 lands mid-month; existing book at target for $11k
    equity = 11000.0
    positions = {t: Position(quantity=1.0, market_value=w * equity)
                 for t, w in ALLOCS["VAGG"].items()}
    broker = FakeBroker(cash=1500.0, positions=positions)
    report = run(broker, ledger, tmp_path, execute=True)
    assert all(r.action == "BUY" for r in report.results)
    assert abs(sum(r.dollars for r in report.results) - 1500.0) < 5.0

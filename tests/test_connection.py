"""Tests for src.broker.connection. ib_insync.IB is mocked — no live Gateway required."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.broker import connection as connection_mod
from src.broker.connection import IBConnection, IBConnectionError


class _FakeIB:
    """Stand-in for ib_insync.IB. Tests mutate the public attributes to drive behavior."""

    def __init__(self):
        self._connected = False
        self._raise_on_connect: Exception | None = None
        self._accounts: list[str] = ["DU1234567"]
        self._summary: list = [
            SimpleNamespace(tag="NetLiquidation", value="8123.45"),
            SimpleNamespace(tag="BuyingPower", value="32493.80"),
        ]
        self._spy_ticker = SimpleNamespace(last=512.34, close=510.10)
        self._qualified: list = []
        self.client = SimpleNamespace(serverVersion=lambda: 178)

    def isConnected(self) -> bool:
        return self._connected

    def connect(self, host, port, clientId, timeout, readonly):  # noqa: ARG002
        if self._raise_on_connect is not None:
            raise self._raise_on_connect
        self._connected = True

    def disconnect(self):
        self._connected = False

    def managedAccounts(self):
        return list(self._accounts)

    def accountSummary(self):
        return list(self._summary)

    def qualifyContracts(self, *contracts):
        self._qualified.extend(contracts)
        return list(contracts)

    def reqMktData(self, contract, snapshot, regulatorySnapshot):  # noqa: ARG002
        return self._spy_ticker

    def cancelMktData(self, contract):  # noqa: ARG002
        pass

    def sleep(self, _):
        pass


@pytest.fixture
def fake_ib(monkeypatch) -> _FakeIB:
    fake = _FakeIB()
    monkeypatch.setattr(connection_mod, "IB", lambda: fake)
    monkeypatch.setattr(connection_mod.util, "startLoop", lambda: None)
    return fake


def test_connect_and_disconnect_lifecycle(fake_ib: _FakeIB):
    conn = IBConnection("127.0.0.1", 4002, 1)
    assert not conn.is_connected
    conn.connect()
    assert conn.is_connected
    conn.disconnect()
    assert not conn.is_connected


def test_context_manager_disconnects_on_exit(fake_ib: _FakeIB):
    with IBConnection("127.0.0.1", 4002, 1) as conn:
        assert conn.is_connected
    assert not conn.is_connected


def test_connect_refused_raises_typed_error(fake_ib: _FakeIB):
    fake_ib._raise_on_connect = ConnectionRefusedError("nope")
    with pytest.raises(IBConnectionError, match="failed to reach IB Gateway"):
        IBConnection("127.0.0.1", 4002, 1).connect()


def test_connect_timeout_raises_typed_error(fake_ib: _FakeIB):
    fake_ib._raise_on_connect = TimeoutError("slow")
    with pytest.raises(IBConnectionError):
        IBConnection("127.0.0.1", 4002, 1).connect()


def test_check_returns_summary_with_spy_quote(fake_ib: _FakeIB):
    with IBConnection("127.0.0.1", 4002, 1) as conn:
        result = conn.check()

    assert result.connected is True
    assert result.server_version == 178
    assert result.accounts == ["DU1234567"]
    assert result.net_liquidation == 8123.45
    assert result.buying_power == 32493.80
    assert result.spy_last == 512.34
    assert result.notes == []


def test_check_falls_back_to_close_when_last_is_none(fake_ib: _FakeIB):
    fake_ib._spy_ticker = SimpleNamespace(last=None, close=510.10)
    with IBConnection("127.0.0.1", 4002, 1) as conn:
        result = conn.check()
    assert result.spy_last == 510.10


def test_check_records_note_when_no_market_data(fake_ib: _FakeIB):
    fake_ib._spy_ticker = SimpleNamespace(last=None, close=None)
    with IBConnection("127.0.0.1", 4002, 1) as conn:
        result = conn.check()
    assert result.spy_last is None
    assert any("market data" in n.lower() for n in result.notes)


def test_check_without_connection_raises(fake_ib: _FakeIB):
    conn = IBConnection("127.0.0.1", 4002, 1)
    with pytest.raises(IBConnectionError, match="disconnected"):
        conn.check()

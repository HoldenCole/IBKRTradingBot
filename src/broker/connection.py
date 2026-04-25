"""Thin wrapper around ib_insync.IB with connect/disconnect lifecycle."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from ib_insync import IB, Stock, util
from loguru import logger


@dataclass
class ConnectionCheck:
    """Snapshot returned by IBConnection.check()."""

    connected: bool
    server_version: int | None
    accounts: list[str]
    net_liquidation: float | None
    buying_power: float | None
    spy_last: float | None
    notes: list[str]


class IBConnectionError(RuntimeError):
    """Raised when the IBKR connection fails or returns unusable state."""


class IBConnection(AbstractContextManager):
    """
    Wraps ib_insync.IB() with explicit connect/disconnect.

    Usage:
        with IBConnection(host, port, client_id) as conn:
            check = conn.check()
            ...
    """

    def __init__(
        self,
        host: str,
        port: int,
        client_id: int,
        connect_timeout_sec: float = 8.0,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connect_timeout_sec = connect_timeout_sec
        self.ib: IB = IB()

    # ---- lifecycle -------------------------------------------------------

    def connect(self) -> None:
        if self.ib.isConnected():
            logger.debug("ib_insync already connected; skipping connect()")
            return

        # ib_insync needs an event loop in non-async callers.
        util.startLoop()

        logger.info(
            "connecting to IBKR host={} port={} clientId={}",
            self.host,
            self.port,
            self.client_id,
        )
        try:
            self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.connect_timeout_sec,
                readonly=False,
            )
        except (TimeoutError, ConnectionRefusedError, OSError) as exc:
            raise IBConnectionError(
                f"failed to reach IB Gateway at {self.host}:{self.port} — "
                f"is Gateway running with API enabled? ({exc})"
            ) from exc

        if not self.ib.isConnected():
            raise IBConnectionError("IB.connect() returned without raising but isConnected()=False")

        logger.info(
            "connected: serverVersion={} accounts={}",
            self.ib.client.serverVersion(),
            self.ib.managedAccounts(),
        )

    def disconnect(self) -> None:
        if self.ib.isConnected():
            logger.info("disconnecting from IBKR")
            self.ib.disconnect()

    @property
    def is_connected(self) -> bool:
        return self.ib.isConnected()

    # ---- context manager -------------------------------------------------

    def __enter__(self) -> IBConnection:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.disconnect()

    # ---- diagnostics -----------------------------------------------------

    def check(self, market_data_timeout_sec: float = 4.0) -> ConnectionCheck:
        """
        Pull account summary and a SPY snapshot quote. Used by --check-connection.

        Market data may be delayed or unavailable depending on subscriptions; that
        path logs a warning but does not raise.
        """
        if not self.is_connected:
            raise IBConnectionError("check() called on a disconnected IBConnection")

        notes: list[str] = []

        accounts = list(self.ib.managedAccounts())
        if not accounts:
            notes.append("no managed accounts returned (account login may be incomplete)")

        summary = self.ib.accountSummary()
        nl = _account_value(summary, "NetLiquidation")
        bp = _account_value(summary, "BuyingPower")

        spy_last = self._try_spy_snapshot(market_data_timeout_sec, notes)

        return ConnectionCheck(
            connected=True,
            server_version=self.ib.client.serverVersion(),
            accounts=accounts,
            net_liquidation=nl,
            buying_power=bp,
            spy_last=spy_last,
            notes=notes,
        )

    def _try_spy_snapshot(self, timeout_sec: float, notes: list[str]) -> float | None:
        try:
            spy = Stock("SPY", "SMART", "USD")
            self.ib.qualifyContracts(spy)
            ticker = self.ib.reqMktData(spy, snapshot=True, regulatorySnapshot=False)
            self.ib.sleep(timeout_sec)

            price = ticker.last
            if price is None or _is_nan(price):
                price = ticker.close
            if price is None or _is_nan(price):
                notes.append("SPY snapshot returned no last/close — market data may not be subscribed")
                return None
            return float(price)
        except Exception as exc:  # broad: any IB error here is non-fatal for the check
            logger.warning("SPY snapshot failed: {}", exc)
            notes.append(f"SPY snapshot raised: {exc}")
            return None
        finally:
            try:
                self.ib.cancelMktData(spy)
            except Exception:
                pass


def _account_value(summary: list, tag: str) -> float | None:
    for row in summary:
        if row.tag == tag:
            try:
                return float(row.value)
            except (TypeError, ValueError):
                return None
    return None


def _is_nan(x: float) -> bool:
    return x != x  # noqa: PLR0124  (NaN check without importing math)

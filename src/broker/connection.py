"""IB() wrapper with reconnect logic.

Handles the nightly Gateway restart (~23:45 ET) by reconnecting with
exponential backoff. Import of ib_insync is kept inside this module so
pure-logic code (strategies, backtest, tests) never needs it installed.
"""

from __future__ import annotations

import time as _time

from loguru import logger

from src.config import Settings


class IBConnection:
    def __init__(self, settings: Settings):
        from ib_insync import IB  # local import: only needed when connecting

        self.settings = settings
        self.ib = IB()
        self.ib.disconnectedEvent += self._on_disconnect
        self._want_connected = False

    def connect(self) -> None:
        s = self.settings
        logger.info(f"Connecting to IBKR {s.ibkr_host}:{s.ibkr_port} clientId={s.ibkr_client_id}")
        self.ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id, timeout=20)
        self._want_connected = True
        logger.info("Connected: {}", self.ib.isConnected())

    def disconnect(self) -> None:
        self._want_connected = False
        if self.ib.isConnected():
            self.ib.disconnect()

    def _on_disconnect(self) -> None:
        if self._want_connected:
            logger.warning("Lost IBKR connection — will attempt reconnect")

    def ensure_connected(self, max_attempts: int = 8) -> None:
        """Reconnect with exponential backoff (2s, 4s, ... capped at 60s)."""
        if self.ib.isConnected():
            return
        delay = 2.0
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Reconnect attempt {attempt}/{max_attempts}")
                self.ib.connect(
                    self.settings.ibkr_host,
                    self.settings.ibkr_port,
                    clientId=self.settings.ibkr_client_id,
                    timeout=20,
                )
                logger.info("Reconnected")
                return
            except Exception as exc:  # noqa: BLE001 - retry on any connect error
                logger.warning(f"Reconnect failed: {exc}; sleeping {delay:.0f}s")
                _time.sleep(delay)
                delay = min(delay * 2, 60)
        raise ConnectionError(f"Could not reconnect after {max_attempts} attempts")

"""IBKR connection wrapper with retry/reconnect.

ib_insync is imported lazily so unit tests don't need it on the import path.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

from src.config import Config


@dataclass
class IBConnection:
    """Thin wrapper around ib_insync.IB. Owns the lifecycle.

    Real connection setup is intentionally minimal — connection details and
    qualification helpers live close to where they are used. Reconnect is
    handled with simple exponential backoff; nightly Gateway restart at
    ~23:45 ET is expected and surviving it is the bot's responsibility.
    """
    config: Config
    _ib: object = None  # IB instance, lazily imported

    def connect(self, max_attempts: int = 4) -> object:
        from ib_insync import IB  # lazy import

        if self._ib is None:
            self._ib = IB()

        delay = 2.0
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"connecting IBKR {self.config.ibkr_host}:{self.config.ibkr_port} "
                    f"clientId={self.config.ibkr_client_id} (attempt {attempt})"
                )
                self._ib.connect(
                    host=self.config.ibkr_host,
                    port=self.config.ibkr_port,
                    clientId=self.config.ibkr_client_id,
                    timeout=10,
                )
                logger.info("IBKR connected")
                return self._ib
            except Exception as exc:
                logger.warning(f"connect attempt {attempt} failed: {exc!r}")
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    def disconnect(self) -> None:
        if self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception as exc:
                logger.warning(f"disconnect raised: {exc!r}")

    def is_connected(self) -> bool:
        return self._ib is not None and bool(getattr(self._ib, "isConnected", lambda: False)())

    async def watchdog(self, check_interval_sec: float = 30.0) -> None:
        """Background task: reconnect if the socket drops."""
        while True:
            await asyncio.sleep(check_interval_sec)
            if not self.is_connected():
                logger.warning("watchdog: connection dropped, reconnecting")
                try:
                    self.connect()
                except Exception as exc:
                    logger.error(f"watchdog reconnect failed: {exc!r}")

"""Regime filter client.

Spec: regime is per-underlying. SPY can be ON while QQQ is OFF. If unreachable
or errors out, fail closed (treat as OFF).

The user owns the regime service in a separate repo. Expected contract:
    GET {REGIME_BASE_URL}/regime/{symbol}  ->  {"active": true|false, "ts": "..."}
If the contract differs, override RegimeClient.fetch() in a subclass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
from loguru import logger


class RegimeProvider(Protocol):
    def is_active(self, symbol: str) -> bool: ...


@dataclass
class StaticRegime:
    """For tests/dev. Pass a dict of {symbol: bool}."""
    states: dict[str, bool]

    def is_active(self, symbol: str) -> bool:
        return bool(self.states.get(symbol.upper(), False))


@dataclass
class HttpRegime:
    base_url: str
    timeout_sec: float = 2.0

    def is_active(self, symbol: str) -> bool:
        try:
            r = httpx.get(
                f"{self.base_url.rstrip('/')}/regime/{symbol.upper()}",
                timeout=self.timeout_sec,
            )
            r.raise_for_status()
            data = r.json()
            return bool(data.get("active", False))
        except Exception as exc:  # fail-closed
            logger.warning(f"regime fetch failed for {symbol}: {exc!r} -> treating as OFF")
            return False


def make_regime_provider(base_url: str | None, timeout_sec: float) -> RegimeProvider:
    if not base_url:
        # No URL configured: fail-closed (everything OFF).
        return StaticRegime(states={})
    return HttpRegime(base_url=base_url, timeout_sec=timeout_sec)

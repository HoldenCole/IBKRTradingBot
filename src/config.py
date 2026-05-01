"""Environment-driven config. Load once at startup; pass the object around."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    ibkr_host: str
    ibkr_port: int
    ibkr_client_id: int

    mode: str  # "paper" | "live"

    log_level: str
    log_dir: Path

    weekly_loss_budget_usd: float
    per_trade_risk_cap_usd: float
    max_concurrent_positions: int
    max_gross_premium_pct: float
    soft_gate_pct: float
    overnight_risk_multiplier: float

    regime_base_url: str | None
    regime_timeout_sec: float

    econ_calendar_provider: str
    fmp_api_key: str | None

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


def _env(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {key}")
    return val if val is not None else ""


def load_config(env_file: str | os.PathLike | None = ".env") -> Config:
    if env_file:
        load_dotenv(env_file, override=False)

    mode = _env("MODE", "paper").lower()
    if mode not in {"paper", "live"}:
        raise ValueError(f"MODE must be 'paper' or 'live', got {mode!r}")

    return Config(
        ibkr_host=_env("IBKR_HOST", "127.0.0.1"),
        ibkr_port=int(_env("IBKR_PORT", "4002")),
        ibkr_client_id=int(_env("IBKR_CLIENT_ID", "1")),
        mode=mode,
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        log_dir=Path(_env("LOG_DIR", "logs")),
        weekly_loss_budget_usd=float(_env("WEEKLY_LOSS_BUDGET_USD", "500")),
        per_trade_risk_cap_usd=float(_env("PER_TRADE_RISK_CAP_USD", "200")),
        max_concurrent_positions=int(_env("MAX_CONCURRENT_POSITIONS", "2")),
        max_gross_premium_pct=float(_env("MAX_GROSS_PREMIUM_PCT", "0.60")),
        soft_gate_pct=float(_env("SOFT_GATE_PCT", "0.70")),
        overnight_risk_multiplier=float(_env("OVERNIGHT_RISK_MULTIPLIER", "1.5")),
        regime_base_url=(_env("REGIME_BASE_URL", "") or None),
        regime_timeout_sec=float(_env("REGIME_TIMEOUT_SEC", "2.0")),
        econ_calendar_provider=_env("ECON_CALENDAR_PROVIDER", "stub").lower(),
        fmp_api_key=(_env("FMP_API_KEY", "") or None),
    )

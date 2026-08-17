"""Environment-driven settings. Paper mode is the default; live requires
both MODE=live and the --i-understand-the-risk CLI flag."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ibkr_host: str
    ibkr_port: int
    ibkr_client_id: int
    mode: str  # "paper" | "live"
    log_level: str
    max_position_usd: float
    max_daily_loss_usd: float

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


def load_settings() -> Settings:
    mode = os.getenv("MODE", "paper").strip().lower()
    if mode not in ("paper", "live"):
        raise ValueError(f"MODE must be 'paper' or 'live', got {mode!r}")

    max_position = float(os.getenv("MAX_POSITION_USD", "500"))
    max_daily_loss = float(os.getenv("MAX_DAILY_LOSS_USD", "200"))
    if max_position <= 0 or max_daily_loss <= 0:
        raise ValueError("MAX_POSITION_USD and MAX_DAILY_LOSS_USD must be positive")

    return Settings(
        ibkr_host=os.getenv("IBKR_HOST", "127.0.0.1"),
        ibkr_port=int(os.getenv("IBKR_PORT", "4002")),
        ibkr_client_id=int(os.getenv("IBKR_CLIENT_ID", "1")),
        mode=mode,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        max_position_usd=max_position,
        max_daily_loss_usd=max_daily_loss,
    )

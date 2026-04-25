"""Runtime configuration loaded from environment / .env file."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # IBKR connection
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = Field(default=4002, ge=1024, le=65535)
    ibkr_client_id: int = Field(default=1, ge=0, le=999)

    # Mode
    mode: Mode = Mode.PAPER

    # Logging
    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    # Risk caps (defaults mirror STRATEGIES.md v1.2)
    weekly_loss_budget_usd: float = Field(default=500.0, gt=0)
    per_trade_risk_cap_usd: float = Field(default=200.0, gt=0)
    max_gross_premium_pct_nav: float = Field(default=0.40, gt=0, le=1.0)
    max_concurrent_positions: int = Field(default=2, ge=1, le=10)

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid LOG_LEVEL: {v}")
        return v

    @property
    def is_paper(self) -> bool:
        return self.mode is Mode.PAPER

    @property
    def is_live(self) -> bool:
        return self.mode is Mode.LIVE

    def assert_live_authorized(self, risk_flag: bool) -> None:
        """Live mode requires the explicit --i-understand-the-risk runtime flag."""
        if self.is_live and not risk_flag:
            raise RuntimeError(
                "MODE=live requires --i-understand-the-risk on the command line. "
                "Refusing to start."
            )


def load_settings() -> Settings:
    """Factory so tests can monkeypatch env without import-time side effects."""
    return Settings()

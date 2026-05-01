"""Wiring helpers — pick concrete implementations from config."""
from __future__ import annotations

from src.config import Config
from src.risk.blackout import BlackoutChecker, StubCalendar
from src.risk.regime import make_regime_provider


def make_blackout_checker(cfg: Config) -> BlackoutChecker:
    if cfg.econ_calendar_provider == "fmp":
        if not cfg.fmp_api_key:
            raise RuntimeError("ECON_CALENDAR_PROVIDER=fmp but FMP_API_KEY is empty")
        from src.data.fmp import FMPCalendar
        return BlackoutChecker(FMPCalendar(api_key=cfg.fmp_api_key))
    # stub: empty calendar -> never blocks. Useful for dev/CI; in prod set to fmp.
    return BlackoutChecker(StubCalendar([]))


def make_regime(cfg: Config):
    return make_regime_provider(cfg.regime_base_url, cfg.regime_timeout_sec)

"""Entrypoint: `python -m src.main [--check-connection|--strategy ...]`."""

from __future__ import annotations

import argparse
import sys

from loguru import logger

from src.broker.connection import IBConnection, IBConnectionError
from src.config import Mode, load_settings
from src.logging_setup import configure_logging


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ibkr-bot", description="IBKR options trading bot")
    p.add_argument(
        "--check-connection",
        action="store_true",
        help="Connect to IB Gateway, pull account summary + SPY quote, then exit.",
    )
    p.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Strategy name to run (not implemented yet).",
    )
    p.add_argument(
        "--mode",
        choices=[m.value for m in Mode],
        default=None,
        help="Override MODE env var (paper|live). Defaults to env.",
    )
    p.add_argument(
        "--i-understand-the-risk",
        dest="risk_flag",
        action="store_true",
        help="Required to start in live mode. Without it, live mode is rejected.",
    )
    return p


def _print_check(check) -> None:
    print("=== IBKR Connection Check ===")
    print(f"  Connected:        {check.connected}")
    print(f"  Server version:   {check.server_version}")
    print(f"  Accounts:         {check.accounts or '<none>'}")
    print(f"  NetLiquidation:   {check.net_liquidation if check.net_liquidation is not None else '?'}")
    print(f"  BuyingPower:      {check.buying_power if check.buying_power is not None else '?'}")
    print(f"  SPY last/close:   {check.spy_last if check.spy_last is not None else '?'}")
    if check.notes:
        print("  Notes:")
        for n in check.notes:
            print(f"    - {n}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = load_settings()

    if args.mode is not None:
        settings = settings.model_copy(update={"mode": Mode(args.mode)})

    settings.assert_live_authorized(args.risk_flag)

    configure_logging(settings.log_level, settings.log_dir)
    logger.info(
        "starting ibkr-bot mode={} host={} port={} clientId={}",
        settings.mode.value,
        settings.ibkr_host,
        settings.ibkr_port,
        settings.ibkr_client_id,
    )

    if args.check_connection:
        try:
            with IBConnection(
                host=settings.ibkr_host,
                port=settings.ibkr_port,
                client_id=settings.ibkr_client_id,
            ) as conn:
                check = conn.check()
            _print_check(check)
            return 0
        except IBConnectionError as exc:
            logger.error("connection check failed: {}", exc)
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    if args.strategy:
        logger.error("--strategy is not implemented yet")
        print("Strategy runner is not implemented yet.", file=sys.stderr)
        return 2

    print("Nothing to do. Try --check-connection.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

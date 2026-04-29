"""CLI entrypoint.

Subcommands:
  --check-connection : ping IBKR, print account summary
  --strategy <name>  : run a registered strategy
  --backtest         : run against historical data instead of live
  --mode live --i-understand-the-risk : opt-in to live trading
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger

from src.config import load_config
from src.logging_setup import configure_logging


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ibkrbot", description="IBKR trading bot")
    p.add_argument("--check-connection", action="store_true",
                   help="Connect, print account summary, exit.")
    p.add_argument("--strategy", help="Strategy name: ewo | ibs | afternoon")
    p.add_argument("--backtest", action="store_true")
    p.add_argument("--from", dest="from_date")
    p.add_argument("--to", dest="to_date")
    p.add_argument("--mode", choices=("paper", "live"))
    p.add_argument("--i-understand-the-risk", action="store_true",
                   help="Required for --mode live.")
    args = p.parse_args(argv)

    cfg = load_config()
    configure_logging(cfg.log_dir, cfg.log_level)

    if args.mode == "live":
        if not args.i_understand_the_risk:
            logger.error("Live mode requires --i-understand-the-risk")
            return 2
        if cfg.mode != "live":
            logger.error("Config MODE != live; refusing to override silently. "
                         "Set MODE=live in .env first.")
            return 2

    if args.check_connection:
        return _check_connection(cfg)

    if args.strategy:
        if args.backtest:
            logger.warning("Backtest engine not implemented yet — see roadmap.")
            return 1
        logger.warning("Live runner not implemented yet — see roadmap.")
        return 1

    p.print_help()
    return 0


def _check_connection(cfg) -> int:
    from src.broker.connection import IBConnection

    conn = IBConnection(cfg)
    try:
        ib = conn.connect()
        summary = ib.accountSummary()
        logger.info(f"Connected: True. Account summary rows: {len(summary)}")
        for row in summary[:10]:
            logger.info(f"  {row.tag}={row.value} ({row.currency})")
        return 0
    except Exception as exc:
        logger.error(f"check-connection failed: {exc!r}")
        return 1
    finally:
        conn.disconnect()


if __name__ == "__main__":
    sys.exit(cli())

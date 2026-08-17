"""Entrypoint.

    python -m src.main --check-connection
    python -m src.main --fetch-data --days 30
    python -m src.main --backtest --cl data/cl_1min.csv --uso data/uso_1min.csv
    python -m src.main --strategy cl1_uso_spread                     # paper
    python -m src.main --strategy cl1_uso_spread --mode live --i-understand-the-risk
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from loguru import logger

from src.config import load_settings


def _setup_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days", level=level)


def cmd_check_connection(settings) -> None:
    from src.broker.connection import IBConnection
    from src.data.market_data import qualify_uso

    conn = IBConnection(settings)
    conn.connect()
    ib = conn.ib
    for row in ib.accountSummary():
        if row.tag in ("NetLiquidation", "AvailableFunds", "BuyingPower"):
            logger.info(f"{row.tag}: {row.value} {row.currency}")
    uso = qualify_uso(ib)
    ticker = ib.reqMktData(uso)
    ib.sleep(3)
    logger.info(f"USO quote: bid={ticker.bid} ask={ticker.ask} last={ticker.last}")
    logger.info(f"Connected: {ib.isConnected()}")
    conn.disconnect()


def cmd_fetch_data(settings, days: int) -> None:
    from src.broker.connection import IBConnection
    from src.data.market_data import fetch_minute_bars, front_month_cl, qualify_uso, save_bars

    conn = IBConnection(settings)
    conn.connect()
    ib = conn.ib
    uso = qualify_uso(ib)
    cl = front_month_cl(ib)
    logger.info(f"Fetching {days} days of 1-min bars (RTH) for USO and {cl.localSymbol}")
    save_bars(fetch_minute_bars(ib, uso, days), "uso")
    save_bars(fetch_minute_bars(ib, cl, days), "cl")
    conn.disconnect()
    logger.info("Done. Run the backtest with: "
                "python -m src.main --backtest --cl data/cl_1min.csv --uso data/uso_1min.csv")


def cmd_backtest(
    cl_path: str, uso_path: str, sizes: list[float], execution: str
) -> None:
    from src.data.market_data import load_bars

    cl = load_bars(cl_path)
    uso = load_bars(uso_path)
    logger.info(f"Loaded {len(cl)} CL bars, {len(uso)} USO bars")

    last_trades = None
    for size in sizes:
        if execution == "options":
            from src.backtest.options_engine import OptionsBacktestConfig, run_options_backtest

            result = run_options_backtest(cl, uso, OptionsBacktestConfig(position_usd=size))
        else:
            from src.backtest.engine import BacktestConfig, run_backtest

            result = run_backtest(cl, uso, BacktestConfig(position_usd=size))
        print(result.summary())
        print()
        last_trades = result.trades

    if last_trades is not None and not last_trades.empty:
        out = Path("logs") / f"backtest_trades_{execution}.csv"
        out.parent.mkdir(exist_ok=True)
        last_trades.to_csv(out, index=False)
        print(f"Trade log ({execution}, ${sizes[-1]:.0f}) written to {out}")


def cmd_run(settings) -> None:
    from src.live_runner import LiveRunner

    LiveRunner(settings).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="IBKR trading bot — CL1/USO spread")
    parser.add_argument("--check-connection", action="store_true")
    parser.add_argument("--fetch-data", action="store_true")
    parser.add_argument("--days", type=int, default=30, help="days of history for --fetch-data")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--cl", default="data/cl_1min.csv", help="CL 1-min CSV for --backtest")
    parser.add_argument("--uso", default="data/uso_1min.csv", help="USO 1-min CSV for --backtest")
    parser.add_argument("--position-usd", type=float, default=None)
    parser.add_argument(
        "--sweep", default=None,
        help="comma-separated position sizes for --backtest, e.g. 1000,2000,4000",
    )
    parser.add_argument(
        "--execution", choices=["shares", "options"], default="shares",
        help="backtest execution model (default: shares)",
    )
    parser.add_argument("--strategy", choices=["cl1_uso_spread"])
    parser.add_argument("--mode", choices=["paper", "live"], default=None)
    parser.add_argument("--i-understand-the-risk", action="store_true", dest="risk_ack")
    args = parser.parse_args()

    settings = load_settings()
    if args.mode:
        settings = replace(settings, mode=args.mode)
    _setup_logging(settings.log_level)

    if settings.is_live and not args.risk_ack:
        parser.error("live mode requires --i-understand-the-risk")
    if settings.is_live:
        logger.warning("LIVE MODE — real money. Position cap ${:.0f}, daily loss cap ${:.0f}",
                       settings.max_position_usd, settings.max_daily_loss_usd)

    if args.check_connection:
        cmd_check_connection(settings)
    elif args.fetch_data:
        cmd_fetch_data(settings, args.days)
    elif args.backtest:
        if args.sweep:
            sizes = [float(s) for s in args.sweep.split(",")]
        else:
            sizes = [args.position_usd or settings.max_position_usd]
        cmd_backtest(args.cl, args.uso, sizes, args.execution)
    elif args.strategy:
        cmd_run(settings)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

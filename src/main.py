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
            return _run_backtest(cfg, args.strategy, args.from_date, args.to_date)
        return _run_live(cfg)

    p.print_help()
    return 0


def _run_backtest(cfg, strategy_filter: str | None, from_date: str | None,
                  to_date: str | None) -> int:
    """Pull historical bars from FMP and run the backtest engine.

    `--strategy` here is a *filter* over the registered strategies (e.g.
    'ewo' to run EWO alone, 'all' for everything). Afternoon Reversion is
    skipped because we don't have multi-year intraday data.
    """
    from datetime import date
    from src.backtest.engine import BacktestConfig, BacktestEngine
    from src.backtest.report import compute_metrics, format_report
    from src.data.fmp import FMPHistorical
    from src.strategies.ewo import EWOStrategy
    from src.strategies.ibs import IBSStrategy

    if not cfg.fmp_api_key:
        logger.error("Backtest needs FMP_API_KEY in env")
        return 2
    if not from_date or not to_date:
        logger.error("Backtest requires --from YYYY-MM-DD --to YYYY-MM-DD")
        return 2

    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    fmp = FMPHistorical(api_key=cfg.fmp_api_key)

    # Pull a buffer of 400 bars before `start` so SMA(200), EWO z-score
    # (252-day lookback) etc. have history.
    from datetime import timedelta
    buffer_start = (start - timedelta(days=600)).isoformat()

    daily_bars = {}
    etf_bars = {}
    for sym in ("SPY", "QQQ"):
        df = fmp.daily(sym, buffer_start, end.isoformat())
        if df.empty:
            logger.error(f"no daily bars from FMP for {sym}")
            return 1
        daily_bars[sym] = df
    for etf in ("UPRO", "TQQQ", "SQQQ"):
        df = fmp.daily(etf, buffer_start, end.isoformat())
        if df.empty:
            logger.error(f"no daily bars from FMP for {etf}")
            return 1
        etf_bars[etf] = df

    # Strategy selection
    requested = (strategy_filter or "all").lower()
    if requested == "afternoon":
        logger.error(
            "afternoon reversion backtest needs multi-year intraday data; "
            "FMP free tier doesn't cover it. Run live in paper to validate."
        )
        return 2
    strategies = []
    if requested in ("ewo", "all"):
        strategies.append(EWOStrategy())
    if requested in ("ibs", "all"):
        strategies.append(IBSStrategy())
    if not strategies:
        logger.error(f"unknown strategy filter: {requested!r}")
        return 2

    bcfg = BacktestConfig(
        start=start, end=end,
        initial_capital=8000.0,
        weekly_loss_budget=cfg.weekly_loss_budget_usd,
        per_trade_risk_cap=cfg.per_trade_risk_cap_usd,
        max_concurrent_positions=cfg.max_concurrent_positions,
        max_gross_premium_pct=cfg.max_gross_premium_pct,
        soft_gate_pct=cfg.soft_gate_pct,
        overnight_multiplier=cfg.overnight_risk_multiplier,
    )
    engine = BacktestEngine(
        config=bcfg,
        strategies=strategies,
        daily_bars=daily_bars,
        underlying_etf_bars=etf_bars,
    )
    result = engine.run()
    metrics = compute_metrics(result)
    print(format_report(result, metrics))
    return 0


def _run_live(cfg) -> int:
    """Wire LiveRunner against IBKR + paper account, then enter the scheduling loop.

    The scheduling loop itself is intentionally minimal: it sleeps until the
    next phase boundary (daily close, session open, intraday tick, EOD) and
    calls the corresponding method on LiveRunner. A supervisor (systemd /
    supervisord) restarts the process on crash; LiveRunner.on_startup() loads
    state from disk so we resume mid-stream.
    """
    import asyncio
    from datetime import date, datetime, time, timedelta
    from pathlib import Path
    from zoneinfo import ZoneInfo

    from src.broker.connection import IBConnection
    from src.positions.manager import PositionManager
    from src.risk.guardrails import Guardrails
    from src.risk.weekly_budget import WeeklyBudget
    from src.runner.ibkr_adapter import IBKRBroker, IBKRDataFeed
    from src.runner.runner import LiveRunner
    from src.runner.store import PositionStore
    from src.strategies.afternoon import AfternoonReversionStrategy
    from src.strategies.ewo import EWOStrategy
    from src.strategies.ibs import IBSStrategy
    from src.wiring import make_blackout_checker, make_regime

    ET = ZoneInfo("America/New_York")

    conn = IBConnection(cfg)
    ib = conn.connect()
    try:
        broker = IBKRBroker(ib=ib)
        feed = IBKRDataFeed(ib=ib)
        budget = WeeklyBudget(
            budget=cfg.weekly_loss_budget_usd,
            soft_gate_pct=cfg.soft_gate_pct,
            overnight_multiplier=cfg.overnight_risk_multiplier,
        )
        store = PositionStore(path=Path(cfg.log_dir).parent / "state" / "positions.json")
        pm, deferred = store.load(budget)

        blackout = make_blackout_checker(cfg)
        regime = make_regime(cfg)
        guardrails = Guardrails(
            budget=budget, blackout=blackout, regime=regime,
            per_trade_risk_cap=cfg.per_trade_risk_cap_usd,
            max_concurrent_positions=cfg.max_concurrent_positions,
            max_gross_premium_pct=cfg.max_gross_premium_pct,
        )
        runner = LiveRunner(
            broker=broker, feed=feed, pm=pm, budget=budget,
            guardrails=guardrails, blackout=blackout,
            daily_strategies=[EWOStrategy(), IBSStrategy()],
            intraday_strategy=AfternoonReversionStrategy(),
            store=store, deferred=deferred,
        )
        asyncio.run(_runner_loop(runner))
        return 0
    except KeyboardInterrupt:
        logger.info("interrupted; shutting down")
        return 0
    except Exception as exc:
        logger.exception(f"runner crashed: {exc!r}")
        return 1
    finally:
        conn.disconnect()


async def _runner_loop(runner) -> None:
    """Phase scheduler. Tight enough to not need APScheduler; explicit enough
    to debug.
    """
    import asyncio
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    await runner.on_startup()

    fired_today = {"open": None, "close": None, "eod": None}

    while True:
        now = datetime.now(tz=ET)
        today = now.date()

        # 09:31 ET — drain deferred entries
        if now.time() >= time(9, 31) and now.time() < time(11, 0) \
                and fired_today["open"] != today:
            await runner.on_session_open(today)
            fired_today["open"] = today

        # 11:00-11:30 ET — afternoon-reversion intraday loop is driven by the
        # broker's bar subscription in production. A minimal poll-based version
        # would fetch the latest 5-min bar and call on_intraday_bar. We leave
        # that to the production wiring; for now we just step exits during
        # this window.

        # 16:05 ET — daily close pass
        if now.time() >= time(16, 5) and now.time() < time(16, 30) \
                and fired_today["close"] != today:
            await runner.on_daily_close(today)
            fired_today["close"] = today

        # 16:00 ET — session-close exits + overnight bookkeeping
        if now.time() >= time(16, 0) and now.time() < time(16, 5) \
                and fired_today["eod"] != today:
            await runner.on_session_close(today)
            fired_today["eod"] = today

        # Reset fire-flags at midnight
        if now.time() < time(0, 5):
            fired_today = {"open": None, "close": None, "eod": None}

        await asyncio.sleep(15)


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

"""XLK vs QQQ period sensitivity — splits 2018-2026 into 2018-2023 and 2024-2026
to test whether XLK's in-sample edge is concentrated in the AAPL/MSFT/NVDA
dominance period (2024-2026).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

from src.backtest.benchmark import equity_metrics
from src.data import yahoo
from src.data.fred import fetch_tbill_3m
from scripts.run_tbill_etf_inverse import (
    bah_on_trend_with_tbill, daily_tbill_factor, slice_close,
)


def main() -> int:
    full_start = date(2000, 1, 3)
    full_end = date(2026, 4, 15)

    print("Fetching XLK, QQQ, T-bill...")
    xlk = yahoo.daily("XLK", full_start.isoformat(), full_end.isoformat())
    qqq = yahoo.daily("QQQ", full_start.isoformat(), full_end.isoformat())
    tbill_pct = fetch_tbill_3m(
        full_start.isoformat(), full_end.isoformat(),
        cache_dir=REPO / "data" / "fred_cache",
    )["close"]
    tbill_daily = daily_tbill_factor(tbill_pct)

    periods = [
        ("2000-2009 (regime shift)", date(2000, 1, 3),  date(2009, 12, 31)),
        ("2010-2017 (held-out)",     date(2010, 1, 1),  date(2017, 12, 31)),
        ("2018-2023 (pre-AI-mega)",  date(2018, 1, 1),  date(2023, 12, 31)),
        ("2024-2026 (AI dominance)", date(2024, 1, 1),  date(2026, 4, 15)),
        ("2018-2026 (full sample)",  date(2018, 1, 1),  date(2026, 4, 15)),
    ]

    print(f"\n{'Period':30s}  {'XLK Sortino':>12s}  {'QQQ Sortino':>12s}  "
          f"{'Δ Sortino':>10s}  {'XLK CAGR':>9s}  {'QQQ CAGR':>9s}  {'Δ CAGR':>8s}")
    print("-" * 110)

    for plabel, ps, pe in periods:
        xlk_close = slice_close(xlk, ps, pe)
        qqq_close = slice_close(qqq, ps, pe)
        if xlk_close.empty or qqq_close.empty or len(qqq_close) < 250:
            continue
        xlk_eq, _ = bah_on_trend_with_tbill(xlk_close, tbill_daily, 8000.0, 1.0)
        qqq_eq, _ = bah_on_trend_with_tbill(qqq_close, tbill_daily, 8000.0, 1.0)
        mx = equity_metrics(xlk_eq, 8000.0)
        mq = equity_metrics(qqq_eq, 8000.0)
        d_sortino = mx["sortino"] - mq["sortino"]
        d_cagr = (mx["cagr"] - mq["cagr"]) * 100
        print(f"  {plabel:30s}  {mx['sortino']:>10.2f}    {mq['sortino']:>10.2f}    "
              f"{d_sortino:>+8.2f}   {mx['cagr']:>+7.1%}   {mq['cagr']:>+7.1%}   "
              f"{d_cagr:>+5.1f}pp")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

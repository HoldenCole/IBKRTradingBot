"""Pull historical 5-minute bars from IBKR for SPY and QQQ, 2018-present.

Used as the data source for Phase 5 (afternoon reversion). FMP free tier
caps intraday history at ~30 days; IBKR provides longer history with the
caveat of pacing limits and 1-day-at-a-time chunking.

Designed to run on the operator's machine where IB Gateway is logged in
and accessible at the configured port. Resumable: skips dates already
present in the cache directory. Throttled to stay under IBKR's pacing
limits (60 historical-data requests per 10 minutes; we sleep 11 seconds
between requests for safe margin).

Estimated runtime for 2018-01-01 to today on SPY+QQQ:
  ~520 weeks * 5 days * 2 symbols = ~5,200 requests
  At 11s/request = ~16 hours. Run overnight on a weekend.

Output: data/intraday/{symbol}/{YYYY-MM-DD}.parquet — one file per
trading day per symbol. Loadable later via:

    df = pd.concat([
        pd.read_parquet(p)
        for p in sorted(Path("data/intraday/SPY").glob("*.parquet"))
    ])

Usage (with Gateway running on paper port 4002):
    .\\.venv\\Scripts\\python.exe scripts\\pull_ibkr_5min.py
    .\\.venv\\Scripts\\python.exe scripts\\pull_ibkr_5min.py --symbols SPY
    .\\.venv\\Scripts\\python.exe scripts\\pull_ibkr_5min.py --start 2024-01-01

Stop and restart any time; resumes where it left off.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", default=["SPY", "QQQ"])
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=None, help="default = today")
    p.add_argument("--port", type=int, default=4002)
    p.add_argument("--client-id", type=int, default=42,
                   help="MUST differ from the live bot's IBKR_CLIENT_ID")
    p.add_argument("--throttle-sec", type=float, default=11.0)
    p.add_argument("--cache-dir", default=str(REPO / "data" / "intraday"))
    args = p.parse_args()

    # Lazy imports so the CLI help works without ib_insync installed.
    try:
        from ib_insync import IB, Stock, util
    except ImportError:
        print("ERROR: ib_insync not installed. Run `pip install ib_insync` "
              "or `pip install -e .` from the repo root.", file=sys.stderr)
        return 1
    import pandas as pd

    cache_root = Path(args.cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)

    start_d = date.fromisoformat(args.start)
    end_d = date.fromisoformat(args.end) if args.end else date.today()

    ib = IB()
    print(f"connecting to 127.0.0.1:{args.port} clientId={args.client_id}")
    ib.connect("127.0.0.1", args.port, clientId=args.client_id, timeout=10)
    if not ib.isConnected():
        print("ERROR: failed to connect", file=sys.stderr)
        return 1

    try:
        for sym in args.symbols:
            sym_dir = cache_root / sym
            sym_dir.mkdir(parents=True, exist_ok=True)
            contract = Stock(sym, "SMART", "USD")
            ib.qualifyContracts(contract)

            d = start_d
            while d <= end_d:
                if d.weekday() >= 5:  # weekend
                    d += timedelta(days=1)
                    continue

                out = sym_dir / f"{d.isoformat()}.parquet"
                if out.exists():
                    d += timedelta(days=1)
                    continue

                # IBKR requires endDateTime as the END of the day's session.
                end_dt = datetime.combine(d, datetime.min.time()).replace(hour=21, minute=0)
                end_str = end_dt.strftime("%Y%m%d-%H:%M:%S")

                try:
                    bars = ib.reqHistoricalData(
                        contract,
                        endDateTime=end_str,
                        durationStr="1 D",
                        barSizeSetting="5 mins",
                        whatToShow="TRADES",
                        useRTH=True,
                        formatDate=1,
                    )
                except Exception as exc:
                    print(f"  {sym} {d}: ERROR {exc!r} — sleeping 30s and retrying once")
                    time.sleep(30)
                    try:
                        bars = ib.reqHistoricalData(
                            contract, endDateTime=end_str, durationStr="1 D",
                            barSizeSetting="5 mins", whatToShow="TRADES",
                            useRTH=True, formatDate=1,
                        )
                    except Exception as exc2:
                        print(f"  {sym} {d}: ERROR (2) {exc2!r} — skipping date")
                        bars = []

                if bars:
                    df = util.df(bars)
                    df.to_parquet(out)
                    print(f"  {sym} {d}: {len(df)} bars")
                else:
                    # Likely a market holiday — write an empty marker so
                    # we don't retry on next run.
                    out.with_suffix(".empty").touch()
                    print(f"  {sym} {d}: empty (likely holiday)")

                time.sleep(args.throttle_sec)
                d += timedelta(days=1)

    finally:
        ib.disconnect()

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Minute bid/ask forex bars for the intraday test harness.

Source: FXCM's public historical candle repository (no key), one gzip CSV per
pair per week: https://candledata.fxcorporate.com/m1/{PAIR}/{YEAR}/{WEEK}.csv.gz
Columns: DateTime (UTC, MM/DD/YYYY HH:MM:SS.fff), Bid OHLC, Ask OHLC. Coverage
found on 2026-11-26: 2012 week 1 to 2026 week 46.

Why not Dukascopy: its free datafeed now answers 429 and points to a paid
AWS requester-pays bucket (checked 2026-11-26).

This is ONE dealer's quotes. The harness never trusts its spread to be the
cost: fills use max(feed spread, the venue's base spread) times a stress
factor (costs.py).

Cache: research/cache/fx/{PAIR}_{YEAR}.parquet. The loader refuses dates in
the hold-out window unless the caller passes the token from registry.open_holdout.
"""
from __future__ import annotations

import gzip
import io
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "research" / "cache" / "fx"
URL = "https://candledata.fxcorporate.com/m1/{pair}/{year}/{week}.csv.gz"
PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "EURGBP", "AUDNZD")
FIRST_YEAR = 2012
COLS = ["bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"]

# Hold-out: the most recent ~two years, opened once per rule (registry.py).
DEV_START = pd.Timestamp("2012-01-01", tz="UTC")
HOLDOUT_START = pd.Timestamp("2024-12-01", tz="UTC")


def pip(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


def _fetch_week(pair: str, year: int, week: int) -> pd.DataFrame | None:
    from src.data.yahoo import _ssl_context
    url = URL.format(pair=pair, year=year, week=week)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
                content = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
            continue
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(2 * (attempt + 1))
            continue
        try:
            raw = gzip.decompress(content)
        except (EOFError, OSError):           # truncated transfer: retry
            time.sleep(2 * (attempt + 1))
            continue
        if not raw.strip():
            return None
        try:
            df = pd.read_csv(io.BytesIO(raw))
        except pd.errors.EmptyDataError:
            return None
        if df.empty:
            return None
        df.columns = ["time"] + COLS
        df["time"] = pd.to_datetime(df["time"], format="%m/%d/%Y %H:%M:%S.%f", utc=True)
        return df
    # Some source files are persistently truncated (e.g. 2025 week 2): treat as missing, say so.
    print(f"  WARNING {url}: unreadable after retries, treated as missing", file=sys.stderr, flush=True)
    return None


def fetch_year(pair: str, year: int, workers: int = 6) -> pd.DataFrame:
    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(lambda w: _fetch_week(pair, year, w), range(1, 54)))
    parts = [p for p in parts if p is not None and len(p)]
    if not parts:
        return pd.DataFrame(columns=["time"] + COLS)
    df = pd.concat(parts).drop_duplicates("time").sort_values("time")
    df = df[df["time"].dt.year == year]          # week 1 / 53 can straddle years
    return df.reset_index(drop=True)


def download(pairs=PAIRS, years=None, refresh_current=True) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    years = years or range(FIRST_YEAR, pd.Timestamp.now(tz="UTC").year + 1)
    this_year = pd.Timestamp.now(tz="UTC").year
    for pair in pairs:
        for y in years:
            f = CACHE / f"{pair}_{y}.parquet"
            if f.exists() and not (refresh_current and y == this_year):
                continue
            t0 = time.time()
            df = fetch_year(pair, y)
            df.to_parquet(f, index=False)
            print(f"{pair} {y}: {len(df):,} bars in {time.time() - t0:.0f}s", flush=True)


class HoldoutLocked(RuntimeError):
    pass


def load(pair: str, start=None, end=None, holdout_token: str | None = None) -> pd.DataFrame:
    """Minute bars indexed by UTC time. Dates on or after HOLDOUT_START need a token."""
    start = pd.Timestamp(start or DEV_START)
    end = pd.Timestamp(end or "2100-01-01")
    start = start.tz_localize("UTC") if start.tzinfo is None else start
    end = end.tz_localize("UTC") if end.tzinfo is None else end
    if end > HOLDOUT_START and holdout_token is None:
        if start >= HOLDOUT_START:
            raise HoldoutLocked("hold-out window requested without a token from registry.open_holdout")
        end = HOLDOUT_START
    if holdout_token is not None:
        from research.fx_intraday.registry import check_token
        check_token(holdout_token)
    files = [CACHE / f"{pair}_{y}.parquet" for y in range(start.year, min(end.year, 2100) + 1)]
    parts = [pd.read_parquet(f) for f in files if f.exists()]
    if not parts:
        raise FileNotFoundError(f"no cached data for {pair}; run python3 -m research.fx_intraday.data")
    df = pd.concat(parts).set_index("time").sort_index()
    df = df[(df.index >= start) & (df.index < end)]
    return df


def quality(pair: str) -> pd.DataFrame:
    """Per-year checks on the full cache (reads the hold-out years too: checks only, no strategy code)."""
    rows = []
    p = pip(pair)
    for f in sorted(CACHE.glob(f"{pair}_*.parquet")):
        df = pd.read_parquet(f)
        if df.empty:
            continue
        y = int(f.stem.split("_")[1])
        spread = (df["ask_o"] - df["bid_o"]) / p
        bad_ohlc = ((df["bid_l"] > df[["bid_o", "bid_c"]].min(axis=1) + 1e-9) |
                    (df["bid_h"] < df[["bid_o", "bid_c"]].max(axis=1) - 1e-9)).sum()
        t = df["time"]
        ny = t.dt.tz_convert("America/New_York")
        wk = ny.dt.day_of_week
        weekend = ((wk == 5) | ((wk == 6) & (ny.dt.hour < 17)) | ((wk == 4) & (ny.dt.hour >= 17))).sum()
        gaps = t.diff().dt.total_seconds().div(60)
        rows.append({"pair": pair, "year": y, "bars": len(df), "first": t.iloc[0], "last": t.iloc[-1],
                     "crossed_quotes": int((spread < 0).sum()), "bad_ohlc": int(bad_ohlc),
                     "weekend_bars": int(weekend), "gaps_over_10min_weekday": int(((gaps > 10) & (gaps < 2000)).sum()),
                     "spread_median_pips": round(float(spread.median()), 2),
                     "spread_p95_pips": round(float(spread.quantile(0.95)), 2)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pairs = sys.argv[1:] or PAIRS
    download(pairs)
    pd.set_option("display.width", 220)
    for p in pairs:
        print(quality(p).to_string(index=False))

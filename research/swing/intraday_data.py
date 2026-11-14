"""Intraday bars for the band-bounce study (entry 80).

Yahoo's free limits: 60m bars for ~730 days, 30m/15m/5m bars for ~60 days.
Regular trading hours only. Prices are raw (unadjusted) — fine intraday.
Cached under research/cache/intra_<SYM>_<interval>.csv.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import _CHART, _get_json, _result  # noqa: E402

CACHE = ROOT / "research" / "cache"
SYMS = ["SPY", "QQQ", "IWM", "XLE", "XLF", "XLK", "SMH", "GLD", "GDX", "USO", "TLT", "TQQQ", "ERX"]
LIMIT_DAYS = {"60m": 725, "30m": 58, "15m": 58, "5m": 58}
CHUNK_DAYS = {"60m": 200, "30m": 58, "15m": 58, "5m": 58}


def fetch(symbol: str, interval: str) -> pd.DataFrame:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=LIMIT_DAYS[interval])
    parts, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=CHUNK_DAYS[interval]), end)
        url = (f"{_CHART.format(symbol=symbol)}?period1={int(cur.timestamp())}&period2={int(nxt.timestamp())}"
               f"&interval={interval}&includePrePost=false")
        res = _result(_get_json(url), symbol)
        got = res.get("meta", {}).get("dataGranularity")
        if got not in (interval, "1h" if interval == "60m" else interval):
            raise ValueError(f"{symbol}: wanted {interval}, got {got!r}")
        q = res["indicators"]["quote"][0]
        idx = pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert("America/New_York")
        parts.append(pd.DataFrame({k: q.get(k) for k in ("open", "high", "low", "close", "volume")}, index=idx))
        cur = nxt
        time.sleep(0.3)
    df = pd.concat(parts).dropna(subset=["close"])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    t = df.index.time
    df = df[(t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())]
    return df


def bars(symbol: str, interval: str, refresh: bool = False) -> pd.DataFrame:
    f = CACHE / f"intra_{symbol}_{interval}.csv"
    if f.exists() and not refresh:
        df = pd.read_csv(f, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
        return df
    df = fetch(symbol, interval)
    df.to_csv(f)
    return df


if __name__ == "__main__":
    for iv in ("60m", "15m", "5m"):
        for s in SYMS:
            try:
                df = bars(s, iv, refresh="--refresh" in sys.argv)
                per_day = df.groupby(df.index.date).size()
                print(f"{iv} {s:5s} {df.index[0].date()} -> {df.index[-1].date()}  bars={len(df):6d}  days={len(per_day)}  bars/day median={per_day.median():.0f}")
            except Exception as exc:
                print(f"{iv} {s}: FAILED {exc}")

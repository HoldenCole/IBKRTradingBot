"""Daily OHLCV for the swing-trading study (entry 75+).

Adjusted bars: Yahoo's adjclose/close ratio is applied to open/high/low so
that returns include dividends and intraday geometry (IBS, gaps) is kept.
Fetched in <=5y chunks with the granularity assertion (Yahoo coarsens long
ranges). Cached under research/cache/ohlc_<SYM>.csv (gitignored).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import _CHART, _get_json, _result  # noqa: E402

CACHE = ROOT / "research" / "cache"

BROAD = ["SPY", "QQQ", "IWM", "DIA"]
SECTORS = ["XLE", "XLF", "XLK", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB"]
SUBSECTORS = ["SMH", "XBI", "KRE", "XHB", "XRT", "IYR", "IYT"]
MACRO = ["GLD", "GDX", "SLV", "TLT", "IEF", "DBC", "USO"]
INTL = ["EFA", "EEM"]
LEVERED = ["TQQQ", "QLD", "ERX"]
INDICES = ["^GSPC", "^NDX", "^VIX", "^VXN", "^GVZ", "^OVX", "^IRX", "^SPGSCI"]
ETFS = BROAD + SECTORS + SUBSECTORS + MACRO + INTL
ALL = ETFS + LEVERED + INDICES + ["SHY"]


def _fetch_chunk(symbol: str, p1: int, p2: int) -> pd.DataFrame:
    url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval=1d"
    res = _result(_get_json(url), symbol)
    got = res.get("meta", {}).get("dataGranularity")
    if got != "1d":
        raise ValueError(f"{symbol}: Yahoo returned {got!r} bars, wanted '1d'")
    stamps = res.get("timestamp") or []
    if not stamps:
        return pd.DataFrame()
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    idx = pd.to_datetime(stamps, unit="s", utc=True).tz_convert(None).normalize()
    df = pd.DataFrame({k: q.get(k) for k in ("open", "high", "low", "close", "volume")}, index=idx)
    df["adjclose"] = adj if adj is not None else df["close"]
    return df.dropna(subset=["close"])


def fetch_ohlc(symbol: str, start: str = "1984-01-01") -> pd.DataFrame:
    parts = []
    cur, end = pd.Timestamp(start), pd.Timestamp.now('UTC').tz_localize(None) + pd.Timedelta(days=1)
    while cur < end:
        nxt = min(cur + pd.DateOffset(years=5), end)
        try:
            part = _fetch_chunk(symbol, int(cur.tz_localize("UTC").timestamp()),
                                int(nxt.tz_localize("UTC").timestamp()))
        except Exception as exc:  # pre-inception chunks 404/400 — skip, keep later ones
            if parts:
                raise
            part = pd.DataFrame()
            if "Data doesn't exist" not in str(exc) and "400" not in str(exc) and "404" not in str(exc) \
                    and "empty" not in str(exc):
                print(f"  {symbol} {cur.date()}: {exc}")
        if not part.empty:
            parts.append(part)
        cur = nxt
        time.sleep(0.15)
    if not parts:
        raise ValueError(f"{symbol}: no data")
    df = pd.concat(parts)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    f = df["adjclose"] / df["close"]
    out = pd.DataFrame({"open": df["open"] * f, "high": df["high"] * f, "low": df["low"] * f,
                        "close": df["adjclose"], "volume": df["volume"], "raw_close": df["close"]})
    # granularity guard: median gap between bars must be one trading day
    gaps = out.index.to_series().diff().dt.days.dropna()
    if len(gaps) > 50 and gaps.median() > 1.5:
        raise ValueError(f"{symbol}: coarse bars (median gap {gaps.median()}d)")
    return out


def ohlc(symbol: str, refresh: bool = False) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"ohlc_{symbol.replace('^', '')}.csv"
    if f.exists() and not refresh:
        return pd.read_csv(f, index_col=0, parse_dates=True)
    df = fetch_ohlc(symbol)
    df.to_csv(f)
    return df


def load(symbols=None, refresh: bool = False) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols or ALL:
        try:
            out[s] = ohlc(s, refresh)
        except Exception as exc:
            print(f"FAILED {s}: {exc}")
    return out


if __name__ == "__main__":
    data = load(refresh="--refresh" in sys.argv)
    for s, df in data.items():
        bad = (df["high"] < df["low"]).sum() + (df["open"] <= 0).sum()
        flat = ((df["high"] == df["low"]) & (df["volume"].fillna(0) > 0)).mean()
        print(f"{s:8s} {df.index[0].date()} -> {df.index[-1].date()}  n={len(df):5d}  bad={bad}  flat-bar share={flat:.1%}")

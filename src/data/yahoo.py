"""Yahoo Finance chart-API fetchers (no API key; goes through the proxy).

Reconstructed 2026-09-21 after the original file was lost to a `.gitignore`
rule (`data/`) that also matched `src/data/`. Two hard-won conventions are
baked in and must stay:

* Yahoo silently COARSENS `interval=1d&range=max` to weekly/monthly bars.
  Every fetch asserts `meta.dataGranularity` equals the interval requested
  and raises otherwise — a coarsened series must never reach a signal.
* Daily/monthly series are ADJUSTED closes (splits + dividends), tz-naive,
  normalized to midnight, sorted, de-duplicated, NaNs dropped.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CA_BUNDLE = "/root/.ccr/ca-bundle.crt"


def _ssl_context() -> ssl.SSLContext:
    """TLS context that trusts the agent proxy's CA when present."""
    if os.path.exists(_CA_BUNDLE):
        return ssl.create_default_context(cafile=_CA_BUNDLE)
    return ssl.create_default_context()


def _get_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.load(resp)


def _result(payload: dict, symbol: str) -> dict:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"{symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise ValueError(f"{symbol}: empty chart result")
    return results[0]


def _closes(result: dict, symbol: str, want_granularity: str, adjusted: bool = True) -> pd.Series:
    got = result.get("meta", {}).get("dataGranularity")
    if got != want_granularity:
        raise ValueError(f"{symbol}: Yahoo returned {got!r} bars, wanted {want_granularity!r} "
                         "(range/interval coarsening) — refusing")
    stamps = result.get("timestamp") or []
    ind = result.get("indicators", {})
    series = None
    if adjusted and ind.get("adjclose"):
        series = ind["adjclose"][0].get("adjclose")
    if series is None:
        series = ind["quote"][0].get("close")
    idx = pd.to_datetime(stamps, unit="s", utc=True).tz_convert(None).normalize()
    s = pd.Series(series, index=idx, dtype="float64", name=symbol).dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError(f"{symbol}: no closes returned")
    return s


def fetch_yahoo_daily(symbol: str, rng: str = "2y") -> pd.Series:
    """Adjusted daily closes for `rng` (Yahoo range string: 1mo, 6mo, 1y, 2y, 5y, 10y).

    Never pass 'max' — Yahoo coarsens it; the granularity assertion would
    reject the result anyway. For long histories use explicit windows.
    """
    url = f"{_CHART.format(symbol=symbol)}?range={rng}&interval=1d"
    return _closes(_result(_get_json(url), symbol), symbol, "1d")


def fetch_yahoo_monthly(symbol: str, years: int = 5) -> pd.Series:
    """Adjusted month-end closes with EXPLICIT epochs and interval=1mo.

    Yahoo stamps monthly bars at the first of the month; callers resample
    to month-end (`.resample("ME").last()`) as the ledger code does. The
    in-progress month appears as a partial bar — callers must drop it via
    completed_month_closes().
    """
    p2 = int(datetime.now(tz=timezone.utc).timestamp())
    p1 = int((datetime.now(tz=timezone.utc) - timedelta(days=366 * years + 40)).timestamp())
    url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval=1mo"
    return _closes(_result(_get_json(url), symbol), symbol, "1mo")


def fetch_yahoo_daily_window(symbol: str, start: str, end: str) -> pd.Series:
    """Adjusted daily closes between two ISO dates, fetched in ≤5-year
    chunks so no single request is coarsened (research helper)."""
    parts = []
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    cur = t0
    while cur < t1:
        nxt = min(cur + pd.DateOffset(years=5), t1)
        p1 = int(cur.tz_localize("UTC").timestamp()); p2 = int(nxt.tz_localize("UTC").timestamp())
        url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval=1d"
        parts.append(_closes(_result(_get_json(url), symbol), symbol, "1d"))
        cur = nxt
        time.sleep(0.2)
    s = pd.concat(parts)
    return s[~s.index.duplicated(keep="last")].sort_index()


# --- intraday helpers used by the CL1/USO research (kept for compatibility) ---

def _fetch_window(symbol: str, p1: int, p2: int) -> pd.DataFrame:
    """One-minute OHLCV between two epochs (Yahoo caps 1m at ~7 days/request)."""
    url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval=1m&includePrePost=true"
    res = _result(_get_json(url), symbol)
    got = res.get("meta", {}).get("dataGranularity")
    if got != "1m":
        raise ValueError(f"{symbol}: wanted 1m bars, got {got!r}")
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert("America/New_York")
    df = pd.DataFrame({k: q.get(k) for k in ("open", "high", "low", "close", "volume")}, index=idx)
    return df.dropna(subset=["close"])


def fetch_yahoo_1m(symbol: str, days: int = 28, pause_s: float = 1.0) -> pd.DataFrame:
    """Up to ~30 days of 1-minute bars, fetched in 7-day windows."""
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    frames = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=7), end)
        frames.append(_fetch_window(symbol, int(cur.timestamp()), int(nxt.timestamp())))
        cur = nxt
        time.sleep(pause_s)
    df = pd.concat(frames)
    return df[~df.index.duplicated(keep="last")].sort_index()


def rth_only(df: pd.DataFrame) -> pd.DataFrame:
    """Regular trading hours only (09:30-16:00 ET), index must be ET-aware."""
    t = df.index.time
    from datetime import time as dtime
    return df[(t >= dtime(9, 30)) & (t < dtime(16, 0))]

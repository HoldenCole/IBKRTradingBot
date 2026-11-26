"""Crypto data for CRYPTO.md studies. Bulk files from data.binance.vision (public archive, no key),
Kraken futures and Hyperliquid public APIs. Cached under research/cache/crypto/ (gitignored).

    python3 -m research.crypto.data
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import _ssl_context  # noqa: E402

CACHE = ROOT / "research" / "cache" / "crypto"
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK", "AVAX", "LTC"]
VISION = "https://data.binance.vision/data"


def _get(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes | None:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": "research"})
            with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def _zip_csv(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return pd.read_csv(f, header=None)


def binance_funding(coin: str, refresh: bool = False) -> pd.DataFrame:
    """USD-M perpetual funding, one row per funding event: time (UTC), rate."""
    f = CACHE / f"binance_funding_{coin}.parquet"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    sym = f"{coin}USDT"
    parts = []
    for m in pd.period_range("2019-09", pd.Timestamp.now().to_period("M") - 1, freq="M"):
        raw = _get(f"{VISION}/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
        if raw is None:
            continue
        d = _zip_csv(raw)
        if not str(d.iloc[0, 0]).isdigit():          # header row present in newer files
            d = d.iloc[1:]
        d = d.iloc[:, [0, 2]].astype(float)
        d.columns = ["ts", "rate"]
        parts.append(d)
    df = pd.concat(parts)
    df["time"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = df[["time", "rate"]].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


def binance_spot_daily(coin: str, refresh: bool = False) -> pd.DataFrame:
    f = CACHE / f"binance_spot1d_{coin}.parquet"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    sym = f"{coin}USDT"
    parts = []
    for m in pd.period_range("2017-08", pd.Timestamp.now().to_period("M") - 1, freq="M"):
        raw = _get(f"{VISION}/spot/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip")
        if raw is None:
            continue
        d = _zip_csv(raw)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, :6].astype(float)
        d.columns = ["ts", "open", "high", "low", "close", "volume"]
        parts.append(d)
    df = pd.concat(parts)
    ts = df["ts"].astype("int64")
    ts = ts.where(ts < 1e14, ts // 1000)               # files from 2025 use microseconds
    df["date"] = pd.to_datetime(ts, unit="ms").dt.normalize()
    df = df.drop(columns="ts").drop_duplicates("date").set_index("date").sort_index()
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


def kraken_funding(symbol: str = "PF_XBTUSD") -> pd.DataFrame:
    raw = _get(f"https://futures.kraken.com/derivatives/api/v4/historicalfundingrates?symbol={symbol}")
    d = pd.DataFrame(json.loads(raw)["rates"])
    d["time"] = pd.to_datetime(d["timestamp"], utc=True)
    return d[["time", "relativeFundingRate"]].rename(columns={"relativeFundingRate": "rate"})


def hyperliquid_funding(coin: str = "BTC", start: str = "2023-05-01") -> pd.DataFrame:
    f = CACHE / f"hl_funding_{coin}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    t = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    rows = []
    while True:
        body = json.dumps({"type": "fundingHistory", "coin": coin, "startTime": t}).encode()
        raw = _get("https://api.hyperliquid.xyz/info", body, {"Content-Type": "application/json", "User-Agent": "research"})
        d = json.loads(raw) if raw else []
        if not d:
            break
        rows += d
        nt = d[-1]["time"] + 1
        if nt <= t or len(d) < 400:
            break
        t = nt
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["rate"] = df["fundingRate"].astype(float)
    df = df[["time", "rate"]].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


if __name__ == "__main__":
    for c in COINS:
        fr = binance_funding(c)
        px = binance_spot_daily(c)
        print(f"{c}: funding {fr.time.iloc[0].date()} to {fr.time.iloc[-1].date()} ({len(fr)}), "
              f"spot {px.index[0].date()} to {px.index[-1].date()} ({len(px)})", flush=True)
    for c in ("BTC", "ETH"):
        h = hyperliquid_funding(c)
        print(f"Hyperliquid {c}: {h.time.iloc[0].date()} to {h.time.iloc[-1].date()} ({len(h)})")

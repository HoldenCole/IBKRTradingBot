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
import urllib.parse
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


# ---------------------------------------------------------------- C2: full Binance USDT spot universe
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
EXCLUDE_BASE = {"USDC", "BUSD", "TUSD", "USDP", "PAX", "DAI", "FDUSD", "USDS", "USDSB", "SUSD", "UST", "USTC", "EUR",
                "GBP", "AUD", "TRY", "BRL", "RUB", "UAH", "NGN", "ZAR", "IDRT", "BIDR", "BVND", "EURI", "AEUR", "XUSD",
                "USD1", "RLUSD", "PAXG", "WBTC", "WBETH", "WETH", "BETH", "BKRW", "VAI", "USDE", "BFUSD", "PYUSD"}
LEVERAGED = ("UP", "DOWN", "BULL", "BEAR")


def _list(prefix: str) -> tuple[list[str], list[str]]:
    """S3 listing: (sub-prefixes, keys), following pagination."""
    import re
    subs, keys, marker = [], [], ""
    while True:
        raw = None
        for _ in range(5):
            raw = _get(f"{S3}?prefix={urllib.parse.quote(prefix)}&delimiter=/&marker={urllib.parse.quote(marker)}")
            if raw is not None:
                break
            time.sleep(5)
        if raw is None:
            raise RuntimeError(f"listing failed: {prefix}")
        txt = raw.decode()
        subs += re.findall(r"<Prefix>([^<]+/)</Prefix>", txt)[1:] if "<CommonPrefixes>" in txt else []
        keys += re.findall(r"<Key>([^<]+)</Key>", txt)
        if "<IsTruncated>true</IsTruncated>" not in txt:
            break
        nm = re.search(r"<NextMarker>([^<]+)</NextMarker>", txt)
        marker = nm.group(1) if nm else (keys[-1] if keys else subs[-1])
    return subs, keys


def usdt_symbols() -> list[str]:
    f = CACHE / "binance_usdt_symbols.json"
    if f.exists():
        return json.loads(f.read_text())
    subs, _ = _list("data/spot/monthly/klines/")
    syms = sorted({s.rstrip("/").split("/")[-1] for s in subs})
    out = []
    for s in syms:
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        if base in EXCLUDE_BASE or any(base.endswith(x) and len(base) > len(x) for x in LEVERAGED):
            continue
        out.append(s)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out))
    return out


def spot_daily_symbol(sym: str) -> pd.DataFrame | None:
    """Daily candles for one Binance pair across all archived months, with quote volume."""
    f = CACHE / "spot1d" / f"{sym}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    _, keys = _list(f"data/spot/monthly/klines/{sym}/1d/")
    keys = [k for k in keys if k.endswith(".zip")]
    parts = []
    for k in keys:
        raw = _get(f"https://data.binance.vision/{urllib.parse.quote(k)}")
        if raw is None:
            continue
        d = _zip_csv(raw)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, [0, 1, 2, 3, 4, 7]].astype(float)
        d.columns = ["ts", "open", "high", "low", "close", "qvol"]
        parts.append(d)
    f.parent.mkdir(parents=True, exist_ok=True)
    if not parts:
        pd.DataFrame().to_parquet(f)
        return None
    df = pd.concat(parts)
    ts = df["ts"].astype("int64")
    ts = ts.where(ts < 1e14, ts // 1000)
    df["date"] = pd.to_datetime(ts, unit="ms").dt.normalize()
    df = df.drop(columns="ts").drop_duplicates("date").set_index("date").sort_index()
    df.to_parquet(f)
    return df


def coinbase_btc_daily() -> pd.Series:
    f = CACHE / "coinbase_btc_usd_1d.parquet"
    if f.exists():
        return pd.read_parquet(f)["close"]
    rows = []
    start = pd.Timestamp("2015-01-01")
    end = pd.Timestamp.now().normalize()
    while start < end:
        stop = min(start + pd.Timedelta(days=299), end)
        url = (f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400"
               f"&start={start:%Y-%m-%dT00:00:00Z}&end={stop:%Y-%m-%dT00:00:00Z}")
        raw = _get(url)
        rows += json.loads(raw) if raw else []
        start = stop + pd.Timedelta(days=1)
        time.sleep(0.4)
    df = pd.DataFrame(rows, columns=["t", "low", "high", "open", "close", "volume"])
    df["date"] = pd.to_datetime(df["t"], unit="s").dt.normalize()
    df = df.drop_duplicates("date").set_index("date").sort_index()
    df.to_parquet(f)
    return df["close"]


def download_universe(workers: int = 12) -> None:
    from concurrent.futures import ThreadPoolExecutor
    syms = usdt_symbols()
    print(f"{len(syms)} USDT pairs after exclusions", flush=True)
    done = 0
    with ThreadPoolExecutor(workers) as ex:
        for _ in ex.map(spot_daily_symbol, syms):
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(syms)}", flush=True)
    print("done", flush=True)


# ---------------------------------------------------------------- C3: hourly USD-M perpetual candles
def perp_hourly(coin: str) -> pd.DataFrame:
    """Binance USD-M perpetual 1h candles (open time UTC) from 2020: open, high, low, close."""
    f = CACHE / f"perp1h_{coin}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    sym = f"{coin}USDT"
    parts = []
    for m in pd.period_range("2020-01", pd.Timestamp.now().to_period("M") - 1, freq="M"):
        raw = _get(f"{VISION}/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{m}.zip")
        if raw is None:
            continue
        d = _zip_csv(raw)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, :5].astype(float)
        d.columns = ["ts", "open", "high", "low", "close"]
        parts.append(d)
    df = pd.concat(parts)
    ts = df["ts"].astype("int64")
    ts = ts.where(ts < 1e14, ts // 1000)
    df["time"] = pd.to_datetime(ts, unit="ms", utc=True)
    df = df.drop(columns="ts").drop_duplicates("time").set_index("time").sort_index()
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df

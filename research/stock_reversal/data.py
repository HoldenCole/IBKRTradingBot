"""Data for the single-stock reversal study (entry 92).

- Point-in-time S&P 500 membership: data/sp500_ticker_start_end.csv, from
  github.com/fja05680/sp500 (MIT licence, data/LICENSE_sp500_membership).
- Daily OHLCV from Yahoo, dividend-adjusted, via research.swing.data.fetch_ohlc.
  Yahoo keeps only listed symbols, so delisted members are missing.
- SEC EDGAR filings (8-K items and acceptance times) from data.sec.gov.
  Item 2.02 ("Results of Operations") marks an earnings release.

Caches go to research/cache/stocks/ (gitignored).

    python3 -m research.stock_reversal.data      # download everything
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import fetch_ohlc  # noqa: E402
from src.data.yahoo import _ssl_context  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = ROOT / "research" / "cache" / "stocks"
SEC_UA = {"User-Agent": "IBKRTradingBot research admin@example.com", "Accept-Encoding": "identity"}
START = "2005-01-01"


def membership() -> pd.DataFrame:
    d = pd.read_csv(HERE / "data" / "sp500_ticker_start_end.csv", parse_dates=["start_date", "end_date"])
    d["end_date"] = d["end_date"].fillna(pd.Timestamp("2099-12-31"))
    return d[d["end_date"] >= START].reset_index(drop=True)


def yahoo_symbol(t: str) -> str:
    return t.replace(".", "-")


def prices(ticker: str, refresh: bool = False) -> pd.DataFrame | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"px_{ticker}.parquet"
    miss = CACHE / f"px_{ticker}.missing"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    if miss.exists() and not refresh:
        return None
    try:
        df = fetch_ohlc(yahoo_symbol(ticker), start="2003-06-01")
    except Exception:
        miss.touch()
        return None
    df.to_parquet(f)
    return df


def _sec_json(url: str) -> dict:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=SEC_UA)
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def cik_map() -> dict[str, int]:
    f = CACHE / "sec_company_tickers.json"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(_sec_json("https://www.sec.gov/files/company_tickers.json")))
    j = json.loads(f.read_text())
    return {v["ticker"].upper().replace("-", "."): int(v["cik_str"]) for v in j.values()}


def _rows(block: dict) -> pd.DataFrame:
    keep = ["form", "filingDate", "acceptanceDateTime", "items"]
    return pd.DataFrame({k: block.get(k, []) for k in keep})


def filings(ticker: str, cik: int, refresh: bool = False) -> pd.DataFrame:
    """All 8-K filings for a CIK since 2004: acceptance time (New York) and items."""
    f = CACHE / f"sec_{ticker}.parquet"
    if f.exists() and not refresh:
        return pd.read_parquet(f)
    j = _sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    parts = [_rows(j["filings"]["recent"])]
    for extra in j["filings"].get("files", []):
        if extra.get("filingTo", "9999") < "2004-01-01":
            continue
        time.sleep(0.12)
        parts.append(_rows(_sec_json(f"https://data.sec.gov/submissions/{extra['name']}")))
    df = pd.concat(parts, ignore_index=True)
    df = df[df["form"].isin(["8-K", "8-K/A"])].copy()
    acc = pd.to_datetime(df["acceptanceDateTime"], utc=True, errors="coerce")
    df["accepted"] = acc.dt.tz_convert("America/New_York").dt.tz_localize(None)
    df["earnings"] = df["items"].fillna("").str.contains("2.02") & (df["form"] == "8-K")
    df = df[df["accepted"] >= "2004-01-01"][["form", "accepted", "items", "earnings"]].reset_index(drop=True)
    df.to_parquet(f)
    time.sleep(0.12)
    return df


def download() -> None:
    m = membership()
    ciks = cik_map()
    tickers = sorted(m["ticker"].unique())
    got = sec = 0
    for i, t in enumerate(tickers):
        if prices(t) is not None:
            got += 1
            if t in ciks:
                try:
                    filings(t, ciks[t])
                    sec += 1
                except Exception as exc:
                    print(f"  SEC {t}: {exc}")
        if i % 50 == 0:
            print(f"{i}/{len(tickers)} prices {got} filings {sec}", flush=True)
    print(f"done: {len(tickers)} tickers, prices {got}, filings {sec}")


if __name__ == "__main__":
    download()

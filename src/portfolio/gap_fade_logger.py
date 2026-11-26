"""Paper log for the lone no-news gap-up fade (TESTS.md entry 92, a post-hoc lead, logged forward).

Each session, after the close: for current S&P 500 members, find stocks whose open gapped up at least 5% AND at
least 3 standard deviations versus SPY (excess gap; sigma = 60-session standard deviation of daily excess
returns), with a prior close of at least $5 and 20-day median dollar volume of at least $20 million.
"No news": no SEC 8-K accepted from 16:00 five sessions before through 09:30 today, and an earnings 8-K
(Item 2.02) seen within the prior 130 sessions (so the filing feed is known to cover the stock).
"Lone": at most two big gaps (up or down, any news) among members that day.
The paper trade shorts at the open and covers at the close; 10 bp a side. Nothing here trades.

    python3 -m src.portfolio.gap_fade_logger

Writes paper/gap_fade_daily.csv (one row per session) and paper/gap_fade_trades.csv (one row per paper trade).
Idempotent by session date.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.yahoo import _CHART, _get_json, _result, _ssl_context
from src.portfolio.trend_cycle import fetch_sp500_members

ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / "paper" / "gap_fade_daily.csv"
TRADES = ROOT / "paper" / "gap_fade_trades.csv"
SEC_UA = {"User-Agent": "IBKRTradingBot research admin@example.com"}
COST = 0.0010


def ohlc(sym: str) -> pd.DataFrame | None:
    try:
        res = _result(_get_json(f"{_CHART.format(symbol=sym)}?range=6mo&interval=1d"), sym)
    except Exception:  # noqa: BLE001
        return None
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    df = pd.DataFrame({k: q.get(k) for k in ("open", "high", "low", "close", "volume")}, index=idx).dropna(subset=["open", "close"])
    return df[~df.index.duplicated(keep="last")]


def _sec(url: str) -> dict:
    req = urllib.request.Request(url, headers=SEC_UA)
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
        return json.loads(r.read())


def cik_map() -> dict[str, int]:
    j = _sec("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"].upper().replace(".", "-"): int(v["cik_str"]) for v in j.values()}


def filings(cik: int) -> pd.DataFrame:
    j = _sec(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")["filings"]["recent"]
    d = pd.DataFrame({k: j.get(k, []) for k in ("form", "acceptanceDateTime", "items")})
    d = d[d.form.isin(["8-K", "8-K/A"])].copy()
    d["accepted"] = pd.to_datetime(d.acceptanceDateTime, utc=True, errors="coerce").dt.tz_convert("America/New_York").dt.tz_localize(None)
    d["earnings"] = d["items"].fillna("").str.contains("2.02") & (d.form == "8-K")
    return d


def logged() -> set[str]:
    if not DAILY.exists():
        return set()
    with DAILY.open() as fh:
        return {r["date"] for r in csv.DictReader(fh)}


def append(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)


def run() -> dict:
    spy = ohlc("SPY")
    day = spy.index[-1]
    if str(day.date()) in logged():
        return {"date": str(day.date()), "skipped": "already logged"}
    sessions = spy.index
    spy_gap = spy.open.iloc[-1] / spy.close.iloc[-2] - 1
    spy_ret = spy.close.pct_change()
    big, cands = [], []
    for sym in fetch_sp500_members():
        d = ohlc(sym)
        time.sleep(0.1)
        if d is None or len(d) < 70 or d.index[-1] != day:
            continue
        d = d.reindex(sessions)
        ex = d.close.pct_change() - spy_ret
        sigma = ex.iloc[-61:-1].std()
        pc = d.close.iloc[-2]
        dv = (d.close * d.volume).iloc[-21:-1].median()
        if not (np.isfinite(sigma) and pc >= 5 and dv >= 20e6):
            continue
        g = (d.open.iloc[-1] / pc - 1) - spy_gap
        if abs(g) >= 0.05 and abs(g) >= 3 * sigma:
            big.append(sym)
            if g > 0:
                cands.append((sym, g, sigma, d.open.iloc[-1], d.close.iloc[-1], spy.open.iloc[-1], spy.close.iloc[-1]))
    trades = []
    if cands and len(big) <= 2:
        ciks = cik_map()
        open_t = day + pd.Timedelta(hours=9, minutes=30)
        start = sessions[-6] + pd.Timedelta(hours=16)        # 16:00 five sessions before today
        cover_from = sessions[-131] + pd.Timedelta(hours=16) if len(sessions) > 131 else sessions[0]
        for sym, g, sigma, o, c, so, sc in cands:
            if sym not in ciks:
                continue
            f = filings(ciks[sym])
            time.sleep(0.15)
            covered = (f.earnings & (f.accepted > cover_from) & (f.accepted <= open_t)).any()
            news = ((f.accepted > start) & (f.accepted <= open_t)).any()
            if covered and not news:
                raw = -(c / o - 1)
                excess = raw + (sc / so - 1)
                trades.append({"date": str(day.date()), "ticker": sym, "gap_excess": round(g, 4), "sigma": round(sigma, 4),
                               "open": round(o, 2), "close": round(c, 2), "fade_raw": round(raw, 4),
                               "fade_excess": round(excess, 4), "net_raw": round(raw - 2 * COST, 4)})
    summary = {"date": str(day.date()), "big_gaps": len(big), "gap_up_candidates": len(cands),
               "lone_day": len(big) <= 2, "paper_trades": len(trades),
               "logged_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M")}
    append(TRADES, trades)
    append(DAILY, [summary])
    return {**summary, "trades": trades}


if __name__ == "__main__":
    out = run()
    print(out)

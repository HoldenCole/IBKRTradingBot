"""Paper log for the bitcoin 10-month rule (TESTS.md entries 104-105; a post-hoc lead, logged forward).

Rule: at each month-end close (UTC, Coinbase BTC-USD), hold bitcoin for the next month if the close is above
the average of the last 10 month-end closes; otherwise hold cash. Nothing here trades.

One row per completed month in paper/btc_rule.csv (append-only, idempotent):
month, close, avg10, signal for the NEXT month, the position held DURING this month, this month's bitcoin
return, the rule's return (bitcoin return if held, else 0, less 0.25% per switch), and the rule's equity index.

    python3 -m src.portfolio.btc_rule_logger          # log any completed months not yet logged
    python3 -m src.portfolio.btc_rule_logger --status # today's provisional reading, nothing written
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

from src.data.yahoo import _ssl_context

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "paper" / "btc_rule.csv"
FIELDS = ["month", "close", "avg10", "signal_next", "held", "btc_return", "rule_return", "rule_equity", "logged_utc"]
SWITCH_COST = 0.0025


def coinbase_daily(start: str = "2014-06-01") -> pd.Series:
    rows, s = [], pd.Timestamp(start)
    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    while s < end:
        e = min(s + pd.Timedelta(days=299), end)
        url = (f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400"
               f"&start={s:%Y-%m-%dT00:00:00Z}&end={e:%Y-%m-%dT00:00:00Z}")
        req = urllib.request.Request(url, headers={"User-Agent": "research"})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
            rows += json.loads(r.read())
        s = e + pd.Timedelta(days=1)
        time.sleep(0.35)
    df = pd.DataFrame(rows, columns=["t", "low", "high", "open", "close", "volume"])
    df["date"] = pd.to_datetime(df["t"], unit="s").dt.normalize()
    return df.drop_duplicates("date").set_index("date").sort_index()["close"]


def month_table(daily: pd.Series) -> pd.DataFrame:
    today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    m = daily.groupby(daily.index.to_period("M")).last()
    m = m[m.index < today.to_period("M")]                      # completed months only
    t = pd.DataFrame({"close": m, "avg10": m.rolling(10).mean()})
    t["signal_next"] = (t.close > t.avg10).map({True: "ON", False: "OFF"})
    t["held"] = t["signal_next"].shift(1)
    t["btc_return"] = t.close.pct_change()
    switch = (t["held"] != t["held"].shift(1)) & t["held"].shift(1).notna()
    t["rule_return"] = (t["btc_return"].where(t["held"] == "ON", 0.0) - switch * SWITCH_COST).fillna(0.0)
    return t.dropna(subset=["avg10"])


def log() -> list[dict]:
    t = month_table(coinbase_daily())
    done = set()
    eq = 1.0
    if PATH.exists():
        with PATH.open() as fh:
            prev = list(csv.DictReader(fh))
        done = {r["month"] for r in prev}
        if prev:
            eq = float(prev[-1]["rule_equity"])
    new = []
    for per, r in t.iterrows():
        if str(per) in done:
            continue
        if not done and not new:
            eq = 1.0                                           # first logged month starts the forward record
            rr = 0.0
        else:
            rr = float(r.rule_return)
        eq *= 1 + rr
        new.append({"month": str(per), "close": round(float(r.close), 2), "avg10": round(float(r.avg10), 2),
                    "signal_next": r.signal_next, "held": r.held if isinstance(r.held, str) else "",
                    "btc_return": round(float(r.btc_return), 5), "rule_return": round(rr, 5),
                    "rule_equity": round(eq, 5), "logged_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M")})
    if new and not done:
        new = new[-1:]                                         # start the record at the latest completed month
        new[0]["rule_return"] = 0.0; new[0]["rule_equity"] = 1.0
    if new:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        exists = PATH.exists()
        with PATH.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if not exists:
                w.writeheader()
            w.writerows(new)
    return new


def status() -> str:
    d = coinbase_daily("2025-01-01")
    m = d.groupby(d.index.to_period("M")).last()
    avg = m.iloc[-10:].mean()                                  # includes the current month at today's price
    sig = "ON" if d.iloc[-1] > avg else "OFF"
    return (f"bitcoin ${d.iloc[-1]:,.0f} ({d.index[-1].date()}); 10-month average incl. this month ${avg:,.0f}; "
            f"if the month closed now: {sig}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(status())
    else:
        rows = log()
        print(f"logged {len(rows)} month(s)" + (": " + ", ".join(f"{r['month']} next={r['signal_next']}" for r in rows) if rows else ""))
        print(status())

"""Entry 108 — Kalshi daily high temperature: forecast model against market prices. See PREREGISTRATION_WEATHER.md.

    python3 -m research.kalshi.weather fetch       # markets, last trades before each decision, forecasts (resumable)
    python3 -m research.kalshi.weather             # development results (hold-out stays sealed)
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.kalshi.study import get, paged  # noqa: E402
from src.data.yahoo import _ssl_context  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi" / "weather"
CITIES = {  # series: (name, lat, lon, local tz, local standard-time zone)
    "KXHIGHNY": ("New York", 40.7789, -73.9692, "America/New_York", "Etc/GMT+5"),
    "KXHIGHLAX": ("Los Angeles", 33.9382, -118.3866, "America/Los_Angeles", "Etc/GMT+8"),
    "KXHIGHMIA": ("Miami", 25.7881, -80.3169, "America/New_York", "Etc/GMT+5"),
    "KXHIGHCHI": ("Chicago", 41.7860, -87.7524, "America/Chicago", "Etc/GMT+6"),
    "KXHIGHAUS": ("Austin", 30.1945, -97.6699, "America/Chicago", "Etc/GMT+6"),
    "KXHIGHDEN": ("Denver", 39.8466, -104.6562, "America/Denver", "Etc/GMT+7"),
}
HOLDOUT = pd.Timestamp("2025-07-01")
DEV_START = pd.Timestamp("2024-01-01")
HOLDOUT_OPEN = False                                            # set True only after the development gates pass
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def target_date(event: str) -> pd.Timestamp | None:
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event)
    if not m or m.group(2) not in MONTHS:
        return None
    return pd.Timestamp(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))


def markets(series: str) -> pd.DataFrame:
    f = CACHE / f"markets_{series}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    ms = paged("/historical/markets", "markets", {"series_ticker": series, "limit": 1000}, cap=500_000)
    ms += paged("/markets", "markets", {"series_ticker": series, "status": "settled", "limit": 1000}, cap=500_000)
    rows, seen = [], set()
    for m in ms:
        if m["ticker"] in seen or m.get("result") not in ("yes", "no"):
            continue
        seen.add(m["ticker"])
        d = target_date(m["event_ticker"])
        ev = m.get("expiration_value")
        if d is None:
            continue
        nums = re.findall(r"-?\d+(?:\.\d+)?", str(ev or ""))
        ev = float(nums[0]) if len(nums) == 1 else np.nan      # only the winning market carries it on older days
        rows.append({"ticker": m["ticker"], "event": m["event_ticker"], "date": d, "strike_type": m.get("strike_type"),
                     "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "result": m["result"],
                     "actual": float(ev), "volume": float(m.get("volume_fp") or m.get("volume") or 0)})
    df = pd.DataFrame(rows)
    # one actual high per day: an exact value from any market that day, else the middle of the winning band
    exact = df.groupby("event")["actual"].transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    win = df[(df.result == "yes") & (df.strike_type == "between")].set_index("event")
    mid = df["event"].map(((win["floor"] + win["cap"]) / 2).groupby(level=0).first())
    df["actual"] = exact.fillna(mid)
    df = df.dropna(subset=["actual"])
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


def decision_times(series: str, d: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    tz = CITIES[series][3]
    t1 = pd.Timestamp(d - pd.Timedelta(days=1)).replace(hour=14).tz_localize("America/New_York").tz_convert("UTC")
    t0 = pd.Timestamp(d).replace(hour=8).tz_localize(tz).tz_convert("UTC")
    return t1, t0


ARCHIVE_CUTOFF = pd.Timestamp("2026-09-27")


def last_trade(ticker: str, t: pd.Timestamp, archived: bool = False):
    path = "/historical/trades" if archived else "/markets/trades"
    d = get(path, {"ticker": ticker, "max_ts": int(t.timestamp()), "limit": 1})
    tr = (d.get("trades") or [])
    if not tr:
        return None, None
    x = tr[0]
    p = x.get("yes_price_dollars")
    p = float(p) if p is not None else (x["yes_price"] / 100 if x.get("yes_price") is not None else None)
    return p, pd.Timestamp(x["created_time"])


def fetch_trades(series: str):
    f = CACHE / f"trades_{series}.parquet"
    done = pd.read_parquet(f) if f.exists() else pd.DataFrame()
    have = set(done["ticker"]) if len(done) else set()
    m = markets(series)
    rows = done.to_dict("records") if len(done) else []
    # amendment 2: development window 2024-01-01 on, and only bands with a model probability of 2-98%
    p = model_probs(series, m)
    m = m.assign(model_p=p)
    end = HOLDOUT if not HOLDOUT_OPEN else pd.Timestamp("2100-01-01")
    todo = m[~m.ticker.isin(have) & (m.date >= DEV_START) & (m.date < end) & m.model_p.between(0.02, 0.98)]
    print(f"{series}: {len(m)} markets, {len(todo)} to fetch", flush=True)
    for i, r in enumerate(todo.itertuples()):
        t1, t0 = decision_times(series, r.date)
        p1, s1 = None, None                                     # amendment 1: the day-before decision is dropped
        p0, s0 = last_trade(r.ticker, t0, archived=r.date < ARCHIVE_CUTOFF - pd.Timedelta(days=1))
        rows.append({"ticker": r.ticker, "p_t1": p1, "ts_t1": s1, "p_t0": p0, "ts_t0": s0})
        if i % 500 == 499:
            pd.DataFrame(rows).to_parquet(f)
            print(f"  {series} {i + 1}/{len(todo)}", flush=True)
    pd.DataFrame(rows).to_parquet(f)


def forecasts(series: str) -> pd.DataFrame:
    f = CACHE / f"forecast_{series}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    name, lat, lon, _, lst = CITIES[series]
    parts = []
    for y in range(2021, 2027):
        s, e = f"{y}-01-01", min(pd.Timestamp(f"{y}-12-31"), pd.Timestamp.now().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "start_date": s, "end_date": e,
                                    "hourly": "temperature_2m_previous_day1,temperature_2m_previous_day2",
                                    "temperature_unit": "fahrenheit", "timezone": lst})
        for attempt in range(4):
            try:
                req = urllib.request.Request(f"https://previous-runs-api.open-meteo.com/v1/forecast?{q}", headers={"User-Agent": "research"})
                with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r:
                    j = json.loads(r.read())
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        else:
            continue
        h = j.get("hourly")
        if not h:
            continue
        d = pd.DataFrame(h)
        d["date"] = pd.to_datetime(d["time"]).dt.normalize()
        g = d.groupby("date").agg(f2=("temperature_2m_previous_day2", lambda x: x.max() if x.notna().sum() >= 20 else np.nan),
                                  f1=("temperature_2m_previous_day1", lambda x: x.max() if x.notna().sum() >= 20 else np.nan))
        parts.append(g)
        time.sleep(1)
    df = pd.concat(parts)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df


def fetch():
    for s in CITIES:
        fc = forecasts(s)
        print(f"{s} forecasts {fc.index.min().date()} to {fc.index.max().date()}, f1 days {fc.f1.notna().sum()}", flush=True)
    for s in CITIES:
        fetch_trades(s)
    print("done", flush=True)


# ------------------------------------------------------------------ analysis
def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def band_prob(row, m: float, s: float) -> float:
    def cdf(x):
        return norm.cdf((x - m) / s)
    if row.strike_type == "greater":
        return 1 - cdf(row.floor + 0.5)
    if row.strike_type == "less":
        return cdf(row.cap - 0.5)
    return cdf(row.cap + 0.5) - cdf(row.floor - 0.5)


def residual_stats(res: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Mean and spread of the previous 45 available residuals (days with a forecast), known before each day."""
    r = res.dropna()
    mu = r.rolling(45, min_periods=45).mean().shift(1)
    sd = r.rolling(45, min_periods=45).std().shift(1).clip(lower=1.5)
    idx = res.index
    return mu.reindex(idx, method="ffill").where(res.index > r.index[0]), sd.reindex(idx, method="ffill")


def model_probs(series: str, m: pd.DataFrame) -> pd.Series:
    """Same-day (T0) model probability for every market, from forecasts and past outcomes only."""
    fc = forecasts(series)
    days = m.groupby("date")["actual"].first().sort_index().to_frame().join(fc, how="left")
    mu, sd = residual_stats(days["actual"] - days["f1"])
    md = days[["f1"]].assign(mu=mu, sd=sd)
    x = m.join(md, on="date")
    return pd.Series([band_prob(r, r.f1 + r.mu, r.sd) if pd.notna(r.mu) and pd.notna(r.f1) else np.nan
                      for r in x.itertuples()], index=m.index)


def build(series: str, holdout: bool = False) -> pd.DataFrame:
    m = markets(series).merge(pd.read_parquet(CACHE / f"trades_{series}.parquet"), on="ticker", how="inner")
    fc = forecasts(series)
    days = m.groupby("date")["actual"].first().sort_index().to_frame()
    days = days.join(fc, how="left")
    out = []
    for col, lead, pcol, tcol in (("f1", "T0 same day 08:00", "p_t0", "ts_t0"),):
        mu, sd = residual_stats(days["actual"] - days[col])
        md = days[[col]].assign(mu=mu, sd=sd).dropna()
        x = m.merge(md, left_on="date", right_index=True)
        x["lead"] = lead
        x["model_p"] = [band_prob(r, r[col] + r.mu, r.sd) for _, r in x.iterrows()]
        x = x[x.model_p.between(0.02, 0.98)]                     # amendment 2
        x["price"] = x[pcol]
        dec = x["date"].map(lambda d: decision_times(series, d)[0 if pcol == "p_t1" else 1])
        x["fresh"] = (dec - pd.to_datetime(x[tcol], utc=True)) <= pd.Timedelta(hours=3)
        out.append(x[["ticker", "date", "strike_type", "floor", "cap", "result", "actual", "lead", "model_p", "price", "fresh"]])
    df = pd.concat(out)
    df["city"] = CITIES[series][0]
    df = df[df.date >= DEV_START]
    if not holdout:
        df = df[df.date < HOLDOUT]
    return df


def trades(df: pd.DataFrame, slip: float = 0.01) -> pd.DataFrame:
    x = df[df.fresh & df.price.notna() & (df.price > 0) & (df.price < 1)].copy()
    yes_fill = (x.price + slip).clip(upper=0.99)
    no_fill = (1 - x.price + slip).clip(upper=0.99)
    yes_fee = yes_fill.map(fee); no_fee = no_fill.map(fee)
    buy_yes = x.model_p - yes_fill - yes_fee >= 0.05
    buy_no = (1 - x.model_p) - no_fill - no_fee >= 0.05
    win = x.result == "yes"
    rows = []
    for side, sel, fill, fe, w in (("YES", buy_yes, yes_fill, yes_fee, win), ("NO", buy_no, no_fill, no_fee, ~win)):
        t = x[sel].copy()
        t["side"] = side
        t["cost"] = fill[sel] + fe[sel]
        t["ret"] = (w[sel].astype(float) - t["cost"]) / t["cost"]
        rows.append(t)
    return pd.concat(rows)


def clustered_t(r: pd.Series, g: pd.Series) -> float:
    m = r.mean(); s = (r - m).groupby(g).sum(); G = len(s)
    se = np.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / len(r)
    return m / se if se > 0 else np.nan


def analyse():
    allx = pd.concat([build(s) for s in CITIES])
    print(f"development markets with a model probability: {len(allx):,}; with a trade in the prior 3 hours: "
          f"{int((allx.fresh & allx.price.notna()).sum()):,}")
    for lead, g in allx.groupby("lead"):
        g = g.copy()
        g["mb"] = (g.model_p * 10).clip(0, 9.999).astype(int)
        cal = g.groupby("mb").agg(n=("model_p", "size"), model=("model_p", "mean"), market=("price", "mean"),
                                  outcome=("result", lambda s: (s == "yes").mean()))
        print(f"\nCalibration, {lead} (model probability decile): n, model mean, market price mean, outcome rate")
        print(cal.round(3).to_string())
        t = trades(g)
        t2 = trades(g, slip=0.02)
        if t.empty:
            print("   no trades"); continue
        t["cityday"] = t.city + t.date.astype(str)
        mid = t.date.min() + (t.date.max() - t.date.min()) / 2
        by_city = t.groupby("city").ret.agg(["size", "mean"])
        pos_cities = int(((by_city["size"] >= 20) & (by_city["mean"] > 0)).sum())
        gates = {"1 trades >= 300": len(t) >= 300,
                 "2 mean > 0, t >= 3": t.ret.mean() > 0 and clustered_t(t.ret, t.cityday) >= 3,
                 "3 both halves > 0": t[t.date < mid].ret.mean() > 0 and t[t.date >= mid].ret.mean() > 0,
                 "4 positive in >= 4 cities": pos_cities >= 4,
                 "5 positive at 2c slippage": t2.ret.mean() > 0}
        print(f"\n{lead}: {len(t)} trades ({(t.side == 'YES').sum()} YES, {(t.side == 'NO').sum()} NO), mean return per $ "
              f"{t.ret.mean():+.1%}, win {(t.ret > 0).mean():.0%}, clustered t {clustered_t(t.ret, t.cityday):.2f}; "
              f"halves {t[t.date < mid].ret.mean():+.1%} / {t[t.date >= mid].ret.mean():+.1%}; at 2c slippage {t2.ret.mean():+.1%}")
        print(by_city.round(3).to_string())
        print("   by side:", t.groupby("side").ret.agg(["size", "mean"]).round(3).to_dict())
        print("   gates:", gates, "->", "PASS" if all(gates.values()) else "FAIL")
        t.to_csv(ROOT / "research" / "kalshi" / f"weather_dev_trades_{lead[:2]}.csv", index=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
    else:
        analyse()

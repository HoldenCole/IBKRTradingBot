"""Entry 106 — Kalshi favourite-longshot bias after fees. See PREREGISTRATION.md.

    python3 -m research.kalshi.study fetch    # build the sample (slow: rate-limited public API)
    python3 -m research.kalshi.study          # analyse
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import _ssl_context  # noqa: E402

API = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = ROOT / "research" / "cache" / "kalshi"
SEED = 20261126
START, END = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-11-25", tz="UTC")
_last = [0.0]


def get(path: str, params: dict | None = None) -> dict:
    url = f"{API}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(8):
        wait = 0.12 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if e.code == 404:
                return {}
            time.sleep(2)
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def paged(path: str, key: str, params: dict, cap: int = 10_000) -> list[dict]:
    out, cursor = [], None
    while len(out) < cap:
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        d = get(path, p)
        out += d.get(key, [])
        cursor = d.get("cursor")
        if not cursor or not d.get(key):
            break
    return out


def sample_series() -> pd.DataFrame:
    f = CACHE / "series.json"
    if f.exists():
        s = json.loads(f.read_text())
    else:
        s = paged("/series", "series", {"limit": 1000}, cap=100_000)
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(s))
    df = pd.DataFrame([{"series": x["ticker"], "category": x.get("category") or "?"} for x in s])
    df = df[~df.series.str.startswith("KXMVE")]
    keep = df.groupby("category").filter(lambda g: len(g) >= 30)
    rng = np.random.default_rng(SEED)
    parts = []
    for cat, g in keep.groupby("category"):
        parts.append(g.iloc[rng.permutation(len(g))[:30]])
    return pd.concat(parts).reset_index(drop=True)


def markets_for(series: str) -> list[dict]:
    ms = paged("/markets", "markets", {"series_ticker": series, "status": "settled", "limit": 200}, cap=400)
    ms += paged("/historical/markets", "markets", {"series_ticker": series, "limit": 200}, cap=400)
    seen, out = set(), []
    for m in ms:
        t = m.get("ticker")
        if t in seen or m.get("result") not in ("yes", "no") or m.get("market_type", "binary") != "binary":
            continue
        seen.add(t)
        ct, ot = pd.Timestamp(m["close_time"]), pd.Timestamp(m["open_time"])
        vol = float(m.get("volume_fp") or m.get("volume") or 0)
        if not (START <= ct <= END) or (ct - ot) < pd.Timedelta(hours=48) or vol < 100:
            continue
        out.append({"ticker": t, "event": m.get("event_ticker"), "close": ct, "open": ot, "result": m["result"], "volume": vol})
    return out


def last_trade_before(ticker: str, ts: pd.Timestamp) -> float | None:
    d = get("/markets/trades", {"ticker": ticker, "max_ts": int(ts.timestamp()), "limit": 1})
    tr = d.get("trades") or []
    if not tr:
        return None
    t = tr[0]
    p = t.get("yes_price_dollars")
    if p is None and t.get("yes_price") is not None:
        p = t["yes_price"] / 100
    return float(p) if p is not None else None


def fetch():
    ser = sample_series()
    print(f"{len(ser)} series sampled across {ser.category.nunique()} categories", flush=True)
    out_f = CACHE / "sample.parquet"
    rows = pd.read_parquet(out_f).to_dict("records") if out_f.exists() else []
    done = {r["series"] for r in rows}
    rng = np.random.default_rng(SEED)
    for i, r in ser.iterrows():
        if r.series in done:
            continue
        ms = markets_for(r.series)
        if len(ms) > 15:
            ms = [ms[j] for j in rng.permutation(len(ms))[:15]]
        for m in ms:
            p24 = last_trade_before(m["ticker"], m["close"] - pd.Timedelta(hours=24))
            if p24 is None:
                continue
            p1 = None                                   # dropped by amendment 1 (rate limits), before any result
            rows.append({**m, "series": r.series, "category": r.category, "p24": p24, "p1": p1})
        done.add(r.series)
        if i % 10 == 0:
            pd.DataFrame(rows).to_parquet(out_f)
            print(f"  {i + 1}/{len(ser)} series, {len(rows)} markets", flush=True)
    pd.DataFrame(rows).to_parquet(out_f)
    print(f"done: {len(rows)} markets")


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def returns(df: pd.DataFrame, col: str, lo: float, hi: float, side: str, with_fee: bool = True) -> pd.DataFrame:
    """Buy the favourite (side='fav') or the long shot (side='long') when its price is in [lo, hi)."""
    y = df[col]
    fav_yes = y >= 0.5
    price = np.where(side == "fav", np.where(fav_yes, y, 1 - y), np.where(fav_yes, 1 - y, y))
    win = np.where(side == "fav", np.where(fav_yes, df.result == "yes", df.result == "no"),
                   np.where(fav_yes, df.result == "no", df.result == "yes"))
    sel = (price >= lo) & (price < hi) & (price > 0) & (price < 1)
    d = df[sel].copy()
    p = price[sel]
    f = np.array([fee(x) for x in p]) if with_fee else 0.0
    d["price"] = p
    d["ret"] = (win[sel].astype(float) - p - f) / (p + f)
    return d


def clustered_t(x: pd.Series, g: pd.Series) -> float:
    m = x.mean(); s = (x - m).groupby(g).sum()
    G = len(s)
    se = np.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / len(x)
    return m / se if se > 0 else np.nan


def analyse():
    df = pd.read_parquet(CACHE / "sample.parquet")
    df["year"] = pd.to_datetime(df["close"], utc=True).dt.year
    print(f"{len(df)} markets, {df.event.nunique()} events, {df.series.nunique()} series; by category:")
    print(df.category.value_counts().to_string())
    df["bucket"] = (df.p24 * 20).clip(0, 19.999).astype(int) * 5
    cal = df.groupby("bucket").agg(n=("p24", "size"), price=("p24", "mean"), yes_rate=("result", lambda s: (s == "yes").mean()))
    print("\nCalibration at 24 hours before close (YES price bucket, cents):")
    print(cal.round(3).to_string())
    top5 = df.category.value_counts().index[:5]
    rows = []
    for name, lo, hi, side in (("K1 favourite 90-99c", 0.90, 1.00, "fav"), ("K2 favourite 75-90c", 0.75, 0.90, "fav"),
                               ("K3 long shot 1-10c", 0.01, 0.10, "long")):
        for col in ("p24",):
            for wf in (True, False):
                d = returns(df, col, lo, hi, side, wf)
                if d.empty:
                    continue
                row = {"trade": name, "horizon": "24h" if col == "p24" else "1h", "fee": "taker" if wf else "none",
                       "n": len(d), "mean_return": d.ret.mean(), "win": (d.ret > 0).mean(), "avg_price": d.price.mean(),
                       "t": clustered_t(d.ret, d.event)}
                for y in (2024, 2025, 2026):
                    row[str(y)] = d[d.year == y].ret.mean()
                cats = {c: d[d.category == c].ret.mean() for c in top5}
                row["top5 categories positive"] = sum(v > 0 for v in cats.values() if pd.notna(v))
                rows.append(row)
    r = pd.DataFrame(rows)
    r["passes"] = (r.fee == "taker") & (r.horizon == "24h") & (r.mean_return > 0) & (r.t >= 3) & \
        (r[["2024", "2025", "2026"]].fillna(1) > 0).all(axis=1) & (r["top5 categories positive"] >= 3)
    pd.set_option("display.width", 220)
    print("\n", r.round(4).to_string(index=False))
    r.to_csv(ROOT / "research" / "kalshi" / "results.csv", index=False, float_format="%.4f")
    cal.to_csv(ROOT / "research" / "kalshi" / "calibration.csv", float_format="%.4f")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
    else:
        analyse()

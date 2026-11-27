"""Entry 109 — Kalshi 15-minute bitcoin up/down: fair value against market prices. See PREREGISTRATION_BTC15M.md.

    python3 -m research.kalshi.btc15m fetch     # minute prices and sampled Kalshi trades (resumable)
    python3 -m research.kalshi.btc15m           # development results (hold-out sealed)
"""
from __future__ import annotations

import io
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.crypto.data import _get as http_get  # noqa: E402
from research.kalshi.study import get  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi"
DEV = (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC"))
HOLD = (pd.Timestamp("2026-09-01", tz="UTC"), pd.Timestamp("2026-11-27", tz="UTC"))
ARCHIVE_CUTOFF = pd.Timestamp("2026-09-27", tz="UTC")
CHECKPOINTS = (1, 5, 10)
SEED = 20261127
HOLDOUT_OPEN = False


def minutes() -> pd.DataFrame:
    f = CACHE / "btcusdt_1m.parquet"
    if f.exists():
        return pd.read_parquet(f)
    parts = []
    urls = [f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-{m}.zip"
            for m in pd.period_range("2026-02", "2026-10", freq="M")]
    urls += [f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{d:%Y-%m-%d}.zip"
             for d in pd.date_range("2026-11-01", "2026-11-26")]
    for u in urls:
        raw = http_get(u)
        if raw is None:
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            d = pd.read_csv(z.open(z.namelist()[0]), header=None)
        if not str(d.iloc[0, 0]).isdigit():
            d = d.iloc[1:]
        d = d.iloc[:, [0, 4]].astype(float)
        d.columns = ["ts", "close"]
        parts.append(d)
    df = pd.concat(parts)
    ts = df.ts.astype("int64")
    ts = ts.where(ts < 1e14, ts // 1000)
    df["end"] = pd.to_datetime(ts, unit="ms", utc=True) + pd.Timedelta(minutes=1)   # the minute ENDING at this time
    df = df.drop_duplicates("end").set_index("end").sort_index()[["close"]]
    df.to_parquet(f)
    return df


def windows() -> pd.DataFrame:
    w = pd.read_parquet(CACHE / "btc15m_markets.parquet")
    w["open"] = pd.to_datetime(w["open"], utc=True)
    w["close"] = pd.to_datetime(w["close"], utc=True)
    w = w[w.result.isin(["yes", "no"]) & w.strike.notna() & w.final.notna()].copy()
    w["final"] = pd.to_numeric(w.final.astype(str).str.replace(",", "", regex=False), errors="coerce")
    w["strike"] = pd.to_numeric(w.strike.astype(str).str.replace(",", "", regex=False), errors="coerce")
    w = w.dropna(subset=["final", "strike"])
    return w.sort_values("close").reset_index(drop=True)


def last_trade(ticker: str, t: pd.Timestamp, archived: bool):
    d = get("/historical/trades" if archived else "/markets/trades", {"ticker": ticker, "max_ts": int(t.timestamp()), "limit": 1})
    tr = d.get("trades") or []
    if not tr:
        return None, None
    x = tr[0]
    p = x.get("yes_price_dollars")
    return (float(p) if p is not None else None), pd.Timestamp(x["created_time"])


def sample(w: pd.DataFrame, span, n: int) -> pd.DataFrame:
    s = w[(w.close >= span[0]) & (w.close < span[1])]
    rng = np.random.default_rng(SEED)
    return s.iloc[np.sort(rng.permutation(len(s))[:n])]


def fetch():
    px = minutes()
    print(f"minutes {px.index.min()} to {px.index.max()}: {len(px):,}", flush=True)
    w = windows()
    todo = sample(w, DEV, 2000)
    if HOLDOUT_OPEN:
        todo = pd.concat([todo, sample(w, HOLD, 1000)])
    f = CACHE / "btc15m_trades.parquet"
    rows = pd.read_parquet(f).to_dict("records") if f.exists() else []
    have = {(r["ticker"], r["m"]) for r in rows}
    for i, r in enumerate(todo.itertuples()):
        for m in CHECKPOINTS:
            if (r.ticker, m) in have:
                continue
            c = r.open + pd.Timedelta(minutes=m)
            p, ts = last_trade(r.ticker, c, archived=r.close < ARCHIVE_CUTOFF)
            rows.append({"ticker": r.ticker, "m": m, "price": p, "trade_ts": ts})
        if i % 200 == 199:
            pd.DataFrame(rows).to_parquet(f)
            print(f"  {i + 1}/{len(todo)} windows", flush=True)
    pd.DataFrame(rows).to_parquet(f)
    print("done", flush=True)


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def build(holdout: bool = False) -> pd.DataFrame:
    px = minutes()["close"]
    lr = np.log(px).diff()
    w = windows()
    # basis from settled windows: settlement / Binance close at the window's close - 1, median of the previous 96
    w["bin_close"] = px.reindex(w.close).values
    w["basis"] = (w.final / w.bin_close - 1).rolling(96, min_periods=48).median().shift(1)
    t = pd.read_parquet(CACHE / "btc15m_trades.parquet").merge(w, on="ticker")
    span = HOLD if holdout else DEV
    t = t[(t.close >= span[0]) & (t.close < span[1])].copy()
    t["chk"] = t.open + pd.to_timedelta(t.m, unit="min")
    t["S"] = px.reindex(t.chk).values * (1 + t.basis.values)
    sig = lr.rolling(60, min_periods=50).std()
    t["sigma"] = sig.reindex(t.chk).values
    t["tau"] = 15 - t.m - 0.5
    t["fair"] = norm.cdf(np.log(t.S / t.strike) / (t.sigma * np.sqrt(t.tau)))
    t["fresh"] = (t.chk - pd.to_datetime(t.trade_ts, utc=True)) <= pd.Timedelta(seconds=60)
    return t.dropna(subset=["fair", "basis"])


def trades(t: pd.DataFrame, slip: float = 0.01) -> pd.DataFrame:
    x = t[t.fresh & t.price.notna() & (t.price > 0) & (t.price < 1)].copy()
    yf = (x.price + slip).clip(upper=0.99); nf = (1 - x.price + slip).clip(upper=0.99)
    yfee = yf.map(fee); nfee = nf.map(fee)
    by = x.fair - yf - yfee >= 0.03
    bn = (1 - x.fair) - nf - nfee >= 0.03
    win = x.result == "yes"
    out = []
    for side, sel, fill, fe, w in (("YES", by, yf, yfee, win), ("NO", bn, nf, nfee, ~win)):
        z = x[sel].copy(); z["side"] = side
        z["cost"] = fill[sel] + fe[sel]
        z["ret"] = (w[sel].astype(float) - z.cost) / z.cost
        out.append(z)
    return pd.concat(out)


def clustered_t(r, g):
    m = r.mean(); s = (r - m).groupby(g).sum(); G = len(s)
    se = np.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / len(r)
    return m / se if se > 0 else np.nan


def analyse():
    t = build()
    print(f"development checkpoints: {len(t):,} ({t.ticker.nunique():,} windows); with a trade in the prior 60 s: {int(t.fresh.sum()):,}")
    print(f"basis (settlement vs Binance) median {t.basis.median() * 1e4:+.1f} bp; settlement vs model fair at checkpoints:")
    t["fb"] = (t.fair * 10).clip(0, 9.999).astype(int)
    cal = t[t.fresh].groupby("fb").agg(n=("fair", "size"), fair=("fair", "mean"), market=("price", "mean"),
                                         outcome=("result", lambda s: (s == "yes").mean()))
    print(cal.round(3).to_string())
    tr = trades(t); tr2 = trades(t, 0.02)
    tr["day"] = tr.close.dt.date
    mid = pd.Timestamp("2026-06-01", tz="UTC")
    print(f"\ntrades: {len(tr)} ({(tr.side == 'YES').sum()} YES, {(tr.side == 'NO').sum()} NO); mean return per $ {tr.ret.mean():+.2%}, "
          f"win {(tr.ret > 0).mean():.0%}, clustered t {clustered_t(tr.ret, tr.day):.2f}; Mar-May {tr[tr.close < mid].ret.mean():+.2%}, "
          f"Jun-Aug {tr[tr.close >= mid].ret.mean():+.2%}; at 2c slippage {tr2.ret.mean():+.2%}")
    print(tr.groupby("m").ret.agg(["size", "mean"]).round(4).rename_axis("checkpoint minute").to_string())
    print(tr.groupby("side").ret.agg(["size", "mean"]).round(4).to_string())
    gates = {"1 trades >= 500": len(tr) >= 500,
             "2 mean > 0, t >= 3": tr.ret.mean() > 0 and clustered_t(tr.ret, tr.day) >= 3,
             "3 both halves > 0": tr[tr.close < mid].ret.mean() > 0 and tr[tr.close >= mid].ret.mean() > 0,
             "4 positive at 2c slippage": tr2.ret.mean() > 0}
    print("gates:", gates, "->", "PASS" if all(gates.values()) else "FAIL")
    tr.to_csv(ROOT / "research" / "kalshi" / "btc15m_dev_trades.csv", index=False)
    cal.to_csv(ROOT / "research" / "kalshi" / "btc15m_dev_calibration.csv", float_format="%.4f")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
    else:
        analyse()

"""Entry 114 — reversal signals through Kalshi's daily (17:00 New York) bitcoin contract.
See PREREGISTRATION_BTC_DAILY.md.

    python3 -m research.kalshi.btc_daily
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.kalshi.btc15m import ARCHIVE_CUTOFF, last_trade, windows  # noqa: E402
from research.kalshi.btc_ta import minutes, rsi  # noqa: E402
from research.kalshi.study import get  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
GATE, MIN_BETS = 0.55, 100


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def daily_frame() -> pd.DataFrame:
    c = minutes().asfreq("1min").ffill()
    days = pd.date_range("2020-02-01", "2026-11-26", freq="D")
    starts = pd.DatetimeIndex([pd.Timestamp(d.date()).replace(hour=17).tz_localize("America/New_York").tz_convert("UTC")
                               for d in days])
    s0 = c.reindex(starts).values
    e = c.reindex(starts + pd.Timedelta(days=1)).values
    df = pd.DataFrame({"start": s0, "end": e}, index=starts).dropna()
    df["up"] = df.end >= df.start
    d = df.start
    mid, sd = d.rolling(20).mean(), d.rolling(20).std(ddof=0)
    df["D1 fade daily Bollinger"] = np.where(d < mid - 2 * sd, 1, np.where(d > mid + 2 * sd, -1, 0))
    r = rsi(d, 14)
    df["D2 fade daily RSI"] = np.where(r < 25, 1, np.where(r > 75, -1, 0))
    for name, freq in (("D3 fade 15-min Bollinger, next 24h", 15), ("D4 fade hourly Bollinger, next 24h", 60)):
        q = c[c.index.minute % freq == 0] if freq == 15 else c[c.index.minute == 0]
        qm, qs = q.rolling(20).mean(), q.rolling(20).std(ddof=0)
        qq, qm, qs = q.reindex(df.index, method="ffill"), qm.reindex(df.index, method="ffill"), qs.reindex(df.index, method="ffill")
        df[name] = np.where(qq < qm - 2 * qs, 1, np.where(qq > qm + 2 * qs, -1, 0))
    prev = c.reindex(df.index - pd.Timedelta(days=1)).values
    df["D5 bet against the previous 24h"] = np.where(df.start.values >= prev, -1, 1)
    return df


def score(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for n in [c for c in df.columns if c.startswith("D")]:
        s = df[n]; bet = s != 0
        hit = ((s > 0) & df.up) | ((s < 0) & ~df.up)
        row = {"signal": n}
        for lab, (a, b) in (("2020-22", ("2020-01-01", "2023-01-01")), ("2023-25", ("2023-01-01", "2026-01-01")),
                            ("2026", ("2026-01-01", "2027-01-01"))):
            m = bet & (df.index >= a) & (df.index < b)
            row[f"{lab} bets"] = int(m.sum()); row[f"{lab} hit"] = hit[m].mean() if m.any() else np.nan
        row["passes"] = (row["2020-22 hit"] >= GATE and row["2023-25 hit"] >= GATE
                         and row["2020-22 bets"] >= MIN_BETS and row["2023-25 bets"] >= MIN_BETS)
        rows.append(row)
    r = pd.DataFrame(rows)
    s = r.copy()
    for col in s.columns:
        if "hit" in col:
            s[col] = (s[col] * 100).round(1)
    pd.set_option("display.width", 200)
    print(s.to_string(index=False))
    return r


def event_ticker(close_utc: pd.Timestamp) -> str:
    et = close_utc.tz_convert("America/New_York")
    return f"KXBTCD-{et:%y}{MONTHS[et.month - 1]}{et:%d}{et:%H}"


def kalshi(df: pd.DataFrame, name: str):
    s = df[name]
    bets = s[(s != 0) & (s.index >= "2026-03-01") & (s.index < "2026-11-26")]
    f = CACHE / f"daily_check_{name[:2]}.parquet"
    rows = pd.read_parquet(f).to_dict("records") if f.exists() else []
    have = {r["open"] for r in rows}
    for t, d in bets.items():
        if t in have:
            continue
        close = t + pd.Timedelta(days=1)
        archived = close < ARCHIVE_CUTOFF
        ms = get("/historical/markets" if archived else "/markets", {"event_ticker": event_ticker(close), "limit": 300}).get("markets", [])
        ms = [m for m in ms if m.get("floor_strike") is not None and m.get("result") in ("yes", "no")]
        if not ms:
            continue
        spot = df.loc[t, "start"] * (1 - 0.00055)
        m = min(ms, key=lambda q: abs(float(q["floor_strike"]) - spot))
        p, ts = last_trade(m["ticker"], t + pd.Timedelta(minutes=5), archived=archived)
        rows.append({"open": t, "ticker": m["ticker"], "strike": float(m["floor_strike"]), "dir": int(d), "price": p,
                     "trade_ts": ts, "result": m["result"]})
    x = pd.DataFrame(rows); x.to_parquet(f)
    x["fresh"] = (x.open + pd.Timedelta(minutes=5) - pd.to_datetime(x.trade_ts, utc=True)) <= pd.Timedelta(minutes=5)
    x = x[x.fresh & x.price.between(0.01, 0.99)].reset_index(drop=True)
    # fair-value path of the held side every 5 minutes
    px = minutes()["close"]; lr = np.log(px).diff(); sig = lr.rolling(60, min_periods=50).std()
    w = windows(); w["bin_close"] = px.reindex(w.close).values
    basis = (w.final / w.bin_close - 1).rolling(96, min_periods=48).median().set_axis(w.close)
    b = basis.reindex(x.open, method="ffill").values
    mins = list(range(10, 1440, 5))
    fair = np.full((len(x), len(mins)), np.nan)
    for j, m in enumerate(mins):
        t = x.open + pd.Timedelta(minutes=m)
        fy = norm.cdf(np.log(px.reindex(t).values * (1 + b) / x.strike.values) / (sig.reindex(t).values * np.sqrt(1440 - m - 0.5)))
        fair[:, j] = np.where(x.dir > 0, fy, 1 - fy)
    p_side = np.where(x.dir > 0, x.price, 1 - x.price)
    buy = np.minimum(p_side + 0.01, 0.99)
    cost = buy + np.array([fee(v) for v in buy])
    win = np.where(x.dir > 0, x.result == "yes", x.result == "no").astype(float)
    day = x.open.dt.date
    late = (x.open >= "2026-09-01").values
    out = []
    for tg in (None, 0.05, 0.10, 0.15):
        ret = (win - cost) / cost
        if tg is not None:
            for i in range(len(x)):
                hit = np.where(fair[i] >= p_side[i] + tg)[0]
                if len(hit):
                    sale = min(max(fair[i, hit[0]] - 0.01, 0.01), 0.99)
                    ret[i] = (sale - fee(sale) - cost[i]) / cost[i]
        r = pd.Series(ret)
        mu = r.mean(); g = (r - mu).groupby(day).sum(); G = len(g)
        tt = mu / (np.sqrt((g ** 2).sum() * G / max(G - 1, 1)) / len(r)) if G > 1 else np.nan
        need = 2 if tg is None else 3
        out.append({"signal": name, "exit": "hold" if tg is None else f"+{int(tg * 100)}c", "bets": len(r),
                    "mean": mu, "win": (r > 0).mean(), "t": tt, "Sep-Nov": r[late].mean(),
                    "passes": mu > 0 and tt >= need and r[late].mean() > 0})
    return pd.DataFrame(out)


def main():
    df = daily_frame()
    print(f"daily windows: {len(df):,}")
    r = score(df)
    r.to_csv(ROOT / "research" / "kalshi" / "btc_daily_scores.csv", index=False, float_format="%.4f")
    passers = list(r[r.passes].signal)
    print("\npass the Binance gate:", passers or "none")
    if passers:
        k = pd.concat([kalshi(df, n) for n in passers])
        s = k.copy()
        for c in ("mean", "win", "Sep-Nov"):
            s[c] = (s[c] * 100).round(1)
        print("\nKalshi daily contract, March-November 2026 (return per dollar, %):")
        print(s.round(2).to_string(index=False))
        k.to_csv(ROOT / "research" / "kalshi" / "btc_daily_kalshi.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()

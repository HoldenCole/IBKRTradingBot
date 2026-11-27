"""Entry 111 — bitcoin technical signals through Kalshi, round 2. See PREREGISTRATION_BTC_TA2.md.

    python3 -m research.kalshi.btc_ta2 score            # Binance gates for H1-H3 and C1-C5
    python3 -m research.kalshi.btc_ta2 check NAME        # Kalshi check for one signal (B1, a passer)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.kalshi.btc15m import ARCHIVE_CUTOFF, last_trade, windows  # noqa: E402
from research.kalshi.btc_ta import minutes, rsi, signals  # noqa: E402
from research.kalshi.study import get  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi"
GATE, MIN_BETS = 0.535, 1000
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def fifteen() -> pd.DataFrame:
    c = minutes().asfreq("1min").ffill()
    df = signals(c)
    lr = np.log(c).diff()
    s60 = lr.rolling(60, min_periods=50).std()
    st = df.index
    prev15 = c.reindex(st - pd.Timedelta(minutes=15)).values
    z = np.log(df.start.values / prev15) / (s60.reindex(st).values * np.sqrt(15))
    df["C1 stretched move"] = np.where(z > 2, -1, np.where(z < -2, 1, 0))
    lo, hi = c.rolling(14).min(), c.rolling(14).max()
    k = ((c - lo) / (hi - lo) * 100).reindex(st)
    df["C2 stochastic extreme"] = np.where(k < 5, 1, np.where(k > 95, -1, 0))
    up = df["up"].astype(int)
    prev = pd.DataFrame({i: up.shift(i) for i in (1, 2, 3)})
    df["C3 runs of three"] = np.where(prev.sum(axis=1) == 3, -1, np.where((prev.sum(axis=1) == 0) & prev.notna().all(axis=1), 1, 0))
    last1 = lr.reindex(st).values
    df["C4 last-minute shock"] = np.where(last1 > 3 * s60.reindex(st).values, -1, np.where(last1 < -3 * s60.reindex(st).values, 1, 0))
    b, r = df["T5 Bollinger 15-min"], df["T4 RSI(14) extremes"]
    df["C5 Bollinger and RSI agree"] = np.where((b != 0) & (b == r), b, 0)
    df["B1 breakout fade"] = -df["T7 Donchian 15-min breakout"]
    return df


def hourly() -> pd.DataFrame:
    c = minutes().asfreq("1min").ffill()
    starts = c.index[c.index.minute == 0]
    s0 = c.reindex(starts).values
    e = c.reindex(starts + pd.Timedelta(hours=1)).values
    df = pd.DataFrame({"start": s0, "end": e}, index=starts).dropna()
    df["up"] = df.end >= df.start
    h = c.reindex(df.index)
    mid, sd = h.rolling(20).mean(), h.rolling(20).std(ddof=0)
    df["H1 hourly Bollinger fade"] = np.where(h < mid - 2 * sd, 1, np.where(h > mid + 2 * sd, -1, 0))
    q = c[c.index.minute % 15 == 0]
    qm, qs = q.rolling(20).mean(), q.rolling(20).std(ddof=0)
    qq = q.reindex(df.index); qm = qm.reindex(df.index); qs = qs.reindex(df.index)
    df["H2 15-min Bollinger fade, next hour"] = np.where(qq < qm - 2 * qs, 1, np.where(qq > qm + 2 * qs, -1, 0))
    rr = rsi(h, 14)
    df["H3 hourly RSI fade"] = np.where(rr < 25, 1, np.where(rr > 75, -1, 0))
    return df


def score(df: pd.DataFrame, names: list[str], label: str) -> pd.DataFrame:
    rows = []
    for n in names:
        s = df[n]; bet = s != 0
        hit = ((s > 0) & df.up) | ((s < 0) & ~df.up)
        row = {"signal": n}
        for lab, (a, b) in (("2020-22", ("2020-01-01", "2023-01-01")), ("2023-25", ("2023-01-01", "2026-01-01")),
                            ("2026", ("2026-01-01", "2027-01-01"))):
            m = bet & (df.index >= a) & (df.index < b)
            row[f"{lab} bets"] = int(m.sum()); row[f"{lab} hit"] = hit[m].mean() if m.any() else np.nan
        for y in range(2020, 2027):
            m = bet & (df.index.year == y)
            row[str(y)] = hit[m].mean() if m.any() else np.nan
        row["bets/day"] = bet.sum() / max((df.index[-1] - df.index[0]).days, 1)
        row["passes Binance gate"] = (row["2020-22 hit"] >= GATE and row["2023-25 hit"] >= GATE
                                      and row["2020-22 bets"] >= MIN_BETS and row["2023-25 bets"] >= MIN_BETS)
        rows.append(row)
    r = pd.DataFrame(rows)
    show = r.copy()
    for col in show.columns:
        if "hit" in col or col.isdigit():
            show[col] = (show[col] * 100).round(1)
    pd.set_option("display.width", 250)
    print(f"\n{label}")
    print(show.round(1).to_string(index=False))
    return r


def report(x: pd.DataFrame, name: str) -> bool:
    for slip in (0.01, 0.02):
        fill = np.where(x.dir > 0, x.price + slip, 1 - x.price + slip).clip(max=0.99)
        cost = fill + np.array([fee(v) for v in fill])
        win = np.where(x.dir > 0, x.result == "yes", x.result == "no")
        x[f"ret{int(slip * 100)}"] = (win - cost) / cost
        x[f"cost{int(slip * 100)}"] = cost
    x["win"] = win
    x["day"] = x.open.dt.date
    r = x.ret1; m = r.mean(); g = (r - m).groupby(x.day).sum(); G = len(g)
    t = m / (np.sqrt((g ** 2).sum() * G / max(G - 1, 1)) / len(r))
    q = x.open.dt.to_period("Q").astype(str)
    print(f"\nKalshi check, {name}: {len(x)} bets, average cost {x.cost1.mean():.3f}, won {x.win.mean():.1%}, "
          f"return per $ {m:+.2%} (t {t:.2f}); at 2c slippage {x.ret2.mean():+.2%}")
    for lab, mm in (("Mar-May", x.open < "2026-06-01"), ("Jun-Aug", (x.open >= "2026-06-01") & (x.open < "2026-09-01")),
                    ("Sep-Nov", x.open >= "2026-09-01")):
        print(f"   {lab}: {int(mm.sum())} bets, won {x.win[mm].mean():.1%}, return per $ {r[mm].mean():+.2%}")
    late = r[x.open >= "2026-09-01"].mean()
    ok = m > 0 and t >= 2 and late > 0
    print("PASS" if ok else "FAIL")
    x.to_csv(ROOT / "research" / "kalshi" / f"btc_ta2_check_{name[:2]}.csv", index=False)
    return ok


def check15(name: str) -> bool:
    df = fifteen()
    w = windows().set_index("open")
    s = df[name]
    bets = s[(s != 0) & (s.index >= "2026-03-01") & (s.index < "2026-11-27")]
    f = CACHE / f"ta2_check_{name[:2]}.parquet"
    rows = pd.read_parquet(f).to_dict("records") if f.exists() else []
    have = {r["open"] for r in rows}
    print(f"{name}: {len(bets)} Kalshi-era bets", flush=True)
    for i, (t, d) in enumerate(bets.items()):
        if t in have or t not in w.index:
            continue
        m = w.loc[t]
        p, ts = last_trade(m.ticker, t + pd.Timedelta(minutes=1), archived=m.close < ARCHIVE_CUTOFF)
        rows.append({"open": t, "ticker": m.ticker, "dir": int(d), "price": p, "trade_ts": ts, "result": m.result})
        if i % 300 == 299:
            pd.DataFrame(rows).to_parquet(f); print(f"  {i + 1}/{len(bets)}", flush=True)
    x = pd.DataFrame(rows); x.to_parquet(f)
    x["fresh"] = (x.open + pd.Timedelta(minutes=1) - pd.to_datetime(x.trade_ts, utc=True)) <= pd.Timedelta(seconds=60)
    return report(x[x.fresh & x.price.between(0.01, 0.99)].copy(), name)


def hour_event(close_utc: pd.Timestamp) -> str:
    et = close_utc.tz_convert("America/New_York")
    return f"KXBTCD-{et:%y}{MONTHS[et.month - 1]}{et:%d}{et:%H}"


def check_hourly(name: str) -> bool:
    df = hourly()
    s = df[name]
    bets = s[(s != 0) & (s.index >= "2026-03-01") & (s.index < "2026-11-27")]
    f = CACHE / f"ta2_check_{name[:2]}.parquet"
    rows = pd.read_parquet(f).to_dict("records") if f.exists() else []
    have = {r["open"] for r in rows}
    print(f"{name}: {len(bets)} Kalshi-era hourly bets", flush=True)
    for i, (t, d) in enumerate(bets.items()):
        if t in have:
            continue
        close = t + pd.Timedelta(hours=1)
        ev = hour_event(close)
        archived = close < ARCHIVE_CUTOFF
        ms = get("/historical/markets" if archived else "/markets", {"event_ticker": ev, "limit": 300}).get("markets", [])
        ms = [m for m in ms if m.get("floor_strike") is not None and m.get("result") in ("yes", "no")]
        if not ms:
            continue
        spot = df.loc[t, "start"] * (1 - 0.00055)
        m = min(ms, key=lambda q: abs(float(q["floor_strike"]) - spot))
        p, ts = last_trade(m["ticker"], t + pd.Timedelta(minutes=2), archived=archived)
        rows.append({"open": t, "ticker": m["ticker"], "strike": float(m["floor_strike"]), "dir": int(d), "price": p,
                     "trade_ts": ts, "result": m["result"]})
        if i % 100 == 99:
            pd.DataFrame(rows).to_parquet(f); print(f"  {i + 1}/{len(bets)}", flush=True)
    x = pd.DataFrame(rows); x.to_parquet(f)
    x["fresh"] = (x.open + pd.Timedelta(minutes=2) - pd.to_datetime(x.trade_ts, utc=True)) <= pd.Timedelta(seconds=120)
    return report(x[x.fresh & x.price.between(0.01, 0.99)].copy(), name)


def main_score():
    f15 = fifteen()
    r15 = score(f15, [c for c in f15.columns if c.startswith("C")], "15-minute signals (Binance)")
    h = hourly()
    rh = score(h, [c for c in h.columns if c.startswith("H")], "Hourly signals (Binance)")
    out = pd.concat([r15, rh])
    out.to_csv(ROOT / "research" / "kalshi" / "btc_ta2_scores.csv", index=False, float_format="%.4f")
    print("\npass the Binance gate:", list(out[out["passes Binance gate"]].signal) or "none")


if __name__ == "__main__":
    if sys.argv[1] == "score":
        main_score()
    elif sys.argv[1] == "check":
        n = " ".join(sys.argv[2:])
        (check_hourly if n.startswith("H") else check15)(n)

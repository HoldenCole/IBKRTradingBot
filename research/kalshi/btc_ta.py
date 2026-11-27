"""Entry 110 — bitcoin technical signals for the Kalshi 15-minute up/down contract. See PREREGISTRATION_BTC_TA.md.

    python3 -m research.kalshi.btc_ta
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.crypto.data import _get as http_get  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi"
HURDLE = 0.535


def minutes() -> pd.Series:
    f = CACHE / "btcusdt_1m_2020.parquet"
    if f.exists():
        return pd.read_parquet(f)["close"]
    urls = [f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-{m}.zip"
            for m in pd.period_range("2020-01", "2026-10", freq="M")]
    urls += [f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{d:%Y-%m-%d}.zip"
             for d in pd.date_range("2026-11-01", "2026-11-26")]
    parts = []
    for i, u in enumerate(urls):
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
        if i % 12 == 11:
            print(f"  {i + 1}/{len(urls)} files", flush=True)
    df = pd.concat(parts)
    ts = df.ts.astype("int64")
    ts = ts.where(ts < 1e14, ts // 1000)
    df["end"] = pd.to_datetime(ts, unit="ms", utc=True) + pd.Timedelta(minutes=1)
    df = df.drop_duplicates("end").set_index("end").sort_index()[["close"]]
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(f)
    return df["close"]


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def signals(c: pd.Series) -> pd.DataFrame:
    c = c.asfreq("1min").ffill()
    starts = c.index[(c.index.minute % 15 == 0)]
    end = c.reindex(starts + pd.Timedelta(minutes=15)).values
    s0 = c.reindex(starts).values
    df = pd.DataFrame({"start": s0, "end": end}, index=starts).dropna()
    df["up"] = df.end >= df.start
    sgn = lambda x: np.sign(x).replace(0, 1)  # noqa: E731
    prev15 = c.reindex(df.index - pd.Timedelta(minutes=15)).values
    prev60 = c.reindex(df.index - pd.Timedelta(minutes=60)).values
    df["T1 prior-window momentum"] = sgn(pd.Series(df.start.values / prev15 - 1, index=df.index))
    df["T2 prior-window reversal"] = -df["T1 prior-window momentum"]
    df["T3 one-hour momentum"] = sgn(pd.Series(df.start.values / prev60 - 1, index=df.index))
    r = rsi(c).reindex(df.index)
    df["T4 RSI(14) extremes"] = np.where(r < 25, 1, np.where(r > 75, -1, 0))
    c15 = c.reindex(df.index)
    mid = c15.rolling(20).mean(); sd = c15.rolling(20).std(ddof=0)
    df["T5 Bollinger 15-min"] = np.where(c15 < mid - 2 * sd, 1, np.where(c15 > mid + 2 * sd, -1, 0))
    ema = c.ewm(span=240, adjust=False).mean()
    e0 = ema.reindex(df.index).values; e1 = ema.reindex(df.index - pd.Timedelta(minutes=15)).values
    df["T6 4-hour trend"] = np.where((df.start > e0) & (e0 > e1), 1, np.where((df.start < e0) & (e0 < e1), -1, 0))
    hi = c15.rolling(20).max().shift(1); lo = c15.rolling(20).min().shift(1)
    df["T7 Donchian 15-min breakout"] = np.where(c15 > hi, 1, np.where(c15 < lo, -1, 0))
    train = df[df.index < "2023-01-01"]
    rate = train.groupby(train.index.hour)["up"].mean()
    hr = df.index.hour.map(rate)
    df["T8 hour-of-day"] = np.where(hr > 0.52, 1, np.where(hr < 0.48, -1, 0))
    df.loc[df.index < "2023-01-01", "T8 hour-of-day"] = 0          # scored out of sample only
    return df


def main():
    c = minutes()
    print(f"minutes {c.index.min()} to {c.index.max()} ({len(c):,})")
    df = signals(c)
    print(f"15-minute windows: {len(df):,}; up share {df.up.mean():.3f}")
    names = [k for k in df.columns if k.startswith("T")]
    rows = []
    for n in names:
        s = df[n]
        bet = s != 0
        hit = ((s > 0) & df.up) | ((s < 0) & ~df.up)
        row = {"signal": n}
        for lab, (a, b) in (("2020-22", ("2020-01-01", "2023-01-01")), ("2023-25", ("2023-01-01", "2026-01-01")),
                            ("2026", ("2026-01-01", "2027-01-01"))):
            m = bet & (df.index >= a) & (df.index < b)
            row[f"{lab} bets"] = int(m.sum())
            row[f"{lab} hit"] = hit[m].mean() if m.any() else np.nan
        for y in range(2020, 2027):
            m = bet & (df.index.year == y)
            row[str(y)] = hit[m].mean() if m.any() else np.nan
        row["bets/day"] = bet.sum() / ((df.index[-1] - df.index[0]).days)
        p1 = row["2020-22 hit"] if not n.startswith("T8") else HURDLE
        row["passes"] = (p1 >= HURDLE and row["2023-25 hit"] >= HURDLE and row["2023-25 bets"] >= 3000
                         and (n.startswith("T8") or row["2020-22 bets"] >= 3000))
        rows.append(row)
    r = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    show = r.copy()
    for col in show.columns:
        if "hit" in col or col.isdigit():
            show[col] = (show[col] * 100).round(1)
    print(show.round(1).to_string(index=False))
    print(f"\nbreak-even hit rate at a 50c price with 2c fee and 1c slippage: 53.0%; gate {HURDLE:.1%}")
    print("passing signals:", list(r[r.passes].signal) or "none")
    r.to_csv(ROOT / "research" / "kalshi" / "btc_ta_results.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()


def kalshi_check(signal: str = "T5 Bollinger 15-min"):
    """Pre-registered Kalshi check: buy the signalled side at the last trade at or before 1 minute into the window."""
    import math
    from research.kalshi.btc15m import ARCHIVE_CUTOFF, last_trade, windows

    def fee(p):
        return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100

    df = signals(minutes())
    w = windows().set_index("open")
    s = df[signal]
    bets = s[(s != 0) & (s.index >= "2026-03-01") & (s.index < "2026-11-27")]
    f = CACHE / f"kalshi_check_{signal[:2]}.parquet"
    rows = pd.read_parquet(f).to_dict("records") if f.exists() else []
    have = {r["open"] for r in rows}
    print(f"{signal}: {len(bets)} Kalshi-era bets to price", flush=True)
    for i, (t, d) in enumerate(bets.items()):
        if t in have or t not in w.index:
            continue
        m = w.loc[t]
        chk = t + pd.Timedelta(minutes=1)
        p, ts = last_trade(m.ticker, chk, archived=m.close < ARCHIVE_CUTOFF)
        rows.append({"open": t, "ticker": m.ticker, "dir": int(d), "price": p, "trade_ts": ts, "result": m.result})
        if i % 300 == 299:
            pd.DataFrame(rows).to_parquet(f); print(f"  {i + 1}/{len(bets)}", flush=True)
    x = pd.DataFrame(rows); x.to_parquet(f)
    x["fresh"] = (x.open + pd.Timedelta(minutes=1) - pd.to_datetime(x.trade_ts, utc=True)) <= pd.Timedelta(seconds=60)
    x = x[x.fresh & x.price.between(0.01, 0.99)].copy()
    for slip in (0.01, 0.02):
        fill = np.where(x.dir > 0, x.price + slip, 1 - x.price + slip).clip(max=0.99)
        cost = fill + np.array([fee(v) for v in fill])
        win = np.where(x.dir > 0, x.result == "yes", x.result == "no")
        x[f"ret{int(slip * 100)}"] = (win - cost) / cost
        x[f"cost{int(slip * 100)}"] = cost
    x["day"] = x.open.dt.date
    r = x.ret1
    m = r.mean(); g = (r - m).groupby(x.day).sum(); G = len(g)
    t = m / (np.sqrt((g ** 2).sum() * G / (G - 1)) / len(r))
    win = np.where(x.dir > 0, x.result == "yes", x.result == "no")
    print(f"\nKalshi check, {signal}: {len(x)} bets with a fresh price, average cost {x.cost1.mean():.3f}, "
          f"won {win.mean():.1%}; mean return per $ {r.mean():+.2%} (t {t:.2f}); at 2c slippage {x.ret2.mean():+.2%}")
    for lab, mm in (("Mar-May", x.open < "2026-06-01"), ("Jun-Aug", (x.open >= "2026-06-01") & (x.open < "2026-09-01")),
                    ("Sep-Nov", x.open >= "2026-09-01")):
        print(f"   {lab}: {int(mm.sum())} bets, won {win[mm.values].mean():.1%}, return per $ {r[mm].mean():+.2%}")
    print("   by side:", x.groupby("dir").ret1.agg(["size", "mean"]).round(4).to_dict())
    print("PASS" if (r.mean() > 0 and t >= 2) else "FAIL")
    x.to_csv(ROOT / "research" / "kalshi" / "btc_ta_kalshi_check.csv", index=False)

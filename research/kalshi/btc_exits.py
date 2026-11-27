"""Entry 112 — early exits (profit targets and stops) on Kalshi 15-minute bitcoin contracts.
See PREREGISTRATION_BTC_EXITS.md.

    python3 -m research.kalshi.btc_exits
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
from research.kalshi.btc15m import ARCHIVE_CUTOFF, last_trade, minutes, windows  # noqa: E402

CACHE = ROOT / "research" / "cache" / "kalshi"
SIGNALS = {"T5 Bollinger fade": "kalshi_check_T5", "B1 breakout fade": "ta2_check_B1", "C1 stretched move": "ta2_check_C1",
           "C2 stochastic": "ta2_check_C2", "C3 runs of three": "ta2_check_C3", "C5 Bollinger+RSI": "ta2_check_C5"}
TARGETS, STOPS = (0.05, 0.10, 0.15), (None, 0.10)
SEED = 20261127


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def entries() -> pd.DataFrame:
    parts = []
    for name, f in SIGNALS.items():
        x = pd.read_parquet(CACHE / f"{f}.parquet")
        x["fresh"] = (x.open + pd.Timedelta(minutes=1) - pd.to_datetime(x.trade_ts, utc=True)) <= pd.Timedelta(seconds=60)
        x = x[x.fresh & x.price.between(0.01, 0.99)].copy()
        x["signal"] = name
        parts.append(x[["signal", "open", "ticker", "dir", "price", "result"]])
    return pd.concat(parts, ignore_index=True)


def paths(e: pd.DataFrame) -> np.ndarray:
    """Fair value of the HELD side at minutes 2..14 for every entry (rows) - entry 109's model."""
    px = minutes()["close"]
    lr = np.log(px).diff()
    sig = lr.rolling(60, min_periods=50).std()
    w = windows()
    w["bin_close"] = px.reindex(w.close).values
    w["basis"] = (w.final / w.bin_close - 1).rolling(96, min_periods=48).median().shift(1)
    w = w.set_index("ticker")
    K = w.strike.reindex(e.ticker).values
    b = w.basis.reindex(e.ticker).values
    out = np.full((len(e), 13), np.nan)
    for j, m in enumerate(range(2, 15)):
        t = e.open + pd.Timedelta(minutes=m)
        S = px.reindex(t).values * (1 + b)
        s = sig.reindex(t).values
        tau = 15 - m - 0.5
        fy = norm.cdf(np.log(S / K) / (s * np.sqrt(tau)))
        out[:, j] = np.where(e.dir.values > 0, fy, 1 - fy)
    return out


def simulate(e: pd.DataFrame, fair: np.ndarray, target: float | None, stop: float | None, adj: float = 0.0):
    p_side = np.where(e.dir > 0, e.price, 1 - e.price)
    buy = np.minimum(p_side + 0.01, 0.99)
    cost = buy + np.array([fee(v) for v in buy])
    win = np.where(e.dir > 0, e.result == "yes", e.result == "no").astype(float)
    ret = (win - cost) / cost
    exit_min = np.full(len(e), np.nan)
    if target is not None:
        for i in range(len(e)):
            for j in range(fair.shape[1]):
                f = fair[i, j]
                if not np.isfinite(f):
                    continue
                hit_t = f >= p_side[i] + target
                hit_s = stop is not None and f <= p_side[i] - stop
                if hit_t or hit_s:
                    sale = min(max(f - 0.01 + adj, 0.01), 0.99)
                    ret[i] = (sale - fee(sale) - cost[i]) / cost[i]
                    exit_min[i] = j + 2
                    break
    return ret, exit_min


def tstat(r: pd.Series, g: pd.Series) -> float:
    m = r.mean(); s = (r - m).groupby(g).sum(); G = len(s)
    return m / (np.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / len(r))


def run(e, fair, adj=0.0, show=True):
    rows = []
    day = e.open.dt.date
    late = (e.open >= "2026-09-01").values
    for name in SIGNALS:
        sel = (e.signal == name).values
        es, fs = e[sel].reset_index(drop=True), fair[sel]
        for tg, st in [(None, None)] + [(t, s) for t in TARGETS for s in STOPS]:
            r, xm = simulate(es, fs, tg, st, adj)
            r = pd.Series(r)
            rows.append({"signal": name, "target": "hold" if tg is None else f"+{int(tg * 100)}c",
                         "stop": "-" if st is None else f"-{int(st * 100)}c", "bets": len(r), "mean": r.mean(),
                         "win": (r > 0).mean(), "exited early": np.isfinite(xm).mean(),
                         "t": tstat(r, day[sel].reset_index(drop=True)),
                         "Mar-May": r[(es.open < "2026-06-01").values].mean(),
                         "Jun-Aug": r[((es.open >= "2026-06-01") & (es.open < "2026-09-01")).values].mean(),
                         "Sep-Nov": r[late[sel]].mean()})
    df = pd.DataFrame(rows)
    df["passes"] = (df.target != "hold") & (df["mean"] > 0) & (df.t >= 3) & (df["Sep-Nov"] > 0)
    if show:
        pd.set_option("display.width", 220)
        s = df.copy()
        for c in ("mean", "win", "exited early", "Mar-May", "Jun-Aug", "Sep-Nov"):
            s[c] = (s[c] * 100).round(1)
        print(s.round(2).to_string(index=False))
    return df


def validate(e, fair, n=400) -> float:
    """Actual Kalshi trade vs modelled fair value at early-exit minutes (+10c target, no stop)."""
    r, xm = simulate(e, fair, 0.10, None)
    idx = np.where(np.isfinite(xm))[0]
    rng = np.random.default_rng(SEED)
    pick = rng.permutation(idx)[:n]
    w = windows().set_index("ticker")
    diffs = []
    for i in pick:
        row = e.iloc[i]
        t = row.open + pd.Timedelta(minutes=int(xm[i]))
        p, ts = last_trade(row.ticker, t, archived=w.loc[row.ticker, "close"] < ARCHIVE_CUTOFF)
        if p is None or (t - pd.Timestamp(ts)) > pd.Timedelta(seconds=60):
            continue
        side = p if row.dir > 0 else 1 - p
        diffs.append(side - fair[i, int(xm[i]) - 2])
    d = pd.Series(diffs)
    print(f"\nexit-price check: {len(d)} early exits, actual Kalshi minus modelled value of the held side: "
          f"mean {d.mean() * 100:+.2f}c, median {d.median() * 100:+.2f}c")
    return float(d.mean())


def main():
    e = entries()
    print(f"entries: {len(e):,} across {e.signal.nunique()} signals")
    fair = paths(e)
    df = run(e, fair)
    adj = validate(e, fair)
    if adj < -0.005:
        print(f"\nactual exits were worse than modelled by {-adj * 100:.2f}c: recomputing with that haircut")
        df = run(e, fair, adj=adj)
    df.to_csv(ROOT / "research" / "kalshi" / "btc_exits_results.csv", index=False, float_format="%.4f")
    print("\npassing trials:", df[df.passes][["signal", "target", "stop"]].to_dict("records") or "none")


if __name__ == "__main__":
    main()

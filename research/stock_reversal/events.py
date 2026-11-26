"""Event builder for entry 92 (see PREREGISTRATION.md). One row per stock-day move that clears
size L, with its news bucket for the open window and the close window, and every horizon's
fade return. The hold-out (2024-01-01 on) is refused unless holdout=True."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.stock_reversal.data import CACHE, membership
from research.swing.data import ohlc

DEV_END = pd.Timestamp("2024-01-01")
START = pd.Timestamp("2005-01-01")
HOLDOUT_FLAG = "I have passed every development gate and open the hold-out once"


def prices(t: str) -> pd.DataFrame | None:
    f = CACHE / f"px_{t}.parquet"
    return pd.read_parquet(f) if f.exists() else None


def _filings(t: str) -> pd.DataFrame | None:
    f = CACHE / f"sec_{t}.parquet"
    return pd.read_parquet(f) if f.exists() else None


def _session_index(times: pd.Series, bounds: np.ndarray) -> np.ndarray:
    """Session k such that bounds[k-1] < time <= bounds[k] (bounds = 16:00 each session)."""
    return np.searchsorted(bounds, times.values.astype("datetime64[ns]"), side="left")


def stock_events(t: str, wins: pd.DataFrame, spy: pd.DataFrame, holdout: bool):
    px = prices(t)
    fl = _filings(t)
    if px is None or fl is None or fl.empty:
        return None, None
    df = px.reindex(spy.index)
    sess = spy.index
    first = px.index[0]
    member = np.zeros(len(sess), bool)
    for _, w in wins.iterrows():
        if first > max(w.start_date, pd.Timestamp("2004-06-01")) - pd.Timedelta(days=60):
            continue                                  # possible reused ticker: skip this window
        member |= (sess >= w.start_date) & (sess <= w.end_date)
    if not member.any():
        return None, 0
    o, c = df["open"].values, df["close"].values
    so, sc = spy["open"].values, spy["close"].values
    pc = np.r_[np.nan, c[:-1]]; spc = np.r_[np.nan, sc[:-1]]
    g = (o / pc - 1) - (so / spc - 1)
    d = (c / pc - 1) - (sc / spc - 1)
    ex = pd.Series(d, index=sess)
    sigma = ex.rolling(60, min_periods=50).std().shift(1).values
    rawpc = np.r_[np.nan, df["raw_close"].values[:-1]]
    dv = pd.Series(df["raw_close"].values * df["volume"].values, index=sess).rolling(20, min_periods=15).median().shift(1).values

    close_t = sess + pd.Timedelta(hours=16)
    open_t = sess + pd.Timedelta(hours=9, minutes=30)
    acc = fl["accepted"].dropna()
    k_all = _session_index(acc, close_t.values)                     # close-window session of each filing
    is_e = fl.loc[acc.index, "earnings"].values
    n = len(sess)
    ok = k_all < n
    k_all, is_e, acc_v = k_all[ok], is_e[ok], acc.values[ok]
    before_open = acc_v <= open_t.values[k_all]
    e_close = np.zeros(n, bool); e_close[k_all[is_e]] = True
    e_open = np.zeros(n, bool); e_open[k_all[is_e & before_open]] = True
    any_close = np.zeros(n, bool); any_close[k_all] = True
    any_open = np.zeros(n, bool); any_open[k_all[before_open]] = True
    # filings accepted between the open and the close of t are unknown at an open entry (open window)

    # N window: from 16:00 five sessions before t (sessions t-4..t-1, then t up to the window end)
    prev5_any = np.r_[np.zeros(1), pd.Series(any_close.astype(int)).rolling(4, min_periods=1).sum().values[:-1]] > 0
    prev5_e = np.r_[np.zeros(1), pd.Series(e_close.astype(int)).rolling(5, min_periods=1).sum().values[:-1]] > 0
    cover = np.r_[np.zeros(1), pd.Series(e_close.astype(int)).rolling(130, min_periods=1).sum().values[:-1]] > 0

    elig = member & (rawpc >= 5) & (dv >= 20e6) & cover & np.isfinite(sigma) & (sess >= START)
    if not holdout:
        elig &= sess < DEV_END
    days = int(member[(sess >= START) & ((sess < DEV_END) | holdout)].sum())

    # forward prices
    nxt_o = np.r_[o[1:], np.nan]; nxt_c = np.r_[c[1:], np.nan]; c5 = np.r_[c[5:], [np.nan] * 5]
    snxt_o = np.r_[so[1:], np.nan]; snxt_c = np.r_[sc[1:], np.nan]; sc5 = np.r_[sc[5:], [np.nan] * 5]
    exit1_date = np.r_[sess[1:].values, [np.datetime64("NaT")]]
    exit5_date = np.r_[sess[5:].values, [np.datetime64("NaT")] * 5]
    dev_end = DEV_END.to_datetime64()
    rows = []
    # typical earnings reaction: median |move| of previous 8 earnings sessions (>=4)
    def typical(flag, mv):
        s = pd.Series(np.where(flag, np.abs(mv), np.nan))
        vals = s.dropna()
        med = vals.rolling(8, min_periods=4).median().shift(1)
        return med.reindex(range(n)).values  # only defined on earnings sessions

    typ_g, typ_d = typical(e_open, g), typical(e_close, d)
    for kind, mv, typ, e_w, any_w in (("gap", g, typ_g, e_open, any_open), ("day", d, typ_d, e_close, any_close)):
        big = elig & np.isfinite(mv) & (np.abs(mv) >= 0.05) & (np.abs(mv) >= 3 * sigma)
        for i in np.where(big)[0]:
            if kind == "gap":
                ret, sret = c[i] / o[i] - 1, sc[i] / so[i] - 1
                rets = {"H0": (ret, sret)}
            else:
                rets = {"H1": (nxt_o[i] / c[i] - 1, snxt_o[i] / sc[i] - 1),
                        "H2": (nxt_c[i] / c[i] - 1, snxt_c[i] / sc[i] - 1),
                        "H3": (c5[i] / c[i] - 1, sc5[i] / sc[i] - 1)}
                if not holdout:
                    if pd.isna(exit1_date[i]) or exit1_date[i] >= dev_end:
                        rets = {}
                    elif pd.isna(exit5_date[i]) or exit5_date[i] >= dev_end:
                        rets.pop("H3")
            if e_w[i]:
                bucket = "E"
            elif any_w[i]:
                bucket = "F"
            elif not (prev5_any[i] or prev5_e[i]):
                bucket = "N"
            else:
                bucket = None
            ex_flag = bool(e_w[i] and np.isfinite(typ[i]) and abs(mv[i]) > 2 * typ[i])
            size = "X" if (abs(mv[i]) >= 0.10 and abs(mv[i]) >= 5 * sigma[i]) else "L"
            for hz, (r, sr) in rets.items():
                if not (np.isfinite(r) and np.isfinite(sr)):
                    continue
                rows.append((t, sess[i], kind, hz, bucket, ex_flag, size, np.sign(mv[i]), mv[i], sigma[i], r, r - sr))
    return rows, days


COLS = ["ticker", "date", "kind", "horizon", "bucket", "ex", "size", "dir", "move", "sigma", "ret", "xret"]


def build(holdout: str | bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    if holdout and holdout != HOLDOUT_FLAG:
        raise PermissionError("hold-out is locked")
    hold = bool(holdout)
    spy = ohlc("SPY")
    m = membership()
    rows, cov = [], []
    for t, wins in m.groupby("ticker"):
        r, days = stock_events(t, wins, spy, hold)
        if r:
            rows += r
        # coverage: member-days with usable prices, by year
        sess = spy.index[(spy.index >= START) & ((spy.index < DEV_END) | hold)]
        mem = np.zeros(len(sess), bool)
        for _, w in wins.iterrows():
            mem |= (sess >= w.start_date) & (sess <= w.end_date)
        px = prices(t)
        have = mem & (sess.isin(px.index) if px is not None else False) & (_filings(t) is not None)
        cov.append(pd.DataFrame({"year": sess.year, "member": mem, "have": have}))
    ev = pd.DataFrame(rows, columns=COLS)
    c = pd.concat(cov).groupby("year")[["member", "have"]].sum()
    c["share"] = c["have"] / c["member"]
    return ev, c

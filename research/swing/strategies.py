"""Signal definitions for the swing study. Each returns (entry, exit, max_hold)."""
from __future__ import annotations

import pandas as pd

from research.swing.lib import bollinger, ibs, rsi, sma


def bb_mr(df, n=20, k=2.0, exit="mid", hold=10, trend=False):
    c = df["close"]
    mid, up, lo, pctb, bw = bollinger(c, n, k)
    entry = c < lo
    if trend:
        entry &= c > sma(c, 200)
    ex = {"mid": c > mid, "sma5": c > sma(c, 5), "none": pd.Series(False, index=c.index)}[exit]
    return entry, ex, hold


def bb_breakout(df, n=20, k=2.0, hold=40, squeeze=False):
    c = df["close"]
    mid, up, lo, pctb, bw = bollinger(c, n, k)
    entry = (c > up) & (c.shift(1) <= up.shift(1))
    if squeeze:
        entry &= bw.shift(1).rolling(126).rank(pct=True) < 0.25
    return entry, c < mid, hold


def rsi2(df, th=10, hold=10, trend=True):
    c = df["close"]
    entry = rsi(c, 2) < th
    if trend:
        entry &= c > sma(c, 200)
    return entry, c > sma(c, 5), hold


def ibs_mr(df, th=0.2, hold=5, trend=False):
    c = df["close"]
    entry = ibs(df) < th
    if trend:
        entry &= c > sma(c, 200)
    return entry, c > df["high"].shift(1), hold


def bb_ibs(df, n=20, k=2.0, th=0.2, hold=10):
    e1, x1, _ = bb_mr(df, n, k)
    return e1 & (ibs(df) < th), x1, hold


def bb_rsi(df, n=20, k=2.0, th=10, hold=10):
    e1, _, _ = bb_mr(df, n, k)
    c = df["close"]
    return e1 & (rsi(c, 2) < th), c > sma(c, 5), hold


def bb_touch_trend(df, n=20, k=2.0, hold=10):
    """Pullback to the lower band inside an uptrend (close > 200d SMA)."""
    return bb_mr(df, n, k, trend=True, hold=hold)


PRIMARY = {
    "BB(20,2) lower -> mid": lambda df: bb_mr(df),
    "BB(20,2) + 200d trend": lambda df: bb_mr(df, trend=True),
    "RSI2<10 + 200d trend": lambda df: rsi2(df),
    "IBS<0.2": lambda df: ibs_mr(df),
    "BB + IBS<0.2": lambda df: bb_ibs(df),
    "BB + RSI2<10": lambda df: bb_rsi(df),
    "BB breakout": lambda df: bb_breakout(df),
    "BB squeeze breakout": lambda df: bb_breakout(df, squeeze=True),
}

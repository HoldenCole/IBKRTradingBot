"""Pure-function indicators. Inputs are pandas Series indexed by time."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def typical_price(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    return (high + low + close) / 3.0


def ewo(high: pd.Series, low: pd.Series, close: pd.Series,
        fast: int = 5, slow: int = 35) -> pd.Series:
    """Elliott Wave Oscillator on typical price: SMA(fast) - SMA(slow)."""
    tp = typical_price(high, low, close)
    return sma(tp, fast) - sma(tp, slow)


def ewo_zscore(high: pd.Series, low: pd.Series, close: pd.Series,
               fast: int = 5, slow: int = 35, lookback: int = 252) -> pd.Series:
    raw = ewo(high, low, close, fast=fast, slow=slow)
    mean = raw.rolling(window=lookback, min_periods=lookback).mean()
    std = raw.rolling(window=lookback, min_periods=lookback).std(ddof=0)
    z = (raw - mean) / std.replace(0, np.nan)
    return z


def rsi(close: pd.Series, period: int = 2) -> pd.Series:
    """Wilder RSI. period=2 is the Connors variant used in the spec."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0, 100.0)
    return out


def ibs(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Internal Bar Strength = (close - low) / (high - low). NaN where high==low."""
    rng = (high - low).replace(0, np.nan)
    return (close - low) / rng


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Session VWAP. Caller must pass intraday bars from a single session."""
    tp = typical_price(high, low, close)
    cum_vol = volume.cumsum().replace(0, np.nan)
    return (tp * volume).cumsum() / cum_vol

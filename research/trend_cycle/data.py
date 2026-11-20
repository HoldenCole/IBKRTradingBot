"""Long-history bars for the quadrant-balance studies.

Member histories use TODAY'S S&P 500 constituents (survivorship-biased:
names that died or were dropped are missing, so historical balances are
somewhat too healthy). Monthly bars, unadjusted (split-adjusted) closes,
one Yahoo request per member; cached in research/cache/qb_members_1mo.pkl.
"""
from __future__ import annotations

import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data.yahoo import _CHART, _closes, _get_json, _result  # noqa: E402
from src.portfolio.trend_cycle import fetch_sp500_members  # noqa: E402

CACHE = ROOT / "research" / "cache"


def fetch_bars(symbol: str, interval: str = "1mo", start: str = "1984-01-01") -> pd.Series:
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int(datetime.now(tz=timezone.utc).timestamp())
    url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval={interval}"
    s = _closes(_result(_get_json(url), symbol), symbol, interval, adjusted=False)
    if interval == "1mo":
        s.index = s.index.to_period("M").to_timestamp("M")      # stamp at month end
        s = s[~s.index.duplicated(keep="last")]
    return s


def member_monthly(refresh: bool = False) -> dict[str, pd.Series]:
    f = CACHE / "qb_members_1mo.pkl"
    if f.exists() and not refresh:
        return pickle.load(open(f, "rb"))
    out = {}
    for sym in fetch_sp500_members():
        try:
            out[sym] = fetch_bars(sym, "1mo")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.12)
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(f, "wb"))
    return out


def index_daily(symbol: str = "^GSPC") -> pd.Series:
    from research.swing.data import fetch_ohlc
    f = CACHE / f"qb_index_{symbol.replace('^', '')}.pkl"
    if f.exists():
        return pickle.load(open(f, "rb"))
    s = fetch_ohlc(symbol, start="1980-01-01")["raw_close"]
    pickle.dump(s, open(f, "wb"))
    return s


if __name__ == "__main__":
    m = member_monthly()
    lens = pd.Series({k: len(v) for k, v in m.items()})
    first = pd.Series({k: v.index[0] for k, v in m.items()})
    print(f"members {len(m)}; with history before 1990: {(first < '1990-01-01').sum()}, before 2007: {(first < '2007-01-01').sum()}")
    g = index_daily(); print("index", g.index[0].date(), g.index[-1].date())

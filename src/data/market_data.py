"""IBKR market-data helpers for the CL1/USO strategy runner.

Reconstructed 2026-09-21 (original lost to the `data/` ignore rule).
Provides the names imported by src/main.py and src/live_runner.py:
qualify_uso, front_month_cl, fetch_minute_bars, save_bars, load_bars.
ib_insync is imported lazily so the rotation code never needs it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BARS_DIR = Path(__file__).resolve().parents[2] / "data" / "bars"


def qualify_uso(ib):
    from ib_insync import Stock

    contract = Stock("USO", "SMART", "USD")
    ib.qualifyContracts(contract)
    return contract


def front_month_cl(ib):
    """Nearest-expiry NYMEX crude future (CL) that is still trading."""
    from ib_insync import Future

    details = ib.reqContractDetails(Future("CL", exchange="NYMEX"))
    if not details:
        raise RuntimeError("no CL contract details returned")
    today = pd.Timestamp.today().strftime("%Y%m%d")
    live = sorted((d.contract for d in details if d.contract.lastTradeDateOrContractMonth >= today),
                  key=lambda c: c.lastTradeDateOrContractMonth)
    if not live:
        raise RuntimeError("no live CL contract found")
    contract = live[0]
    ib.qualifyContracts(contract)
    return contract


def fetch_minute_bars(ib, contract, days: int = 5, what: str = "TRADES") -> pd.DataFrame:
    from ib_insync import util

    bars = ib.reqHistoricalData(
        contract, endDateTime="", durationStr=f"{days} D", barSizeSetting="1 min",
        whatToShow=what, useRTH=False, formatDate=1,
    )
    df = util.df(bars)
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)
    return df


def save_bars(df: pd.DataFrame, name: str) -> Path:
    BARS_DIR.mkdir(parents=True, exist_ok=True)
    path = BARS_DIR / f"{name}.csv"
    df.to_csv(path)
    return path


def load_bars(name: str) -> pd.DataFrame:
    path = BARS_DIR / f"{name}.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df

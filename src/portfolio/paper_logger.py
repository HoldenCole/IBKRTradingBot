"""Monthly paper logger for the quadrant rotation portfolios (matrix v5).

Run once a month (any day; idempotent per calendar month):

    python -m src.main --paper-log

Each run:
1. Fetches daily closes, truncates to COMPLETED months only (ex-ante:
   the quadrant and all resolution signals for month T use data through
   the end of month T-1, even when run mid-month).
2. Classifies the quadrant via the locked switch, computes the v3
   resolution signals — TLT 10-month trend flag (conditional-duration
   S cell) and 6-month commodity momentum (reflation tilt).
3. Appends one row to paper/ledger.csv — month, quadrant, signals,
   matrix version, per-tier RESOLVED allocations — unless the month is
   already logged. Append-only: snapshots make later matrix revisions
   unable to repaint history.
4. Marks the ledger to market vs SPY.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from loguru import logger

from src.portfolio.matrix import (
    INCLUDE_SHORTS,
    MATRIX_VERSION,
    R_TILT,
    TIERS,
    all_tickers,
    resolve_allocation,
)
from src.regime.quadrant import SMA_MONTHS, Quadrant, classify

LEDGER_PATH = Path("paper/ledger.csv")
LEDGER_COLUMNS = ["month", "logged_at", "quadrant", "matrix_version", "signals", "allocations"]
MOMENTUM_MONTHS = 6


def completed_month_closes(daily: pd.Series, today: date) -> pd.Series:
    """Month-end closes using ONLY months completed before `today`'s month."""
    cutoff = pd.Timestamp(today.replace(day=1))
    return daily[daily.index < cutoff].resample("ME").last().dropna()


def compute_signals(prices: dict[str, pd.Series], today: date) -> dict:
    """Quadrant + v3 resolution signals from completed-month data."""
    spy_m = completed_month_closes(prices["SPY"], today)
    dbc_m = completed_month_closes(prices["DBC"], today)
    quadrant = classify(spy_m, dbc_m)
    if quadrant is None:
        raise RuntimeError("not enough history to classify the quadrant")

    tlt_m = completed_month_closes(prices["TLT"], today)
    tlt_up = None
    if len(tlt_m) >= SMA_MONTHS:
        tlt_up = bool(tlt_m.iloc[-1] > tlt_m.tail(SMA_MONTHS).mean())

    momentum: dict[str, float] = {}
    trio_assets = {a for trio in R_TILT.values() for a in trio}
    for asset in sorted(trio_assets):
        if asset not in prices:
            continue
        m = completed_month_closes(prices[asset], today)
        if len(m) > MOMENTUM_MONTHS:
            momentum[asset] = round(float(m.iloc[-1] / m.iloc[-(MOMENTUM_MONTHS + 1)] - 1), 4)

    return {"quadrant": quadrant, "tlt_trend_up": tlt_up, "commodity_momentum": momentum}


def load_ledger(path: Path = LEDGER_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    return pd.read_csv(path, dtype=str)


def append_entry(
    quadrant: Quadrant,
    today: date,
    path: Path = LEDGER_PATH,
    tlt_trend_up: bool | None = None,
    commodity_momentum: dict[str, float] | None = None,
) -> bool:
    """Append this month's row with resolved allocations. False if logged."""
    ledger = load_ledger(path)
    month = today.strftime("%Y-%m")
    if not ledger.empty and (ledger["month"] == month).any():
        logger.info(f"{month} already logged — nothing to do")
        return False
    allocs = {
        tier: resolve_allocation(tier, quadrant, tlt_trend_up, commodity_momentum)
        for tier in TIERS
    }
    row = {
        "month": month,
        "logged_at": today.isoformat(),
        "quadrant": quadrant.name,
        "matrix_version": MATRIX_VERSION,
        "signals": json.dumps(
            {
                "tlt_trend_up": tlt_trend_up,
                "commodity_momentum": commodity_momentum or {},
                "include_shorts": INCLUDE_SHORTS,
            }
        ),
        "allocations": json.dumps(allocs),
    }
    ledger = pd.concat([ledger, pd.DataFrame([row])], ignore_index=True)
    path.parent.mkdir(exist_ok=True)
    ledger.to_csv(path, index=False)
    logger.info(f"Logged {month}: {quadrant.name} (matrix {MATRIX_VERSION}, tlt_up={tlt_trend_up})")
    return True


def mark_to_market(ledger: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Per-tier paper performance since ledger inception.

    Each entry's allocation is held (daily-rebalanced to target) from
    its logged_at until the next entry's logged_at.
    """
    if ledger.empty:
        return pd.DataFrame()
    ledger = ledger.sort_values("logged_at").reset_index(drop=True)
    rets = prices.sort_index().pct_change()
    starts = [pd.Timestamp(d) for d in ledger["logged_at"]]
    rows = []
    for tier in TIERS:
        parts = []
        for i in range(len(ledger)):
            allocs = json.loads(ledger.loc[i, "allocations"])[tier]
            lo = starts[i]
            hi = starts[i + 1] if i + 1 < len(ledger) else None
            window = rets.loc[rets.index > lo]
            if hi is not None:
                window = window.loc[window.index <= hi]
            if window.empty:
                continue
            parts.append(sum(window[a] * w for a, w in allocs.items()))
        if not parts:
            continue
        r = pd.concat(parts).dropna()
        eq = (1 + r).cumprod()
        rows.append({"tier": tier, "since": str(starts[0].date()),
                     "ret": float((1 + r).prod() - 1),
                     "maxDD": float((eq / eq.cummax() - 1).min()), "days": len(r)})
    if rows and "SPY" in prices.columns:
        spy = rets["SPY"].loc[rets.index > starts[0]].dropna()
        eq = (1 + spy).cumprod()
        rows.append({"tier": "SPY (bench)", "since": str(starts[0].date()),
                     "ret": float((1 + spy).prod() - 1),
                     "maxDD": float((eq / eq.cummax() - 1).min()), "days": len(spy)})
    return pd.DataFrame(rows)


def run_paper_log(path: Path = LEDGER_PATH) -> None:
    """Fetch, classify, resolve, append, and report. Network required."""
    from src.data.yahoo import fetch_yahoo_daily

    today = date.today()
    signal_tickers = sorted({"SPY", "DBC", "TLT"} | {a for t in R_TILT.values() for a in t})
    prices = {t: fetch_yahoo_daily(t, "2y") for t in signal_tickers}
    sig = compute_signals(prices, today)
    quadrant = sig["quadrant"]
    logger.info(
        f"Quadrant in force for {today:%Y-%m}: {quadrant.name} "
        f"(tlt_up={sig['tlt_trend_up']}, mom={sig['commodity_momentum']})"
    )
    for tier in TIERS:
        logger.info(f"  {tier:>5} target: "
                    f"{resolve_allocation(tier, quadrant, sig['tlt_trend_up'], sig['commodity_momentum'])}")
    append_entry(quadrant, today, path,
                 tlt_trend_up=sig["tlt_trend_up"],
                 commodity_momentum=sig["commodity_momentum"])

    ledger = load_ledger(path)
    referenced: set[str] = set(all_tickers()) | {"SPY"}
    for blob in ledger["allocations"]:
        for tier_alloc in json.loads(blob).values():
            referenced.update(tier_alloc)
    px = dict(prices)
    for t in sorted(referenced):
        if t not in px:
            px[t] = fetch_yahoo_daily(t, "2y")
    frame = pd.DataFrame(px)
    report = mark_to_market(ledger, frame)
    if report.empty:
        if ledger.empty:
            print("Ledger empty — nothing to mark to market yet.")
        else:
            print("No completed trading days since the first entry — "
                  "performance starts accruing next session.")
        return
    print("\n=== Paper rotation ledger — mark to market ===")
    for r in report.itertuples():
        print(f"{r.tier:>12}: {r.ret:+8.2%}  maxDD={r.maxDD:6.1%}  ({r.days} days since {r.since})")

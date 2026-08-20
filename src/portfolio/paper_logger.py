"""Monthly paper logger for the quadrant rotation portfolios.

Run once a month (any day; idempotent per calendar month):

    python -m src.main --paper-log

Each run:
1. Fetches daily closes for SPY and DBC, classifies the quadrant in
   force for the CURRENT month (ex-ante: month-end data through the
   last completed month, via the locked switch in src/regime/quadrant).
2. Appends one row to paper/ledger.csv — month, quadrant, matrix
   version, per-tier target allocations — unless the month is already
   logged. The ledger is committed to git: it is the forward evidence.
3. Marks the ledger to market: daily adjusted closes for all matrix
   tickers since inception, each tier rebalanced to its logged targets
   on each entry's logged_at date, performance reported vs SPY.

The ledger only ever appends. Allocations are snapshotted into the row
so later matrix revisions (v3, ...) can never repaint history.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from loguru import logger

from src.portfolio.matrix import MATRIX_VERSION, TIERS, all_tickers, allocation
from src.regime.quadrant import Quadrant, quadrant_series

LEDGER_PATH = Path("paper/ledger.csv")
LEDGER_COLUMNS = ["month", "logged_at", "quadrant", "matrix_version", "allocations"]


def classify_current_month(spy_daily: pd.Series, dbc_daily: pd.Series) -> Quadrant:
    """Quadrant in force now = classification from the last completed month."""
    series = quadrant_series(spy_daily, dbc_daily)
    if series.empty:
        raise RuntimeError("not enough history to classify the quadrant")
    return series.iloc[-1]


def load_ledger(path: Path = LEDGER_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    return pd.read_csv(path, dtype=str)


def append_entry(
    quadrant: Quadrant,
    today: date,
    path: Path = LEDGER_PATH,
) -> bool:
    """Append this month's row. Returns False if the month is already logged."""
    ledger = load_ledger(path)
    month = today.strftime("%Y-%m")
    if (ledger["month"] == month).any():
        logger.info(f"{month} already logged — nothing to do")
        return False
    allocs = {tier: allocation(tier, quadrant) for tier in TIERS}
    row = {
        "month": month,
        "logged_at": today.isoformat(),
        "quadrant": quadrant.name,
        "matrix_version": MATRIX_VERSION,
        "allocations": json.dumps(allocs),
    }
    ledger = pd.concat([ledger, pd.DataFrame([row])], ignore_index=True)
    path.parent.mkdir(exist_ok=True)
    ledger.to_csv(path, index=False)
    logger.info(f"Logged {month}: {quadrant.name} (matrix {MATRIX_VERSION})")
    return True


def mark_to_market(ledger: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Per-tier paper performance since ledger inception.

    `prices`: daily adjusted closes for every ticker appearing in the
    ledger, covering at least the first logged_at date through now.
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
    """Fetch, classify, append, and report. Network required."""
    from src.data.yahoo import fetch_yahoo_daily

    spy = fetch_yahoo_daily("SPY", "2y")
    dbc = fetch_yahoo_daily("DBC", "2y")
    quadrant = classify_current_month(spy, dbc)
    logger.info(f"Quadrant in force for {date.today():%Y-%m}: {quadrant.name}")
    for tier in TIERS:
        logger.info(f"  {tier:>5} target: {allocation(tier, quadrant)}")
    append_entry(quadrant, date.today(), path)

    ledger = load_ledger(path)
    # Fetch every ticker any ledger row references (not just the current
    # matrix) so old entries stay markable after future matrix revisions.
    referenced: set[str] = set(all_tickers()) | {"SPY"}
    for blob in ledger["allocations"]:
        for tier_alloc in json.loads(blob).values():
            referenced.update(tier_alloc)
    prices = pd.DataFrame({t: fetch_yahoo_daily(t, "2y") for t in sorted(referenced)})
    report = mark_to_market(ledger, prices)
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

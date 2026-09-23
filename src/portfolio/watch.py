"""Mid-month regime watch — READ-ONLY visibility, never trades.

The classifier only uses completed months, so re-running the paper
logger mid-month returns the month's answer unchanged. What CAN move
mid-month is the distance between current prices and the regime
boundaries. This module logs that: for each signal, today's price vs
its threshold (mean of the prior 9 completed monthly closes — the
month-end rule's exact algebraic equivalent), and the PROVISIONAL
quadrant if the month ended today, compared against the quadrant in
force from the ledger.

Informational by design: entry 67 (TESTS.md) showed that TRADING on
checkpoints faster than monthly loses 1.9-3.3pp/yr in both eras. This
watch feeds no allocation and writes to paper/watch.csv, not the
ledger. Only the monthly ledger row moves money.

    python -m src.portfolio.watch
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

from src.data.yahoo import fetch_yahoo_daily
from src.portfolio.paper_logger import FRAGILE_EXT_MAX, FRAGILE_RVOL_MIN, LEDGER_PATH, load_ledger
from src.regime.quadrant import Quadrant

WATCH_PATH = Path(__file__).resolve().parents[2] / "paper" / "watch.csv"


def boundary(daily: pd.Series, today: date) -> tuple[float, float, float]:
    """(current price, threshold, % distance). Threshold = mean of the
    prior 9 COMPLETED monthly closes — equivalent to the 10m SMA rule."""
    daily = daily[daily.index.date < pd.Timestamp(today).date()]
    monthly = daily.resample("ME").last()
    completed = monthly[monthly.index < pd.Timestamp(today).replace(day=1)]
    if len(completed) < 9:
        raise ValueError("insufficient history for 9 completed months")
    price = float(daily.iloc[-1])
    thresh = float(completed.tail(9).mean())
    return price, thresh, price / thresh - 1


def provisional_quadrant(growth_on: bool, infl_on: bool) -> Quadrant:
    if growth_on and not infl_on:
        return Quadrant.GROWTH
    if growth_on and infl_on:
        return Quadrant.REFLATION
    if infl_on:
        return Quadrant.STAGFLATION
    return Quadrant.DEFLATION


def _append_row(path: Path, row: dict) -> None:
    """Append a row; if the file's header predates new columns, rewrite it
    with the union of columns so old rows keep their values and new ones
    are blank (schema migration, never a misaligned CSV)."""
    fieldnames = list(row)
    existing: list[dict] = []
    if path.exists():
        with path.open() as fh:
            reader = csv.DictReader(fh)
            old_fields = reader.fieldnames or []
            existing = list(reader)
        if old_fields == fieldnames:
            with path.open("a", newline="") as fh:
                csv.DictWriter(fh, fieldnames=fieldnames).writerow(row)
            return
        fieldnames = list(old_fields) + [f for f in fieldnames if f not in old_fields]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in existing:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
        writer.writerow({k: row.get(k, "") for k in fieldnames})


def run_watch(today: date | None = None, path: Path = WATCH_PATH) -> dict:
    today = today or date.today()
    spy = fetch_yahoo_daily("SPY", rng="2y")
    dbc = fetch_yahoo_daily("DBC", rng="2y")
    spy_px, spy_th, spy_d = boundary(spy, today)
    dbc_px, dbc_th, dbc_d = boundary(dbc, today)
    prov = provisional_quadrant(spy_d > 0, dbc_d > 0)
    # provisional fragility (entry 70 shadow): today's price vs the 10m SMA that
    # would apply if the month ended today, and trailing 20d realized vol
    spy_hist = spy[spy.index.date < pd.Timestamp(today).date()]
    m10 = pd.concat([spy_hist.resample("ME").last().iloc[:-1].tail(9), pd.Series([spy_px])])
    ext_now = float(spy_px / m10.mean() - 1)
    rvol_now = float(spy_hist.pct_change().dropna().tail(20).std() * (252 ** 0.5))
    fragile_now = bool(prov in (Quadrant.GROWTH, Quadrant.REFLATION)
                       and ext_now < FRAGILE_EXT_MAX and rvol_now > FRAGILE_RVOL_MIN)

    in_force = None
    ledger = load_ledger()
    if not ledger.empty:
        in_force = str(ledger.iloc[-1]["quadrant"])

    row = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spy_dist": round(spy_d, 4),
        "dbc_dist": round(dbc_d, 4),
        "provisional": prov.name,
        "in_force": in_force,
        "divergence": in_force is not None and prov.name != in_force,
        "ext_now": round(ext_now, 4),
        "rvol20_now": round(rvol_now, 4),
        "fragile_now": fragile_now,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _append_row(path, row)

    logger.info(f"SPY {spy_px:,.2f} vs boundary {spy_th:,.2f} ({spy_d:+.1%}) — "
                f"growth {'ON' if spy_d > 0 else 'OFF'}")
    logger.info(f"DBC {dbc_px:,.2f} vs boundary {dbc_th:,.2f} ({dbc_d:+.1%}) — "
                f"inflation {'ON' if dbc_d > 0 else 'OFF'}")
    logger.info(f"Fragility shadow if month ended today: SPY {ext_now:+.1%} vs 10m SMA, 20d vol {rvol_now:.0%} "
                f"-> {'FRAGILE' if fragile_now else 'not fragile'} (informational)")
    if row["divergence"]:
        logger.warning(f"If the month ended today: {prov.name} (vs {in_force} in force). "
                       "INFORMATIONAL ONLY — the book rotates at the monthly row, not now.")
    else:
        logger.info(f"If the month ended today: {prov.name} — matches the quadrant in force.")
    return row


if __name__ == "__main__":
    run_watch()

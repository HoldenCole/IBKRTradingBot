"""Saturday weekly review — where things stand after the week, ahead of the
next one. READ-ONLY: trades nothing, writes no ledger row.

Reports, in order:
  1. the week and month-to-date for the assets the book cares about
  2. regime boundaries (watch row logged) + provisional quadrant + fragility
  3. PROVISIONAL versions of the monthly signals, "if the month ended today":
     breadth (sectors above their 10m line), 6m momentum tilt, TLT trend,
     and the AGG/VAGG books that would result — vs the books in force
  4. the live AGG book's week, leg by leg
  5. paper ledger mark-to-market
  6. (optional, --balance) provisional S&P 500 quadrant balance incl. the
     in-progress month (the user's weekly-fed 'main version')
Appends one row to paper/weekly.csv.

    python3 -m src.portfolio.weekly_review [--balance] [--tier AGG]
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

from src.data.yahoo import _ssl_context, fetch_yahoo_daily, fetch_yahoo_monthly
from src.portfolio.matrix import R_TILT, TIERS, resolve_allocation
from src.portfolio.paper_logger import (
    BREADTH_TICKERS, FRAGILE_EXT_MAX, FRAGILE_RVOL_MIN, MIN_BALANCE_NAMES, SP500_MEMBERS_URL,
    WASHOUT_THRESHOLD, current_allocations, load_ledger, mark_to_market, member_phase,
    quadrant_balance,
)
from src.portfolio.watch import boundary, provisional_quadrant, run_watch
from src.regime.quadrant import SMA_MONTHS, Quadrant

WEEKLY_PATH = Path(__file__).resolve().parents[2] / "paper" / "weekly.csv"
KEY_ASSETS = ["SPY", "QQQ", "XLE", "ERX", "DBC", "USO", "GLD", "GDX", "TLT", "SHY"]


def _ret(s: pd.Series, n: int) -> float:
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else float("nan")


def _mtd(s: pd.Series) -> float:
    s = s.dropna()
    last_me = s[s.index < pd.Timestamp(s.index[-1]).replace(day=1)]
    return float(s.iloc[-1] / last_me.iloc[-1] - 1) if len(last_me) else float("nan")


def provisional_monthly(daily: pd.Series) -> pd.Series:
    """Monthly closes INCLUDING the in-progress month at its latest close."""
    return daily.dropna().resample("ME").last().dropna()


def provisional_breadth(prices: dict[str, pd.Series]) -> tuple[float | None, int]:
    above = total = 0
    for t in BREADTH_TICKERS:
        if t not in prices:
            continue
        m = provisional_monthly(prices[t])
        if len(m) < SMA_MONTHS:
            continue
        total += 1
        above += int(m.iloc[-1] > m.tail(SMA_MONTHS).mean())
    return (round(above / total, 3) if total else None), total


def provisional_balance(today: date) -> dict | None:
    """S&P 500 member phases with the in-progress month included (weekly-fed)."""
    try:
        req = urllib.request.Request(SP500_MEMBERS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            lines = resp.read().decode().splitlines()
        members = [ln.split(",")[0].strip().replace(".", "-") for ln in lines[1:] if ln.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"member list fetch failed: {exc}")
        return None
    closes = {}
    for sym in members:
        try:
            m = fetch_yahoo_monthly(sym, years=3).resample("ME").last().dropna()
            if len(m) >= 6:
                closes[sym] = m
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    return quadrant_balance(closes)


def run_review(tier: str = "AGG", balance: bool = False, today: date | None = None) -> dict:
    today = today or date.today()
    ledger = load_ledger()
    month, in_force, allocs, restated = current_allocations()
    tilt_assets = sorted({a for t in R_TILT.values() for a in t})
    tickers = sorted(set(KEY_ASSETS) | set(tilt_assets) | set(BREADTH_TICKERS) | {"TLT", "DBC", "SPY"}
                     | {a for al in allocs.values() for a in al})
    prices: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            prices[t] = fetch_yahoo_daily(t, "2y")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{t}: fetch failed ({exc})")
    asof = max(s.index[-1] for s in prices.values()).date()

    # 1. the week
    print(f"\n=== WEEKLY REVIEW — prices through {asof} · ledger month {month} ({in_force}, matrix restated={restated}) ===")
    print("1) The week / month-to-date:")
    print("   " + "  ".join(f"{t} {_ret(prices[t], 5):+.1%}" for t in KEY_ASSETS if t in prices))
    print("   MTD: " + "  ".join(f"{t} {_mtd(prices[t]):+.1%}" for t in KEY_ASSETS if t in prices))

    # 2. boundaries + fragility (logs the watch row)
    w = run_watch(today)
    print(f"2) Regime: SPY {w['spy_dist']:+.1%} / DBC {w['dbc_dist']:+.1%} above their lines -> provisional {w['provisional']} "
          f"(in force {w['in_force']}); fragility: ext {w['ext_now']:+.1%}, 20d vol {w['rvol20_now']:.0%} -> {'FRAGILE' if w['fragile_now'] else 'not fragile'}")

    # 3. provisional monthly signals
    br, n_br = provisional_breadth(prices)
    tlt_m = provisional_monthly(prices["TLT"]); tlt_up = bool(tlt_m.iloc[-1] > tlt_m.tail(SMA_MONTHS).mean())
    mom = {}
    for a in tilt_assets:
        if a in prices:
            m = provisional_monthly(prices[a])
            if len(m) > 6:
                mom[a] = round(float(m.iloc[-1] / m.iloc[-7] - 1), 4)
    prov_q = Quadrant[w["provisional"]]
    washout = (br is not None and br < WASHOUT_THRESHOLD)
    prov_books = {t: resolve_allocation(t, prov_q, tlt_up, mom, breadth_washout=washout) for t in TIERS}
    logged_breadth = None
    if not ledger.empty:
        try:
            logged_breadth = json.loads(ledger.iloc[-1]["signals"]).get("breadth")
        except Exception:  # noqa: BLE001
            pass
    print(f"3) Provisional monthly signals (if the month ended {asof}):")
    print(f"   breadth {br:.1%} of {n_br} sectors above their 10m line (logged at month start: {logged_breadth})  washout={'YES' if washout else 'no'}")
    print(f"   TLT trend up: {tlt_up}   6m momentum: {mom}")
    for t in ("MOD", tier) if tier != "MOD" else ("MOD",):
        cur, nxt = allocs[t], prov_books[t]
        changes = {a: (cur.get(a, 0.0), nxt.get(a, 0.0)) for a in sorted(set(cur) | set(nxt)) if abs(cur.get(a, 0.0) - nxt.get(a, 0.0)) > 1e-9}
        print(f"   {t} book in force: {cur}")
        print(f"   {t} if month ended today: {nxt}" + (f"   CHANGES: {changes}" if changes else "   (no change)"))

    # 4. live book week
    book = allocs[tier]
    legs = {a: (_ret(prices[a], 5), _mtd(prices[a])) for a in book if a in prices}
    wk = sum(book[a] * legs[a][0] for a in legs); mtd = sum(book[a] * legs[a][1] for a in legs)
    print(f"4) Live {tier} book: week {wk:+.2%}, MTD {mtd:+.2%}  (SPY week {_ret(prices['SPY'], 5):+.2%}, MTD {_mtd(prices['SPY']):+.2%})")
    print("   legs: " + "  ".join(f"{a} {book[a]:.0%}: wk {legs[a][0]:+.1%} (contrib {book[a]*legs[a][0]:+.2%})" for a in legs))

    # 5. paper MTM
    px = pd.DataFrame({t: prices[t] for t in prices})
    mtm = mark_to_market(ledger, px)
    print("5) Paper ledger mark-to-market since inception:")
    for r in mtm.to_dict("records"):
        print(f"   {r['tier']:>11}: {r['ret']:+.2%}  maxDD {r['maxDD']:.1%}  ({r['days']} days)")

    # 6. provisional balance
    bal = provisional_balance(today) if balance else None
    if bal:
        print(f"6) Provisional S&P 500 quadrant balance (in-progress month included): {bal}")

    row = {"asof": str(asof), "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "spy_dist": w["spy_dist"], "dbc_dist": w["dbc_dist"], "provisional": w["provisional"], "in_force": w["in_force"],
           "prov_breadth": br, "fragile": w["fragile_now"],
           "spy_wk": round(_ret(prices["SPY"], 5), 4), "qqq_wk": round(_ret(prices["QQQ"], 5), 4), "xle_wk": round(_ret(prices["XLE"], 5), 4),
           "dbc_wk": round(_ret(prices["DBC"], 5), 4), "gld_wk": round(_ret(prices["GLD"], 5), 4), "tlt_wk": round(_ret(prices["TLT"], 5), 4),
           f"{tier.lower()}_book_wk": round(wk, 4), "balance_q4": (bal or {}).get("q4"), "balance_dominant": (bal or {}).get("dominant")}
    WEEKLY_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not WEEKLY_PATH.exists()
    with WEEKLY_PATH.open("a", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(row))
        if is_new:
            wr.writeheader()
        wr.writerow(row)
    return row


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="AGG", choices=TIERS)
    ap.add_argument("--balance", action="store_true", help="include the ~5-minute S&P 500 member sweep")
    args = ap.parse_args()
    run_review(tier=args.tier, balance=args.balance)

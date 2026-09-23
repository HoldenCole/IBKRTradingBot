"""Monthly paper logger for the quadrant rotation portfolios (matrix v7).

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
from src.regime.quadrant import SMA_MONTHS, Quadrant, classify, shadow_classify

LEDGER_PATH = Path("paper/ledger.csv")
LEDGER_COLUMNS = ["month", "logged_at", "quadrant", "matrix_version", "signals", "allocations"]
MOMENTUM_MONTHS = 6

# v7 breadth signal: share of the sector universe above its own 10m SMA.
BREADTH_TICKERS = ["XLE", "XLY", "XLF", "XLK", "XLI", "XLB", "XLV", "XLU", "XLP",
                   "IYR", "XRT", "XHB", "ITB", "KRE", "IYT", "SMH", "GDX", "XBI"]
WASHOUT_THRESHOLD = 0.25
MIN_BREADTH_NAMES = 12  # fewer usable names -> breadth unknown, fail closed

# S&P 500 quadrant balance — INFORMATIONAL ONLY, never used in any
# resolution. The user's phase-clock: each member classified by the
# direction x acceleration of its 3m-smoothed monthly closes
# (Q1 fall/decel, Q2 rise/accel, Q3 rise/decel, Q4 fall/accel);
# the balance is the population share per quadrant. Best bottom
# DIAGNOSTIC measured (PORTFOLIOS.md); a dashboard, not a lever.
SP500_MEMBERS_URL = ("https://raw.githubusercontent.com/datasets/"
                     "s-and-p-500-companies/main/data/constituents.csv")
MIN_BALANCE_NAMES = 150

# Managed-futures watchlist — INFORMATIONAL ONLY. Filed S-cell
# instrument candidates (TESTS.md): each row logs the funds' PRIOR
# completed-month returns so the pre-registered trigger ("outperform
# the S-cell allocation over the next >=4 live S-classified months")
# can be adjudicated from ledger rows alone.
MANAGED_FUTURES_TICKERS = ["DBMF", "KMLM"]


def member_phase(monthly_closes: pd.Series) -> float | None:
    """Latest quadrant (1-4) of one member from completed monthly closes."""
    s = monthly_closes.rolling(3).mean()
    d1 = s.diff()
    d2 = d1.diff()
    if len(d2.dropna()) == 0:
        return None
    a, b = float(d1.iloc[-1]), float(d2.iloc[-1])
    if a < 0 and b >= 0:
        return 1.0
    if a >= 0 and b >= 0:
        return 2.0
    if a >= 0:
        return 3.0
    return 4.0


def quadrant_balance(monthly_closes: dict[str, pd.Series]) -> dict | None:
    """Population balance across phases; None if too few members."""
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    total = 0
    for series in monthly_closes.values():
        ph = member_phase(series)
        if ph is None:
            continue
        counts[int(ph)] += 1
        total += 1
    if total < MIN_BALANCE_NAMES:
        return None
    bal = {f"q{k}": round(v / total, 3) for k, v in counts.items()}
    bal["dominant"] = max(counts, key=counts.get)
    bal["n"] = total
    return bal


def fetch_sp500_balance(today: date) -> dict | None:
    """Fetch current members + monthly closes and compute the balance.

    Informational: any failure returns None and must never block the
    ledger run. Uses completed months only (ex-ante, like all signals).
    """
    import time as _time
    import urllib.request

    from src.data.yahoo import _ssl_context, fetch_yahoo_monthly

    try:
        req = urllib.request.Request(SP500_MEMBERS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            lines = resp.read().decode().splitlines()
        members = [ln.split(",")[0].strip().replace(".", "-")
                   for ln in lines[1:] if ln.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"S&P 500 member list fetch failed: {exc}")
        return None
    closes: dict[str, pd.Series] = {}
    for sym in members:
        try:
            s = fetch_yahoo_monthly(sym, years=3)
            m = completed_month_closes(s, today)
            if len(m) >= 6:
                closes[sym] = m
        except Exception:  # noqa: BLE001 - individual members are expendable
            pass
        _time.sleep(0.2)
    return quadrant_balance(closes)


def completed_month_closes(daily: pd.Series, today: date) -> pd.Series:
    """Month-end closes using ONLY months completed before `today`'s month."""
    cutoff = pd.Timestamp(today.replace(day=1))
    return daily[daily.index < cutoff].resample("ME").last().dropna()


# Fragility shadow (entry 70, PORTFOLIOS.md): modern-era crash months were
# entered with SPY barely above its 10m line AND elevated realized vol.
# Era-flipped pre-2007, so it is INFORMATIONAL — logged alongside, feeds no
# resolution. Promotion trigger pre-registered in TESTS.md.
FRAGILE_EXT_MAX = 0.03      # SPY no more than 3% above its 10m SMA
FRAGILE_RVOL_MIN = 0.16     # 20-day realized vol (annualized) above 16%
DELEVER_NOTCH = {"TQQQ": "QLD", "QLD": "QQQ"}


def fragility_signal(spy_daily: pd.Series, quadrant: Quadrant | None, today: date) -> dict:
    """Ex-ante fragility features from completed-month data.

    ext: last completed monthly close vs its 10-month SMA (incl. that month);
    rvol20: annualized std of the 20 daily returns ending at that month-end;
    fragile: risk-on quadrant AND ext < FRAGILE_EXT_MAX AND rvol20 > FRAGILE_RVOL_MIN.
    """
    m = completed_month_closes(spy_daily, today)
    cutoff = pd.Timestamp(today.replace(day=1))
    daily = spy_daily[spy_daily.index < cutoff].dropna()
    if len(m) < SMA_MONTHS or len(daily) < 21:
        return {"ext": None, "rvol20": None, "fragile": None}
    ext = float(m.iloc[-1] / m.tail(SMA_MONTHS).mean() - 1)
    rvol = float(daily.pct_change().dropna().tail(20).std() * (252 ** 0.5))
    risk_on = quadrant in (Quadrant.GROWTH, Quadrant.REFLATION)
    fragile = bool(risk_on and ext < FRAGILE_EXT_MAX and rvol > FRAGILE_RVOL_MIN)
    return {"ext": round(ext, 4), "rvol20": round(rvol, 4), "fragile": fragile}


def delever_one_notch(weights: dict[str, float]) -> dict[str, float]:
    """Shadow book: equity leverage one notch down (TQQQ->QLD, QLD->QQQ)."""
    out: dict[str, float] = {}
    for asset, w in weights.items():
        target = DELEVER_NOTCH.get(asset, asset)
        out[target] = round(out.get(target, 0.0) + w, 4)
    return out


def compute_signals(prices: dict[str, pd.Series], today: date) -> dict:
    """Quadrant + v3 resolution signals from completed-month data."""
    spy_m = completed_month_closes(prices["SPY"], today)
    dbc_m = completed_month_closes(prices["DBC"], today)
    quadrant = classify(spy_m, dbc_m)
    if quadrant is None:
        raise RuntimeError("not enough history to classify the quadrant")
    shadow = shadow_classify(spy_m, dbc_m)  # informational fast-entry variant

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

    above = total = 0
    for t in BREADTH_TICKERS:
        if t not in prices:
            continue
        m = completed_month_closes(prices[t], today)
        if len(m) < SMA_MONTHS:
            continue
        total += 1
        if m.iloc[-1] > m.tail(SMA_MONTHS).mean():
            above += 1
    breadth = round(above / total, 3) if total >= MIN_BREADTH_NAMES else None
    washout = (breadth < WASHOUT_THRESHOLD) if breadth is not None else None

    mf_returns: dict[str, float] = {}
    for t in MANAGED_FUTURES_TICKERS:
        if t not in prices:
            continue
        m = completed_month_closes(prices[t], today)
        if len(m) >= 2:
            mf_returns[t] = round(float(m.iloc[-1] / m.iloc[-2] - 1), 4)

    fragility = fragility_signal(prices["SPY"], quadrant, today)

    return {"quadrant": quadrant, "tlt_trend_up": tlt_up,
            "commodity_momentum": momentum,
            "breadth": breadth, "breadth_washout": washout,
            "shadow_quadrant": shadow.name if shadow else None,
            "managed_futures": mf_returns,
            "fragility": fragility}


def load_ledger(path: Path = LEDGER_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    return pd.read_csv(path, dtype=str)

def current_allocations(path: Path = LEDGER_PATH) -> tuple[str, str, dict, bool]:
    """(month, quadrant, per-tier allocations, restated) from the latest
    ledger row. If the matrix version has moved on since the row was
    logged, re-resolve every tier from the row's stored signals under the
    CURRENT matrix and flag restated=True. The ledger row itself is never
    modified (append-only); this is for the manual order tools so a
    mid-month matrix adoption can be traded before the next ledger run.
    The automated executor deliberately reads the ledger row as-is."""
    ledger = load_ledger(path)
    if ledger.empty:
        raise SystemExit("ledger is empty — run the paper logger first")
    row = ledger.iloc[-1]
    month, quadrant = str(row["month"]), str(row["quadrant"])
    allocs = json.loads(row["allocations"])
    restated = False
    signals = row.get("signals")
    if str(row["matrix_version"]) != MATRIX_VERSION and isinstance(signals, str) and signals:
        sig = json.loads(signals)
        quad = Quadrant[quadrant]
        allocs = {
            tier: resolve_allocation(
                tier, quad, sig.get("tlt_trend_up"), sig.get("commodity_momentum"),
                include_shorts=sig.get("include_shorts"),
                breadth_washout=sig.get("breadth_washout"))
            for tier in TIERS
        }
        restated = True
    return month, quadrant, allocs, restated



def append_entry(
    quadrant: Quadrant,
    today: date,
    path: Path = LEDGER_PATH,
    tlt_trend_up: bool | None = None,
    commodity_momentum: dict[str, float] | None = None,
    breadth: float | None = None,
    breadth_washout: bool | None = None,
    sp500_balance: dict | None = None,
    shadow_quadrant: str | None = None,
    managed_futures: dict[str, float] | None = None,
    fragility: dict | None = None,
) -> bool:
    """Append this month's row with resolved allocations. False if logged."""
    ledger = load_ledger(path)
    month = today.strftime("%Y-%m")
    if not ledger.empty and (ledger["month"] == month).any():
        logger.info(f"{month} already logged — nothing to do")
        return False
    allocs = {
        tier: resolve_allocation(tier, quadrant, tlt_trend_up, commodity_momentum,
                                 breadth_washout=breadth_washout)
        for tier in TIERS
    }
    shadow_delever = None
    if fragility and fragility.get("fragile"):
        shadow_delever = {tier: delever_one_notch(allocs[tier]) for tier in ("AGG", "VAGG")}
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
                "breadth": breadth,
                "breadth_washout": breadth_washout,
                "sp500_balance": sp500_balance,  # informational only
                "shadow_quadrant": shadow_quadrant,  # informational fast-entry classifier
                "managed_futures": managed_futures or {},  # informational watchlist (prior-month returns)
                "fragility": fragility,  # informational shadow (entry 70): ext / rvol20 / fragile
                "shadow_delever": shadow_delever,  # what AGG/VAGG would hold one notch down, if fragile
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
    signal_tickers = sorted({"SPY", "DBC", "TLT"} | {a for t in R_TILT.values() for a in t}
                            | set(BREADTH_TICKERS) | set(MANAGED_FUTURES_TICKERS))
    prices = {}
    for t in signal_tickers:
        try:
            prices[t] = fetch_yahoo_daily(t, "2y")
        except Exception as exc:  # noqa: BLE001 - a missing breadth name shouldn't kill the run
            if t in ("SPY", "DBC", "TLT"):
                raise
            logger.warning(f"{t}: fetch failed ({exc}) — continuing without it")
    sig = compute_signals(prices, today)
    quadrant = sig["quadrant"]
    logger.info(
        f"Quadrant in force for {today:%Y-%m}: {quadrant.name} "
        f"(tlt_up={sig['tlt_trend_up']}, breadth={sig['breadth']}, "
        f"washout={sig['breadth_washout']}, mom={sig['commodity_momentum']})"
    )
    if sig["shadow_quadrant"] and sig["shadow_quadrant"] != quadrant.name:
        logger.warning(
            f"SHADOW DISAGREES: fast-entry classifier says {sig['shadow_quadrant']} "
            f"vs primary {quadrant.name} — forward-evidence event, see PORTFOLIOS.md"
        )
    frag = sig.get("fragility") or {}
    if frag.get("fragile"):
        logger.warning(f"FRAGILE MONTH (shadow, informational): SPY {frag['ext']:+.1%} above its 10m line, "
                       f"20d vol {frag['rvol20']:.0%} — de-levered shadow book logged; live book unchanged")
    elif frag.get("ext") is not None:
        logger.info(f"Fragility shadow: ext {frag['ext']:+.1%}, 20d vol {frag['rvol20']:.0%} — not fragile")
    for tier in TIERS:
        logger.info(f"  {tier:>5} target: "
                    f"{resolve_allocation(tier, quadrant, sig['tlt_trend_up'], sig['commodity_momentum'], breadth_washout=sig['breadth_washout'])}")
    try:
        balance = fetch_sp500_balance(today)
    except Exception as exc:  # noqa: BLE001 - informational, never blocks the row
        logger.warning(f"S&P 500 quadrant balance failed: {exc}")
        balance = None
    if balance:
        logger.info(f"S&P 500 quadrant balance (informational): {balance}")
    append_entry(quadrant, today, path,
                 tlt_trend_up=sig["tlt_trend_up"],
                 commodity_momentum=sig["commodity_momentum"],
                 breadth=sig["breadth"],
                 breadth_washout=sig["breadth_washout"],
                 sp500_balance=balance,
                 shadow_quadrant=sig["shadow_quadrant"],
                 managed_futures=sig["managed_futures"],
                 fragility=sig.get("fragility"))

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

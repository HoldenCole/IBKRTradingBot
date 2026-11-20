"""QUADRANT BALANCES (trend & cycle state codes + member balances) — a FLAG, never an order.

Rebuilt 2026-11-21 from the user's Optuma workbook (the tool their former
desk called "trend and cycle / quadrant balances"). Reverse-engineered from
the chart-header codes and verified: all 18 S&P 500 and Nasdaq-100 codes in
the workbook (daily / weekly / monthly, 2026-08-21 and 2026-11-20) reproduce
exactly.

Two oscillators, on any bar size (daily, weekly, monthly — the in-progress
weekly or monthly bar counts, as in the workbook):

  CYCLE ("D", workbook series DAS / DAL):  SMA(5) - SMA(15) of the close
  TREND ("T", workbook series TPL):        Coppock curve, WMA10(ROC14 + ROC11)

Each oscillator is in one of four quadrants:

  Q1  below zero, rising    (recovering)
  Q2  above zero, rising    (advancing)
  Q3  above zero, falling   (rolling over)
  Q4  below zero, falling   (declining)

State code = Q CC NN:  quadrant, bars spent in that quadrant so far (01 = it
just began), bars spent on this side of zero. "D 40525" = cycle in Q4 for 5
bars, below zero for 25.

Quadrant Balances = the share of an index's MEMBERS in each quadrant, per
oscillator and bar size (workbook codes like SPX.DAL.W.Q4), plus Q1+Q2 (the
share that is rising).

MARKET FLAG (TESTS.md entries 84-85) — one reading from the three bar sizes:

  WASHOUT       >= 50% of members in monthly cycle Q4. S&P next 12 months
                +17% / +21% in the two eras; 2008 fired early (-28% first).
  BROKEN        index monthly cycle AND trend below zero. Regime exits in
                this state were real in both eras (S&P next month -0.1% / -0.4%).
  DETERIORATING one monthly oscillator below zero.
  INTACT        both monthly oscillators above zero; qualified by the weekly
                stage: decline EARLY (weeks 1-3: poor entries), decline MATURE
                (week 4+: the favourable window), or no weekly decline.

Tie-in to the regime classifier: when the classifier turns growth OFF while
the flag is INTACT, the exit was a whipsaw more often than not in both eras
(S&P next month +1.7% / +3.2%). The tested candidate — hold 25% of the
risk-on book alongside 75% of the defensive book in those months — raised
CAGR and Sortino in all eight tier-era cells and cost ~1pp of max drawdown
in the modern era (March 2020). It is a CANDIDATE: reported every run,
adopted only on the user's decision.

Nothing here feeds the ledger, the matrix, or any order.

    python3 -m src.portfolio.trend_cycle              # index state codes
    python3 -m src.portfolio.trend_cycle --members    # + S&P 500 quadrant balances (~5 min)
    python3 -m src.portfolio.trend_cycle --members --log   # also append paper/trend_cycle.csv
"""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

LOG_PATH = Path(__file__).resolve().parents[2] / "paper" / "trend_cycle.csv"
TIMEFRAMES = {"D": "daily", "W": "weekly", "M": "monthly"}
QUADRANT_NAMES = {1: "below zero, rising", 2: "above zero, rising",
                  3: "above zero, falling", 4: "below zero, falling"}
MEASURES = ("cycle", "trend")


def cycle(close: pd.Series) -> pd.Series:
    return close.rolling(5).mean() - close.rolling(15).mean()


def trend(close: pd.Series) -> pd.Series:
    """Coppock curve: 10-bar weighted MA of (14-bar ROC + 11-bar ROC), in %."""
    roc = (close.pct_change(14) + close.pct_change(11)) * 100
    w = np.arange(1, 11, dtype=float)
    return roc.rolling(10).apply(lambda v: float(np.dot(v, w) / w.sum()), raw=True)


OSCILLATORS = {"cycle": cycle, "trend": trend}


def to_bars(daily_close: pd.Series, tf: str) -> pd.Series:
    """Closing series at the bar size; the current partial week/month is kept."""
    if tf == "D":
        return daily_close
    return daily_close.resample({"W": "W-FRI", "M": "ME"}[tf]).last().dropna()


def quadrants(osc: pd.Series) -> pd.Series:
    """Quadrant (1-4) per bar; NaN where the oscillator or its change is undefined."""
    d = osc.diff()
    q = pd.Series(np.nan, index=osc.index)
    q[(osc <= 0) & (d > 0)] = 1
    q[(osc > 0) & (d > 0)] = 2
    q[(osc > 0) & (d <= 0)] = 3
    q[(osc <= 0) & (d <= 0)] = 4
    return q


@dataclass(frozen=True)
class State:
    quadrant: int
    in_quadrant: int      # consecutive bars in this quadrant, counting the current one
    on_side: int          # consecutive bars on this side of zero

    @property
    def code(self) -> str:
        return f"{self.quadrant}{min(self.in_quadrant, 99):02d}{min(self.on_side, 99):02d}"

    def describe(self, unit: str = "bars") -> str:
        return (f"Q{self.quadrant} ({QUADRANT_NAMES[self.quadrant]}) for {self.in_quadrant} {unit}; "
                f"{'above' if self.quadrant in (2, 3) else 'below'} zero for {self.on_side}")


def state(osc: pd.Series) -> State | None:
    q = quadrants(osc).dropna()
    if q.empty:
        return None
    qv = q.values
    side = np.isin(qv, (2, 3))
    cc = 1
    while cc < len(qv) and qv[-cc - 1] == qv[-1]:
        cc += 1
    nn = 1
    while nn < len(side) and side[-nn - 1] == side[-1]:
        nn += 1
    return State(int(qv[-1]), cc, nn)


def state_history(osc: pd.Series) -> pd.DataFrame:
    """Per-bar quadrant, bars-in-quadrant and bars-on-side (for research)."""
    q = quadrants(osc).dropna()
    side = q.isin([2, 3])
    in_q = q.groupby((q != q.shift()).cumsum()).cumcount() + 1
    on_side = side.groupby((side != side.shift()).cumsum()).cumcount() + 1
    return pd.DataFrame({"quadrant": q.astype(int), "in_quadrant": in_q, "on_side": on_side})


def index_states(daily_close: pd.Series) -> dict[str, dict[str, State | None]]:
    out: dict[str, dict[str, State | None]] = {}
    for tf in TIMEFRAMES:
        bars = to_bars(daily_close, tf)
        out[tf] = {m: state(fn(bars)) for m, fn in OSCILLATORS.items()}
    return out


def quadrant_balances(member_closes: dict[str, pd.Series], min_names: int = 50) -> dict | None:
    """{tf: {measure: {"q1".."q4": pct, "q1q2": pct, "n": count}}} over the members."""
    out: dict = {}
    for tf in TIMEFRAMES:
        out[tf] = {}
        for m, fn in OSCILLATORS.items():
            counts = {1: 0, 2: 0, 3: 0, 4: 0}
            for s in member_closes.values():
                st = state(fn(to_bars(s, tf)))
                if st is not None:
                    counts[st.quadrant] += 1
            n = sum(counts.values())
            if n < min_names:
                return None
            row = {f"q{k}": round(100 * v / n, 2) for k, v in counts.items()}
            row["q1q2"] = round(100 * (counts[1] + counts[2]) / n, 2)
            row["n"] = n
            out[tf][m] = row
    return out


# ---------- data (network) ----------
def fetch_close(symbol: str, rng: str = "5y") -> pd.Series:
    """UNADJUSTED (split-adjusted only) daily closes, as a price chart shows them."""
    from src.data.yahoo import _CHART, _closes, _get_json, _result

    url = f"{_CHART.format(symbol=symbol)}?range={rng}&interval=1d"
    return _closes(_result(_get_json(url), symbol), symbol, "1d", adjusted=False)


def fetch_bars(symbol: str, interval: str = "1mo", start: str = "1984-01-01") -> pd.Series:
    """UNADJUSTED closes at a native bar size over an explicit window (monthly bars are stamped at month end)."""
    from datetime import datetime, timezone

    from src.data.yahoo import _CHART, _closes, _get_json, _result

    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int(datetime.now(tz=timezone.utc).timestamp())
    url = f"{_CHART.format(symbol=symbol)}?period1={p1}&period2={p2}&interval={interval}"
    s = _closes(_result(_get_json(url), symbol), symbol, interval, adjusted=False)
    if interval == "1mo":
        s.index = s.index.to_period("M").to_timestamp("M")
        s = s[~s.index.duplicated(keep="last")]
    return s


def fetch_sp500_members() -> list[str]:
    import urllib.request

    from src.data.yahoo import _ssl_context
    from src.portfolio.paper_logger import SP500_MEMBERS_URL

    req = urllib.request.Request(SP500_MEMBERS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
        lines = resp.read().decode().splitlines()
    return [ln.split(",")[0].strip().replace(".", "-") for ln in lines[1:] if ln.strip()]


def fetch_member_closes(members: list[str], pause: float = 0.15) -> dict[str, pd.Series]:
    out = {}
    for sym in members:
        try:
            s = fetch_close(sym)
            if len(s) >= 300:
                out[sym] = s
        except Exception:  # noqa: BLE001 - individual members are expendable
            pass
        time.sleep(pause)
    return out


def log_row(out: dict, path: Path = LOG_PATH) -> dict:
    """One row per run: every index code, and the S&P 500 balances when computed."""
    row = {"date": out["asof"], "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for label, key in (("S&P 500", "spx"), ("Nasdaq-100", "ndx")):
        for tf in TIMEFRAMES:
            for m in MEASURES:
                st = out["indices"][label][tf][m]
                row[f"{key}_{tf}_{m}"] = st.code if st else ""
    bal = out.get("balances") or {}
    for tf in TIMEFRAMES:
        for m in MEASURES:
            r = (bal.get(tf) or {}).get(m) or {}
            for q in ("q1", "q2", "q3", "q4"):
                row[f"bal_{tf}_{m}_{q}"] = r.get(q, "")
    row["flag"] = (out.get("reading") or {}).get("flag", "")
    row["weekly_stage"] = (out.get("reading") or {}).get("weekly_stage", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields, existing = list(row), []
    if path.exists():
        with path.open() as fh:
            reader = csv.DictReader(fh)
            old_fields = reader.fieldnames or []
            existing = list(reader)
        if any(r.get("date") == row["date"] for r in existing):
            return row                      # one row per price date
        fields = list(old_fields) + [f for f in fields if f not in old_fields]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in existing:
            w.writerow({k: r.get(k, "") for k in fields})
        w.writerow({k: row.get(k, "") for k in fields})
    return row


WASHOUT_Q4 = 50.0          # % of members in monthly cycle Q4
EARLY_WEEKS = 3            # a weekly decline is "early" through this count


def market_flag(spx: dict, balances: dict | None) -> dict:
    """The quadrant-balance market flag from the S&P 500 states (and member balances when available)."""
    mc, mt = spx["M"]["cycle"], spx["M"]["trend"]
    wc, wt = spx["W"]["cycle"], spx["W"]["trend"]
    above = [st.quadrant in (2, 3) for st in (mc, mt)]
    m_q4 = ((balances or {}).get("M") or {}).get("cycle", {}).get("q4")
    declines = [st.in_quadrant for st in (wc, wt) if st.quadrant == 4]
    if not declines:
        stage = "no weekly decline"
    elif max(declines) <= EARLY_WEEKS:
        stage = "weekly decline EARLY"
    else:
        stage = "weekly decline MATURE"
    if m_q4 is not None and m_q4 >= WASHOUT_Q4:
        flag = "WASHOUT"
    elif not any(above):
        flag = "BROKEN"
    elif not all(above):
        flag = "DETERIORATING"
    else:
        flag = "INTACT"
    return {"flag": flag, "weekly_stage": stage, "monthly_above_zero": all(above), "monthly_q4_share": m_q4}


FLAG_TEXT = {
    "WASHOUT": "Monthly washout: at least half the index is in a monthly decline. Historically the best long-horizon entry "
               "(S&P +17% / +21% over the next 12 months in the two eras), but 2008 shows it can fire many months early.",
    "BROKEN": "Monthly trend broken: both monthly readings are below zero. Regime exits in this state were real in both eras.",
    "DETERIORATING": "Monthly trend deteriorating: one monthly reading is below zero.",
    "INTACT": "Monthly trend intact: both monthly readings are above zero.",
}
STAGE_TEXT = {
    "weekly decline EARLY": "The weekly decline is early (weeks 1-3), historically a poor entry point.",
    "weekly decline MATURE": "The weekly decline is mature (week 4 or later), historically the favourable entry window.",
    "no weekly decline": "No weekly decline is in force.",
}


def regime_growth_on() -> tuple[bool | None, bool | None]:
    """The classifier's two dials at the latest close (SPY and DBC vs their 10-month lines)."""
    from datetime import timedelta

    from src.data.yahoo import fetch_yahoo_daily
    from src.portfolio.watch import boundary
    try:
        spy, dbc = fetch_yahoo_daily("SPY", rng="2y"), fetch_yahoo_daily("DBC", rng="2y")
        after = (spy.index[-1] + timedelta(days=1)).date()
        return boundary(spy, after)[2] > 0, boundary(dbc, after)[2] > 0
    except Exception:  # noqa: BLE001
        return None, None


def print_reading(out: dict) -> dict:
    spx = out["indices"]["S&P 500"]; bal = out.get("balances")
    r = market_flag(spx, bal)
    growth_on, infl_on = regime_growth_on()
    r["classifier_growth_on"] = growth_on
    print(f"\nQUADRANT BALANCES FLAG: {r['flag']} — {r['weekly_stage']}")
    print(f"   {FLAG_TEXT[r['flag']]} {STAGE_TEXT[r['weekly_stage']]}")
    for tf, name in TIMEFRAMES.items():
        c, t = spx[tf]["cycle"], spx[tf]["trend"]
        line = f"   {name:8s} cycle {c.quadrant}-{c.in_quadrant:02d}-{c.on_side:02d}, trend {t.quadrant}-{t.in_quadrant:02d}-{t.on_side:02d}"
        if bal:
            line += (f"; members declining (Q4) {bal[tf]['cycle']['q4']:.0f}% cycle / {bal[tf]['trend']['q4']:.0f}% trend, "
                     f"rising (Q1+Q2) {bal[tf]['cycle']['q1q2']:.0f}% / {bal[tf]['trend']['q1q2']:.0f}%")
        print(line)
    if growth_on is not None:
        if growth_on and r["flag"] in ("INTACT", "DETERIORATING"):
            verdict = "Regime model: growth ON. Quadrant balances agree."
        elif growth_on:
            verdict = f"Regime model: growth ON, but quadrant balances read {r['flag']}."
        elif r["flag"] == "INTACT":
            verdict = ("DISAGREEMENT: the regime model has growth OFF while the monthly quadrant balances are intact. In both eras "
                       "these exits were whipsaws more often than not (S&P next month +1.7% / +3.2%). Candidate tie-in: hold 25% of "
                       "the risk-on book with 75% of the defensive book.")
        else:
            verdict = f"Regime model: growth OFF. Quadrant balances read {r['flag']} — they agree the exit is real."
        r["verdict"] = verdict
        print(f"   {verdict}")
    out["reading"] = r
    return r


def report(with_members: bool = False) -> dict:
    out: dict = {"indices": {}, "balances": None, "asof": None}
    for label, sym in (("S&P 500", "^GSPC"), ("Nasdaq-100", "^NDX")):
        close = fetch_close(sym, rng="10y")
        st = index_states(close)
        out["indices"][label] = st
        out["asof"] = close.index[-1].date().isoformat()
        print(f"{label}  (close {close.iloc[-1]:,.2f}, {close.index[-1].date()})")
        for tf, name in TIMEFRAMES.items():
            c, t = st[tf]["cycle"], st[tf]["trend"]
            print(f"   {name:8s} cycle D {c.code}  {c.describe()}")
            print(f"   {'':8s} trend T {t.code}  {t.describe()}")
    if with_members:
        closes = fetch_member_closes(fetch_sp500_members())
        bal = quadrant_balances(closes)
        out["balances"] = bal
        if bal:
            print(f"S&P 500 quadrant balances (% of {bal['D']['cycle']['n']} members):")
            for tf, name in TIMEFRAMES.items():
                for m in MEASURES:
                    r = bal[tf][m]
                    print(f"   {name:8s} {m:5s}  Q1 {r['q1']:5.1f}  Q2 {r['q2']:5.1f}  Q3 {r['q3']:5.1f}  Q4 {r['q4']:5.1f}   rising (Q1+Q2) {r['q1q2']:5.1f}")
    print_reading(out)
    return out


if __name__ == "__main__":
    result = report(with_members="--members" in sys.argv)
    if "--log" in sys.argv:
        log_row(result)
        print(f"logged to {LOG_PATH}")

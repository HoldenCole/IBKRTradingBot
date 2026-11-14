"""Paper log for the standalone swing account (TESTS.md entry 79).

A SEPARATE paper account from the rotation ledger: nothing here reads or
writes paper/ledger.csv, and nothing here trades. Rules, as tested:

  * instruments: SPY and QQQ, two slots of 50% each
  * entry (at the close): RSI(2) < 10 AND (close < lower Bollinger(20,2)
    OR close > 200-day SMA); most oversold first
  * gate: quadrant in force is GROWTH or REFLATION, and the S&P 500 is not
    in the fragile state (0-3% above its 200d SMA with 20d realized vol > 16%)
  * exit (at the close): first close above the 5-day SMA, or 10 trading days
  * cost: 5bp per side; 2x/3x marks use the real levered ETFs over the
    same dates (SSO/UPRO for SPY, QLD/TQQQ for QQQ)

Run once per trading day after the close:

    python3 -m src.portfolio.swing_logger            # log today's bar
    python3 -m src.portfolio.swing_logger --summary  # paper account to date

Idempotent: a bar date already in paper/swing_daily.csv is skipped.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from src.data.yahoo import fetch_yahoo_daily
from src.regime.quadrant import Quadrant, quadrant_series

ROOT = Path(__file__).resolve().parents[2]
TRADES_PATH = ROOT / "paper" / "swing_trades.csv"
DAILY_PATH = ROOT / "paper" / "swing_daily.csv"

SYMBOLS = ("SPY", "QQQ")
LEVERED = {"SPY": ("SSO", "UPRO"), "QQQ": ("QLD", "TQQQ")}
SLOTS = 2
RSI_MAX = 10.0
MAX_HOLD = 10
COST = 5 / 1e4                       # per side
FRAGILE_EXT = (0.0, 0.03)
FRAGILE_RVOL = 0.16
RISK_ON = (Quadrant.GROWTH, Quadrant.REFLATION)

TRADE_FIELDS = ["trade_id", "symbol", "entry_date", "entry_px", "trigger", "rsi2_at_entry",
                "quadrant_at_entry", "exit_date", "exit_px", "days", "exit_reason",
                "ret_1x", "ret_2x", "ret_3x"]


# ---------- indicators (same definitions as research/swing/lib.py) ----------
def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def indicators(close: pd.Series) -> dict:
    mid = close.rolling(20).mean()
    sd = close.rolling(20).std(ddof=0)
    lower, upper = mid - 2 * sd, mid + 2 * sd
    c = float(close.iloc[-1])
    out = {"close": c, "rsi2": float(rsi(close, 2).iloc[-1]),
           "pctb": float((c - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])),
           "below_band": bool(c < lower.iloc[-1]),
           "sma5": float(close.rolling(5).mean().iloc[-1]),
           "sma200": float(close.rolling(200).mean().iloc[-1])}
    out["above_200"] = bool(c > out["sma200"])
    out["vs200"] = c / out["sma200"] - 1
    out["entry_signal"] = bool(out["rsi2"] < RSI_MAX and (out["below_band"] or out["above_200"]))
    out["exit_signal"] = bool(c > out["sma5"])
    return out


def fragile_state(sp500: pd.Series) -> tuple[bool, float, float]:
    ext = float(sp500.iloc[-1] / sp500.rolling(200).mean().iloc[-1] - 1)
    rvol = float(sp500.pct_change().rolling(20).std().iloc[-1] * np.sqrt(252))
    return bool(FRAGILE_EXT[0] <= ext <= FRAGILE_EXT[1] and rvol > FRAGILE_RVOL), ext, rvol


def quadrant_in_force(spy: pd.Series, dbc: pd.Series, bar_date: pd.Timestamp) -> Quadrant | None:
    """Quadrant governing the month of `bar_date`: classified on data through
    the end of the PRIOR month (the rotation model's ex-ante rule)."""
    first = bar_date.replace(day=1)
    q = quadrant_series(spy[spy.index < first], dbc[dbc.index < first])
    return q.iloc[-1] if len(q) else None


# ---------- ledger files ----------
def load_trades(path: Path = TRADES_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def save_trades(rows: list[dict], path: Path = TRADES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TRADE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in TRADE_FIELDS})


def logged_dates(path: Path = DAILY_PATH) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as fh:
        return {r["date"] for r in csv.DictReader(fh)}


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


# ---------- the daily step (pure: prices in, decisions out) ----------
def step(prices: dict[str, pd.Series], sp500: pd.Series, quadrant: Quadrant | None,
         trades: list[dict]) -> tuple[list[dict], dict, list[str]]:
    """Apply one completed daily bar. `prices` holds adjusted closes for SPY,
    QQQ and the four levered ETFs, all ending on the same bar date."""
    bar = prices[SYMBOLS[0]].index[-1]
    ind = {s: indicators(prices[s]) for s in SYMBOLS}
    fragile, ext, rvol = fragile_state(sp500)
    gate_ok = quadrant in RISK_ON and not fragile
    actions: list[str] = []

    # exits first
    for t in trades:
        if t.get("exit_date"):
            continue
        s = t["symbol"]; px = prices[s]
        entry = pd.Timestamp(t["entry_date"])
        held = int((px.index > entry).sum())
        if held == 0:
            continue
        reason = "above_sma5" if ind[s]["exit_signal"] else "time_stop" if held >= MAX_HOLD else None
        if reason is None:
            continue
        def ret(sym: str) -> float:
            p = prices[sym]
            return float(p.iloc[-1] / p.loc[entry] - 1 - 2 * COST)
        t.update(exit_date=bar.date().isoformat(), exit_px=round(ind[s]["close"], 4), days=held,
                 exit_reason=reason, ret_1x=round(ret(s), 5),
                 ret_2x=round(ret(LEVERED[s][0]), 5), ret_3x=round(ret(LEVERED[s][1]), 5))
        actions.append(f"EXIT {s} {reason} {float(t['ret_1x']):+.2%} after {held}d")

    # entries
    open_syms = {t["symbol"] for t in trades if not t.get("exit_date")}
    free = SLOTS - len(open_syms)
    if gate_ok and free > 0:
        cands = sorted((s for s in SYMBOLS if ind[s]["entry_signal"] and s not in open_syms),
                       key=lambda s: ind[s]["rsi2"])
        for s in cands[:free]:
            trades.append({"trade_id": len(trades) + 1, "symbol": s, "entry_date": bar.date().isoformat(),
                           "entry_px": round(ind[s]["close"], 4),
                           "trigger": "band" if ind[s]["below_band"] else "trend_pullback",
                           "rsi2_at_entry": round(ind[s]["rsi2"], 2),
                           "quadrant_at_entry": quadrant.name if quadrant else ""})
            actions.append(f"ENTER {s} at {ind[s]['close']:.2f} (RSI2 {ind[s]['rsi2']:.1f})")
    blocked = [s for s in SYMBOLS if ind[s]["entry_signal"] and s not in open_syms] if not gate_ok else []
    if blocked:
        why = "fragile state" if fragile else f"quadrant {quadrant.name if quadrant else 'unknown'}"
        actions.append(f"BLOCKED {'+'.join(blocked)} ({why})")

    row = {"date": bar.date().isoformat(),
           "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "quadrant": quadrant.name if quadrant else "", "fragile": fragile, "gate_ok": gate_ok,
           "sp_ext200": round(ext, 4), "sp_rvol20": round(rvol, 4)}
    for s in SYMBOLS:
        row.update({f"{s.lower()}_close": round(ind[s]["close"], 4), f"{s.lower()}_rsi2": round(ind[s]["rsi2"], 2),
                    f"{s.lower()}_pctb": round(ind[s]["pctb"], 3), f"{s.lower()}_vs200": round(ind[s]["vs200"], 4),
                    f"{s.lower()}_signal": ind[s]["entry_signal"]})
    row["open_positions"] = "+".join(sorted(t["symbol"] for t in trades if not t.get("exit_date")))
    row["actions"] = "; ".join(actions)
    return trades, row, actions


def account_curve(trades: list[dict]) -> dict:
    """Compound closed trades at 50% of the account each (sequential approximation)."""
    out = {}
    for lev in ("1x", "2x", "3x"):
        eq = 1.0
        for t in trades:
            if t.get("exit_date"):
                eq *= 1 + float(t[f"ret_{lev}"]) / SLOTS
        out[lev] = eq - 1
    return out


def summary(trades: list[dict] | None = None) -> str:
    trades = load_trades() if trades is None else trades
    closed = [t for t in trades if t.get("exit_date")]
    open_ = [t for t in trades if not t.get("exit_date")]
    lines = [f"Swing paper account: {len(closed)} closed trades, {len(open_)} open"]
    if closed:
        r = np.array([float(t["ret_1x"]) for t in closed])
        acc = account_curve(trades)
        lines.append(f"  per trade: mean {r.mean():+.2%}, win {(r > 0).mean():.0%}, worst {r.min():+.2%}")
        lines.append(f"  account since start: 1x {acc['1x']:+.2%}  2x {acc['2x']:+.2%}  3x {acc['3x']:+.2%} "
                     "(excludes T-bill interest on idle cash)")
    for t in open_:
        lines.append(f"  open: {t['symbol']} since {t['entry_date']} at {t['entry_px']}")
    return "\n".join(lines)


def run() -> list[str]:
    need = list(SYMBOLS) + [x for pair in LEVERED.values() for x in pair]
    prices = {s: fetch_yahoo_daily(s, rng="2y") for s in need}
    sp500 = fetch_yahoo_daily("^GSPC", rng="2y")
    dbc = fetch_yahoo_daily("DBC", rng="2y")
    bar = prices["SPY"].index[-1]
    if any(p.index[-1] != bar for p in prices.values()) or sp500.index[-1] != bar:
        raise RuntimeError("price series end on different dates — rerun after the close")
    if bar.date().isoformat() in logged_dates():
        logger.info(f"{bar.date()} already logged — nothing to do")
        return []
    quadrant = quadrant_in_force(prices["SPY"], dbc, bar)
    trades, row, actions = step(prices, sp500, quadrant, load_trades())
    save_trades(trades)
    _append(DAILY_PATH, row)
    logger.info(f"{row['date']} · {row['quadrant']} · gate {'OPEN' if row['gate_ok'] else 'CLOSED'}"
                f"{' (fragile)' if row['fragile'] else ''} · S&P {row['sp_ext200']:+.1%} vs 200d, vol {row['sp_rvol20']:.0%}")
    for s in SYMBOLS:
        k = s.lower()
        logger.info(f"  {s}: RSI2 {row[k + '_rsi2']:.1f}, %B {row[k + '_pctb']:.2f}, {row[k + '_vs200']:+.1%} vs 200d"
                    f"{' — ENTRY SIGNAL' if row[k + '_signal'] else ''}")
    for a in actions:
        logger.info(f"  {a}")
    if not actions:
        logger.info("  no action")
    return actions


if __name__ == "__main__":
    if "--summary" in sys.argv:
        print(summary())
    else:
        run()
        print(summary())

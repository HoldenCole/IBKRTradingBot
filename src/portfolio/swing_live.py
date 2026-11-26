"""Live swing account at 3x (TESTS.md entries 79 and 89).

A small, separate IBKR cash account that follows the paper swing rules with
real money: same signals as src/portfolio/swing_logger.py (SPY and QQQ dip
buys, two slots, regime gate, exit above the 5-day average or after 10 days),
held through the leveraged funds (3x: UPRO for SPY, TQQQ for QQQ). It never
opens and closes a position on the same day, so the day-trading rule never
applies. Nothing here sends orders: it tells the user what to place.

Files (append-only except the account config):
  paper/swing_live_account.json   leverage, funds, deposits, commission
  paper/swing_live_orders.csv     orders issued before each close
  paper/swing_live_trades.csv     positions, with fills (assumed at the official
                                  close until the user confirms the real fill)

Commands:
  python3 -m src.portfolio.swing_live --preclose     # ~15:40 New York: orders to place at today's close
  python3 -m src.portfolio.swing_live --settle       # after the close: book today's orders at the closing price
  python3 -m src.portfolio.swing_live --fill 2026-12-03 BUY UPRO 4 117.12   # record the real fill
  python3 -m src.portfolio.swing_live --deposit 2026-12-01 1000
  python3 -m src.portfolio.swing_live --status
"""
from __future__ import annotations

import copy
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.yahoo import fetch_yahoo_daily
from src.portfolio import swing_logger as sl

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "paper" / "swing_live_account.json"
ORDERS = ROOT / "paper" / "swing_live_orders.csv"
TRADES = ROOT / "paper" / "swing_live_trades.csv"
NY = ZoneInfo("America/New_York")

DEFAULT_CONFIG = {"leverage": 3, "funds": {"SPY": "UPRO", "QQQ": "TQQQ"}, "commission_per_order": 0.35,
                  "slots": 2, "deposits": [], "notes": "IBKR cash account; whole shares; market-on-close orders"}
ORDER_FIELDS = ["date", "issued_at", "side", "fund", "signal", "shares", "ref_price", "reason", "trade_id"]
TRADE_FIELDS = ["trade_id", "signal", "fund", "entry_date", "shares", "entry_px", "entry_source",
                "exit_date", "exit_px", "exit_source", "exit_reason", "commission", "pnl"]


# ---------------------------------------------------------------- files
def load_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=1) + "\n")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- accounting
def equity(cfg: dict, trades: list[dict], marks: dict[str, float]) -> dict:
    deposits = sum(float(d["amount"]) for d in cfg["deposits"])
    cash, value = deposits, 0.0
    for t in trades:
        sh = float(t["shares"])
        cash -= sh * float(t["entry_px"])
        cash -= float(t["commission"] or 0)
        if t.get("exit_date"):
            cash += sh * float(t["exit_px"])
        else:
            value += sh * marks.get(t["fund"], float(t["entry_px"]))
    eq = cash + value
    realized = sum(float(t["pnl"]) for t in trades if t.get("exit_date") and t.get("pnl") not in (None, ""))
    return {"deposits": deposits, "cash": cash, "positions": value, "equity": eq,
            "gain": eq - deposits, "realized": realized}


# ---------------------------------------------------------------- pre-close orders
def _paper_view(trades: list[dict]) -> list[dict]:
    """Open live positions in the paper logger's format so its step() can be reused."""
    return [{"symbol": t["signal"], "entry_date": t["entry_date"], "exit_date": ""}
            for t in trades if not t.get("exit_date")]


def plan_orders(prices: dict[str, pd.Series], sp500: pd.Series, quadrant, cfg: dict,
                trades: list[dict], fund_px: dict[str, float], eq: float) -> list[dict]:
    """Orders to place at today's close, from the same rules as the paper account."""
    view = _paper_view(trades)
    n_open = len(view)
    after, _row, actions = sl.step(prices, sp500, quadrant, copy.deepcopy(view))
    orders = []
    for t in after[:n_open]:
        if t.get("exit_date"):
            live = next(x for x in trades if not x.get("exit_date") and x["signal"] == t["symbol"])
            orders.append({"side": "SELL", "fund": live["fund"], "signal": t["symbol"], "shares": live["shares"],
                           "ref_price": round(fund_px[live["fund"]], 2), "reason": t["exit_reason"],
                           "trade_id": live["trade_id"]})
    slot_cash = eq / cfg["slots"]
    for t in after[n_open:]:
        fund = cfg["funds"][t["symbol"]]
        px = fund_px[fund]
        shares = math.floor(slot_cash / px)
        if shares < 1:
            continue
        orders.append({"side": "BUY", "fund": fund, "signal": t["symbol"], "shares": shares,
                       "ref_price": round(px, 2), "reason": f"{t['trigger']} RSI2 {t['rsi2_at_entry']}", "trade_id": ""})
    blocked = [a for a in actions if a.startswith("BLOCKED")]
    for b in blocked:
        orders.append({"side": "NONE", "fund": "", "signal": "", "shares": 0, "ref_price": 0, "reason": b, "trade_id": ""})
    return orders


def _live_prices():
    need = list(sl.SYMBOLS)
    prices = {s: fetch_yahoo_daily(s, rng="2y") for s in need}
    sp500 = fetch_yahoo_daily("^GSPC", rng="2y")
    dbc = fetch_yahoo_daily("DBC", rng="2y")
    return prices, sp500, dbc


def _raw_last(symbol: str) -> tuple[pd.Timestamp, float]:
    from src.portfolio.trend_cycle import fetch_close
    s = fetch_close(symbol, rng="1mo")
    return s.index[-1], float(s.iloc[-1])


def preclose() -> list[dict]:
    cfg = load_config()
    if not cfg["deposits"]:
        print("Live swing account not funded yet: no orders.")
        return []
    today = datetime.now(NY).date()
    prices, sp500, dbc = _live_prices()
    if any(p.index[-1].date() != today for p in prices.values()) or sp500.index[-1].date() != today:
        print("Market closed today or prices not live yet: no orders.")
        return []
    if any(r["date"] == today.isoformat() for r in _read(ORDERS)):
        print(f"Orders for {today} were already issued.")
        return []
    trades = _read(TRADES)
    fund_px = {}
    for f in cfg["funds"].values():
        d, px = _raw_last(f)
        fund_px[f] = px
    eq = equity(cfg, trades, fund_px)["equity"]
    quadrant = sl.quadrant_in_force(prices["SPY"], dbc, prices["SPY"].index[-1])
    orders = plan_orders(prices, sp500, quadrant, cfg, trades, fund_px, eq)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = _read(ORDERS) + [{"date": today.isoformat(), "issued_at": stamp, **o} for o in orders]
    _write(ORDERS, rows, ORDER_FIELDS)
    real = [o for o in orders if o["side"] in ("BUY", "SELL")]
    if not real:
        print("No orders today." + (" " + "; ".join(o["reason"] for o in orders) if orders else ""))
    for o in real:
        print(f"{o['side']} {o['shares']} {o['fund']} market-on-close (ref {o['ref_price']:.2f}; {o['reason']})")
    return orders


# ---------------------------------------------------------------- after the close
def settle(day: str | None = None) -> list[str]:
    """Book the day's orders at the official close unless a confirmed fill already exists."""
    cfg = load_config()
    day = day or datetime.now(NY).date().isoformat()
    orders = [o for o in _read(ORDERS) if o["date"] == day and o["side"] in ("BUY", "SELL")]
    trades = _read(TRADES)
    done = []
    for o in orders:
        d, close = _raw_last(o["fund"])
        if d.date().isoformat() != day:
            raise RuntimeError(f"{o['fund']}: no closing price for {day} yet")
        comm = cfg["commission_per_order"]
        if o["side"] == "BUY":
            if any(t["entry_date"] == day and t["fund"] == o["fund"] for t in trades):
                continue
            trades.append({"trade_id": str(len(trades) + 1), "signal": o["signal"], "fund": o["fund"],
                           "entry_date": day, "shares": o["shares"], "entry_px": round(close, 4),
                           "entry_source": "close", "exit_date": "", "exit_px": "", "exit_source": "",
                           "exit_reason": "", "commission": comm, "pnl": ""})
            done.append(f"bought {o['shares']} {o['fund']} at {close:.2f}")
        else:
            t = next((t for t in trades if t["trade_id"] == o["trade_id"]), None)
            if t is None or t.get("exit_date"):
                continue
            t.update(exit_date=day, exit_px=round(close, 4), exit_source="close", exit_reason=o["reason"],
                     commission=float(t["commission"]) + comm)
            t["pnl"] = round(float(t["shares"]) * (float(t["exit_px"]) - float(t["entry_px"])) - float(t["commission"]), 2)
            done.append(f"sold {t['shares']} {o['fund']} at {close:.2f}, P&L {float(t['pnl']):+.2f}")
    _write(TRADES, trades, TRADE_FIELDS)
    return done


def record_fill(day: str, side: str, fund: str, shares: str, price: str) -> None:
    trades = _read(TRADES)
    side = side.upper()
    if side == "BUY":
        t = next((t for t in trades if t["entry_date"] == day and t["fund"] == fund), None)
        if t is None:
            raise SystemExit(f"no BUY of {fund} booked on {day}; run --settle first")
        t.update(shares=shares, entry_px=price, entry_source="confirmed")
    else:
        t = next((t for t in trades if t["exit_date"] == day and t["fund"] == fund), None)
        if t is None:
            raise SystemExit(f"no SELL of {fund} booked on {day}; run --settle first")
        t.update(exit_px=price, exit_source="confirmed")
    if t.get("exit_date"):
        t["pnl"] = round(float(t["shares"]) * (float(t["exit_px"]) - float(t["entry_px"])) - float(t["commission"]), 2)
    _write(TRADES, trades, TRADE_FIELDS)


def status() -> str:
    cfg = load_config()
    trades = _read(TRADES)
    marks = {}
    for t in trades:
        if not t.get("exit_date") and t["fund"] not in marks:
            marks[t["fund"]] = _raw_last(t["fund"])[1]
    e = equity(cfg, trades, marks)
    closed = [t for t in trades if t.get("exit_date")]
    lines = [f"Live swing account ({cfg['leverage']}x): deposits ${e['deposits']:,.2f}, equity ${e['equity']:,.2f}, "
             f"gain ${e['gain']:+,.2f}; cash ${e['cash']:,.2f}, positions ${e['positions']:,.2f}",
             f"  closed trades {len(closed)}, realized ${e['realized']:+,.2f}"]
    for t in trades:
        if not t.get("exit_date"):
            lines.append(f"  open: {t['shares']} {t['fund']} since {t['entry_date']} at {float(t['entry_px']):.2f} "
                         f"({t['entry_source']}), now {marks[t['fund']]:.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--preclose" in a:
        preclose()
    elif "--settle" in a:
        for line in settle() or ["nothing to settle"]:
            print(line)
        print(status())
    elif "--fill" in a:
        i = a.index("--fill")
        record_fill(*a[i + 1:i + 6])
        print(status())
    elif "--deposit" in a:
        i = a.index("--deposit")
        cfg = load_config()
        cfg["deposits"].append({"date": a[i + 1], "amount": float(a[i + 2])})
        save_config(cfg)
        print(status())
    else:
        print(status())

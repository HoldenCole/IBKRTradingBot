"""Entry 86 — the November 2026 sell-off, reconstructed.

What did Quadrant Balances say on each day going in, and what did every
other logged model say at its last checkpoint? Ex-ante throughout: each
row uses closes through that day only (partial week and month included,
as the tool itself does).
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.data import fetch_ohlc  # noqa: E402
from src.portfolio import trend_cycle as tc  # noqa: E402

CACHE = ROOT / "research" / "cache"


def spx_long() -> pd.Series:
    f = CACHE / "qb_index_GSPC_1950.pkl"
    if f.exists():
        s = pickle.load(open(f, "rb"))
        if s.index[-1] >= pd.Timestamp("2026-11-20"):
            return s
    s = fetch_ohlc("^GSPC", start="1950-01-01")["raw_close"]
    pickle.dump(s, open(f, "wb"))
    return s


def code(st) -> str:
    return f"{st.quadrant}-{st.in_quadrant:02d}-{st.on_side:02d}"


def timeline(close: pd.Series, members: dict[str, pd.Series], start: str) -> pd.DataFrame:
    rows = []
    days = close.index[close.index >= start]
    for d in days:
        c = close.loc[:d]
        st = tc.index_states(c)
        bal = tc.quadrant_balances({k: v.loc[:d] for k, v in members.items() if len(v.loc[:d]) > 300})
        row = {"close": c.iloc[-1], "off_high": c.iloc[-1] / c.iloc[-260:].max() - 1}
        for tf in "DWM":
            row[f"{tf}_cyc"] = code(st[tf]["cycle"]); row[f"{tf}_trd"] = code(st[tf]["trend"])
            row[f"{tf}_cq4"] = bal[tf]["cycle"]["q4"]; row[f"{tf}_tq4"] = bal[tf]["trend"]["q4"]
            row[f"{tf}_cup"] = bal[tf]["cycle"]["q1q2"]; row[f"{tf}_tup"] = bal[tf]["trend"]["q1q2"]
            row[f"{tf}_cq3"] = bal[tf]["cycle"]["q3"]; row[f"{tf}_tq3"] = bal[tf]["trend"]["q3"]
        row["flag"] = tc.market_flag(st, bal)["flag"]
        rows.append(pd.Series(row, name=d))
    return pd.DataFrame(rows)


def main():
    close = spx_long()
    members = pickle.load(open(CACHE / "report_members_1d.pkl", "rb"))
    print(f"S&P 500 {close.index[0].date()} -> {close.index[-1].date()}; members {len(members)}")
    hi = close.loc["2026-01-01":]
    print(f"2026 closing high {hi.max():,.0f} on {hi.idxmax().date()}; last {close.iloc[-1]:,.0f} ({close.iloc[-1] / hi.max() - 1:+.1%})")
    tl = timeline(close, members, "2026-08-24")
    tl.to_pickle(CACHE / "qb_selloff_timeline.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    show = tl.copy()
    show["close"] = show["close"].round(0); show["off_high"] = (show["off_high"] * 100).round(1)
    for c in show.columns:
        if c.endswith(("q4", "up", "q3")):
            show[c] = show[c].round(0)
    print("\nINDEX CODES (S&P 500)")
    print(show[["close", "off_high", "D_cyc", "D_trd", "W_cyc", "W_trd", "M_cyc", "M_trd", "flag"]].to_string())
    print("\nMEMBER BALANCES: % in Q4 (declining) and % rising (Q1+Q2), cycle / trend")
    print(show[["close", "D_cq4", "D_tq4", "D_cup", "D_tup", "W_cq4", "W_tq4", "W_cup", "W_tup", "M_cq4", "M_tq4", "M_cup", "M_tup", "M_cq3", "M_tq3"]].to_string())


if __name__ == "__main__":
    main()

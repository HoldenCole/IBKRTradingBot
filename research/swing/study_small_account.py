"""Entry 89 — the swing accounts at a $1,000 starting balance.

User: fund a separate IBKR account with $1,000 to test strategies; milestones
of $50, $100, then $200 a month in gains. IBKR still applies the $25,000
pattern-day-trader rule to this user, so only strategies that never open and
close the same position on one day are considered. Both swing designs qualify:
entries at a close, exits at a later close (test 79 and test 82).

Small-account cost model (IBKR Pro tiered, US ETFs, fractional shares):
  commission $0.35 minimum per order (shares x $0.0035 is below it at this
  size), so cost per side = $0.35 / slot value + spread and fees
  (1 bp for SPY/QQQ, 2 bp for the 2x/3x funds and the commodity ETFs).
  With two slots on $1,000 the slot is $500, so commission is 7 bp per side.
  Costs are charged on the fund actually bought, so for 2x/3x they are NOT
  multiplied by the leverage.
Leverage is modelled as in tests 79 and 82: N x the daily return minus
(N-1) x (T-bill + 1%) financing and 0.95% expense on the invested share.

    python3 -m research.swing.study_small_account
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing import study_selloff_account as v2
from research.swing.data import load
from research.swing.lib import daily_features, perf
from research.swing.study_standalone import account, run

START_BALANCE = 1000.0
SLOTS = 2
COMMISSION = 0.35
MILESTONES = (50, 100, 200)
CONTRIBUTIONS = (0, 100, 250, 500)


def cost_bps(balance: float, spread_bps: float) -> float:
    return COMMISSION / (balance / SLOTS) * 1e4 + spread_bps


def monthly(a: pd.Series) -> pd.Series:
    return (1 + a).groupby(a.index.to_period("M")).prod() - 1


def describe(lab: str, a: pd.Series, out: pd.DataFrame, tr: pd.DataFrame) -> dict:
    p = perf(a)
    m = monthly(a)
    invested = out["expo"].groupby(out.index.to_period("M")).max() > 0
    y12 = (1 + m).rolling(12).apply(np.prod, raw=True) - 1
    d = {"design": lab, "CAGR": p["CAGR"], "maxDD": p["maxDD"], "Sharpe": p["Sharpe"],
         "trades_per_year": len(tr) / (len(out) / 252), "months_with_a_position": invested.mean(),
         "months_up": (m > 0.0005).mean(), "months_down": (m < -0.0005).mean(),
         "avg_month": m.mean(), "median_month": m.median(), "worst_month": m.min(), "best_month": m.max(),
         "p05_month": m.quantile(0.05), "y12_p05": y12.quantile(0.05), "y12_median": y12.median(),
         "y12_negative": (y12 < 0).mean(),
         "first_year_avg_$": START_BALANCE * m.mean(), "first_year_worst_month_$": START_BALANCE * m.min()}
    return d


def milestone_months(cagr: float, contrib: float, target: float, start: float = START_BALANCE, cap: int = 600):
    g = (1 + cagr) ** (1 / 12) - 1
    bal = start
    for k in range(1, cap + 1):
        if bal * g >= target:
            return k - 1, bal
        bal = bal * (1 + g) + contrib
    return None, bal


def main():
    data = load()
    feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    rows, curves = [], {}
    for entry in ("close", "open"):
        for lev in (1, 2, 3):
            c = cost_bps(START_BALANCE, 1.0 if lev == 1 else 2.0) / lev    # charged on the fund bought, not the leveraged exposure
            out, tr = run(data, feats, "UNION", ["SPY", "QQQ"], SLOTS, "aligned+nofragile", cost_bps=c, entry=entry)
            a = account(out, rf, lev)
            lab = f"Dip-buy SPY/QQQ (test 79), {lev}x, entry at {'the close' if entry == 'close' else 'next open'}"
            rows.append(describe(lab, a, out, tr)); curves[lab] = a
    for lev in (1, 2):
        c = cost_bps(START_BALANCE, 2.0) / lev / 1e4
        out, tr = v2.run(data, feats, v2.MODEL, "e79+z5line", 2, True, cost=c)
        a = v2.account(out, rf, lev)
        lab = f"Dip-buy + sell-off bounces (test 82), {lev}x" + (" (not every leg has a 2x fund)" if lev == 2 else "")
        rows.append(describe(lab, a, out, tr)); curves[lab] = a
    spy = data["SPY"]["close"].pct_change().reindex(feats.index[feats.index >= "1999-06-01"]).fillna(0.0)
    o = pd.DataFrame({"expo": 1.0}, index=spy.index)
    rows.append(describe("SPY buy and hold (reference)", spy, o, pd.DataFrame(index=range(1))))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    show = df.copy()
    for c in show.columns:
        if c not in ("design", "trades_per_year") and not c.endswith("_$"):
            show[c] = (show[c] * 100).round(1)
    show["trades_per_year"] = show["trades_per_year"].round(0)
    for c in ("first_year_avg_$", "first_year_worst_month_$"):
        show[c] = show[c].round(0)
    print(f"Cost per side at $1,000 (two $500 slots): SPY/QQQ {cost_bps(1000, 1):.0f} bp, 2x/3x funds {cost_bps(1000, 2):.0f} bp "
          f"(vs 5 bp in tests 79 and 82). At $5,000: {cost_bps(5000, 2):.1f} bp.\n")
    print("=== 1. 1999-2026, percent figures; $ columns are for a $1,000 balance ===")
    print(show.to_string(index=False))

    print("\n=== 2. Balance needed for each milestone (expected monthly gain = balance x CAGR / 12) ===")
    for _, r in df.iterrows():
        if "next open" in r["design"] or "reference" in r["design"]:
            continue
        need = {f"${m}/mo": f"${12 * m / r['CAGR']:,.0f}" for m in MILESTONES}
        print(f"   {r['design'][:66]:66s} CAGR {r['CAGR']:+.1%}  " + "  ".join(f"{k} needs {v}" for k, v in need.items()))

    print("\n=== 3. Months from a $1,000 start until the EXPECTED monthly gain reaches each milestone ===")
    for _, r in df.iterrows():
        if "next open" in r["design"] or "reference" in r["design"]:
            continue
        cells = []
        for c in CONTRIBUTIONS:
            parts = []
            for m in MILESTONES:
                k, bal = milestone_months(r["CAGR"], c, m)
                parts.append("never" if k is None else f"{k / 12:.1f}y")
            cells.append(f"+${c}/mo: " + "/".join(parts))
        print(f"   {r['design'][:66]:66s} " + " | ".join(cells))
    print("   (each cell: years to $50 / $100 / $200 a month; 'never' = not within 50 years)")

    print("\n=== 4. How lumpy: share of calendar months with a gain of at least $50 / $100 / $200, by balance ===")
    for lab in [k for k in curves if "next open" not in k]:
        m = monthly(curves[lab])
        cells = []
        for bal in (1000, 5000, 10000, 25000):
            cells.append(f"${bal:,}: " + "/".join(f"{(m * bal >= x).mean():.0%}" for x in MILESTONES))
        print(f"   {lab[:66]:66s} " + " | ".join(cells))

    print("\n=== 5. Recent years, test 79 at 1x and 3x and test 82 at 1x: calendar-year return ===")
    keys = [k for k in curves if ("1x" in k or "3x" in k) and "next open" not in k and "2x" not in k]
    y = pd.DataFrame({k[:40]: (1 + curves[k]).groupby(curves[k].index.year).prod() - 1 for k in keys})
    print((y.loc[2015:] * 100).round(1).to_string())
    df.to_csv("research/swing/small_account_results.csv", index=False)


if __name__ == "__main__":
    main()

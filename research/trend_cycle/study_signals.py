"""Entry 87 — when does Quadrant Balances say buy, and when does it say sell?

S&P 500 index states on weekly and monthly bars, 1950-2026. Three eras:
1950-1986 (extra, price only), 1987-2006 and 2007-2026 (the house eras).

  A. every quadrant transition as an event: forward return, hit rate, heat
  B. turning points: how each signal lines up with the actual major lows and
     highs (zigzag on daily closes: 20% = multi-year, 10% = intra-year)
  C. long/flat rules built from the states, against buy-and-hold and the
     10-month rule (total return from 1987: index fund + T-bills when out)
  D. member-balance signals on monthly bars (today's constituents)

All signals are read at the close of a COMPLETED bar and acted on from that close.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.portfolio import trend_cycle as tc  # noqa: E402

CACHE = ROOT / "research" / "cache"
ERAS = {"1950-86": ("1950-01-01", "1986-12-31"), "1987-2006": ("1987-01-01", "2006-12-31"), "2007-2026": ("2007-01-01", "2026-12-31")}
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)


def load():
    close = pickle.load(open(CACHE / "qb_index_GSPC_1950.pkl", "rb"))
    vf = pd.read_csv(CACHE / "long_VFINX.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    irx = pd.read_csv(CACHE / "long_IRX.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
    return close, vf, irx


def states(bars: pd.Series) -> pd.DataFrame:
    c, t = tc.state_history(tc.cycle(bars)), tc.state_history(tc.trend(bars))
    df = pd.DataFrame({"px": bars, "cq": c["quadrant"], "cc": c["in_quadrant"], "cn": c["on_side"],
                       "tq": t["quadrant"], "tcn": t["in_quadrant"], "tn": t["on_side"]}).dropna()
    for o in ("cq", "tq"):
        df[o + "_prev"] = df[o].shift(1)
    df["cn_prev"] = df["cn"].shift(1); df["tn_prev"] = df["tn"].shift(1)
    df["cc_prev"] = df["cc"].shift(1); df["tcn_prev"] = df["tcn"].shift(1)
    return df


def events(df: pd.DataFrame, tf: str) -> dict[str, pd.Series]:
    long_side = {"W": 26, "M": 12}[tf]; deep = {"W": 6, "M": 4}[tf]
    ent = lambda o, q: (df[o] == q) & (df[o + "_prev"] != q)  # noqa: E731
    c_up, t_up = df["cq"].isin([1, 2]), df["tq"].isin([1, 2])
    both_up = c_up & t_up; both_dn = ~c_up & ~t_up
    below2 = df["cq"].isin([1, 4]) & df["tq"].isin([1, 4])
    ev = {
        "BUY  cycle turns up below zero (->Q1)": ent("cq", 1),
        "BUY  trend turns up below zero (->Q1)": ent("tq", 1),
        f"BUY  trend ->Q1 after {deep}+ bars declining": ent("tq", 1) & (df["tcn_prev"] >= deep),
        f"BUY  trend ->Q1 after <{deep} bars declining": ent("tq", 1) & (df["tcn_prev"] < deep),
        "BUY  both rising, first bar, trend still below zero": both_up & ~both_up.shift(1, fill_value=False) & df["tq"].eq(1),
        "BUY  cycle crosses above zero (->Q2)": ent("cq", 2) & df["cq_prev"].isin([1, 4]),
        "BUY  trend crosses above zero (->Q2)": ent("tq", 2) & df["tq_prev"].isin([1, 4]),
        "SELL cycle rolls over above zero (->Q3)": ent("cq", 3),
        "SELL trend rolls over above zero (->Q3)": ent("tq", 3),
        f"SELL trend ->Q3 after {long_side}+ bars above zero": ent("tq", 3) & (df["tn"] >= long_side),
        f"SELL trend ->Q3 after <{long_side} bars above zero": ent("tq", 3) & (df["tn"] < long_side),
        "SELL both falling above zero, first bar (both Q3)": (df["cq"].eq(3) & df["tq"].eq(3)) & ~(df["cq"].eq(3) & df["tq"].eq(3)).shift(1, fill_value=False),
        "SELL cycle crosses below zero (->Q4)": ent("cq", 4) & df["cq_prev"].isin([2, 3]),
        "SELL trend crosses below zero (->Q4)": ent("tq", 4) & df["tq_prev"].isin([2, 3]),
        "SELL both below zero and falling, first bar": (df["cq"].eq(4) & df["tq"].eq(4)) & ~(df["cq"].eq(4) & df["tq"].eq(4)).shift(1, fill_value=False),
        "SELL both below zero, first bar (BROKEN)": below2 & ~below2.shift(1, fill_value=False),
    }
    return {k: v.fillna(False) for k, v in ev.items()}


def event_table(df: pd.DataFrame, ev: dict, tf: str):
    hz = {"W": (4, 13, 26, 52), "M": (3, 6, 12, 24)}[tf]; u = {"W": "w", "M": "m"}[tf]
    px = df["px"]
    fwd = {h: px.shift(-h) / px - 1 for h in hz}
    main_h = hz[2]
    heat = pd.Series([px.iloc[i:i + main_h + 1].min() / px.iloc[i] - 1 for i in range(len(px))], index=px.index)
    run = pd.Series([px.iloc[i:i + main_h + 1].max() / px.iloc[i] - 1 for i in range(len(px))], index=px.index)
    print(f"\n=== A. {tf} transitions: mean forward S&P 500 return, share higher at {main_h}{u}, average worst point and best point within {main_h}{u} ===")
    def line(lab, mask):
        cells = []
        for era, (a, b) in ERAS.items():
            idx = df.index[mask]; idx = idx[(idx >= a) & (idx <= b)]
            if len(idx) < 4:
                cells.append(f"{era} n={len(idx):3d}: thin" + " " * 58); continue
            cells.append(f"{era} n={len(idx):3d}: " + " ".join(f"{h}{u} {fwd[h].reindex(idx).mean():+6.1%}" for h in hz)
                         + f" | up {(fwd[main_h].reindex(idx).dropna() > 0).mean():4.0%} heat {heat.reindex(idx).mean():+5.1%} run {run.reindex(idx).mean():+5.1%}")
        print(f"  {lab:52s} " + " || ".join(cells))
    line("ANY BAR (baseline)", pd.Series(True, index=df.index))
    for lab, m in ev.items():
        line(lab, m)
    # states (not transitions)
    print(f"  --- states held (every bar in the state) ---")
    for lab, m in {
        "state: trend rising (Q1 or Q2)": df["tq"].isin([1, 2]), "state: trend falling (Q3 or Q4)": df["tq"].isin([3, 4]),
        "state: trend Q1": df["tq"].eq(1), "state: trend Q2": df["tq"].eq(2), "state: trend Q3": df["tq"].eq(3), "state: trend Q4": df["tq"].eq(4),
        "state: cycle Q1": df["cq"].eq(1), "state: cycle Q2": df["cq"].eq(2), "state: cycle Q3": df["cq"].eq(3), "state: cycle Q4": df["cq"].eq(4),
        "state: both Q3": df["cq"].eq(3) & df["tq"].eq(3), "state: both Q4": df["cq"].eq(4) & df["tq"].eq(4),
        "state: both Q1": df["cq"].eq(1) & df["tq"].eq(1), "state: both Q2": df["cq"].eq(2) & df["tq"].eq(2),
    }.items():
        line(lab, m)


def zigzag(close: pd.Series, pct: float) -> list[tuple[pd.Timestamp, str, float]]:
    """Alternating highs and lows separated by moves of at least pct (on closes)."""
    piv = []; hi_d = lo_d = close.index[0]; hi = lo = close.iloc[0]; mode = None
    for d, v in close.items():
        if mode in (None, "up"):
            if v > hi:
                hi, hi_d = v, d
            if v <= hi * (1 - pct):
                piv.append((hi_d, "H", hi)); mode = "down"; lo, lo_d = v, d
        if mode in (None, "down"):
            if v < lo:
                lo, lo_d = v, d
            if v >= lo * (1 + pct):
                if mode is None and not piv:
                    pass
                piv.append((lo_d, "L", lo)); mode = "up"; hi, hi_d = v, d
    out = [piv[0]] if piv else []
    for p in piv[1:]:
        if p[1] != out[-1][1]:
            out.append(p)
    return out


def turning_points(close: pd.Series, df: pd.DataFrame, ev: dict, tf: str, pct: float, start: str):
    piv = [p for p in zigzag(close, pct) if p[0] >= pd.Timestamp(start)]
    lows = [(d, v) for d, k, v in piv if k == "L"]; highs = [(d, v) for d, k, v in piv if k == "H"]
    u = {"W": "weeks", "M": "months"}[tf]
    print(f"\n=== B. {tf} signals against the {int(pct * 100)}% turning points since {start[:4]} ({len(lows)} lows, {len(highs)} highs) ===")
    px = df["px"]
    def nxt(pts, i):
        return pts[i + 1][0] if i + 1 < len(pts) else px.index[-1] + pd.Timedelta(days=1)
    for side, pts, others, labs in (("LOW", lows, highs, [k for k in ev if k.startswith("BUY")]), ("HIGH", highs, lows, [k for k in ev if k.startswith("SELL")])):
        print(f"  -- at each {side}: bars until the first signal, and how far price had already moved from the {side.lower()} by then --")
        res = {k: [] for k in labs}
        for d, v in pts:
            # window: from the turning point to the next opposite turning point
            opp = [o for o, _ in others if o > d]
            end = opp[0] if opp else px.index[-1] + pd.Timedelta(days=1)
            for k in labs:
                s = ev[k]; hit = s.index[(s.values) & (s.index >= d) & (s.index < end)]
                if len(hit):
                    lag = int(((df.index >= d) & (df.index <= hit[0])).sum()) - 1 + (0 if d in df.index else 1)
                    res[k].append((lag, px.loc[hit[0]] / v - 1))
                else:
                    res[k].append((np.nan, np.nan))
        tot = len(pts)
        for k in labs:
            a = pd.DataFrame(res[k], columns=["lag", "move"])
            got = a["lag"].notna().sum()
            nsig = int(ev[k][ev[k].index >= start].sum())
            first = got  # one first-signal per turning point
            print(f"  {k:52s} caught {got:2d}/{tot:2d}  median lag {a['lag'].median():4.1f} {u}  median move already {a['move'].median():+6.1%}  "
                  f"signals in total {nsig:3d} (so {nsig - first:3d} came later in the same swing or were repeats)")
    return piv


def perf(r: pd.Series, per_year: int) -> str:
    r = r.dropna()
    if len(r) < per_year:
        return "thin"
    eq = (1 + r).cumprod(); yrs = len(r) / per_year
    cagr = eq.iloc[-1] ** (1 / yrs) - 1; dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(per_year) if r.std() > 0 else np.nan
    return f"{cagr:+6.1%} DD {dd:+5.0%} Sh {sh:4.2f}"


def rules(close: pd.Series, vf: pd.Series, irx: pd.Series, tf: str, df: pd.DataFrame, mdf: pd.DataFrame | None = None):
    per = {"W": 52, "M": 12}[tf]
    bars = df["px"]
    # total return per bar: VFINX where available, else the price index; cash = 3-month bill
    tr = tc.to_bars(vf, tf).pct_change().reindex(bars.index)
    r_stock = tr.where(tr.notna(), bars.pct_change())
    rf = (irx / 100).reindex(pd.date_range(irx.index[0], bars.index[-1]), method="ffill").reindex(bars.index, method="ffill").fillna(0.0) / per
    sma = bars.rolling({"W": 40, "M": 10}[tf]).mean()
    c_up, t_up = df["cq"].isin([1, 2]), df["tq"].isin([1, 2])
    pos = {
        "buy and hold": pd.Series(True, index=df.index),
        f"benchmark: above the {'10-month' if tf == 'M' else '40-week'} average": bars > sma,
        "in while trend rising (Q1,Q2)": t_up,
        "in while cycle rising (Q1,Q2)": c_up,
        "in while trend above zero (Q2,Q3)": df["tq"].isin([2, 3]),
        "in unless trend Q4": ~df["tq"].eq(4),
        "in unless trend Q4 AND cycle Q4": ~(df["tq"].eq(4) & df["cq"].eq(4)),
        "in unless both below zero (not BROKEN)": ~(df["cq"].isin([1, 4]) & df["tq"].isin([1, 4])),
        "in unless trend Q4 or (trend Q3 and cycle Q4)": ~(df["tq"].eq(4) | (df["tq"].eq(3) & df["cq"].eq(4))),
        "in unless both falling (cycle and trend in Q3/Q4)": ~(~c_up & ~t_up),
        "in when either is rising": c_up | t_up,
        "in when trend rising or above zero with cycle rising": t_up | (df["tq"].eq(3) & c_up),
    }
    if tf == "W":
        pos["in unless trend Q4 in its first 3 weeks"] = ~(df["tq"].eq(4) & (df["tcn"] <= 3))
        pos["in unless trend Q4 after week 3 (inverse check)"] = ~(df["tq"].eq(4) & (df["tcn"] > 3))
        if mdf is not None:
            m_broken = (mdf["cq"].isin([1, 4]) & mdf["tq"].isin([1, 4])).shift(1).reindex(df.index, method="ffill").fillna(False).astype(bool)
            m_trend_dn = mdf["tq"].eq(4).shift(1).reindex(df.index, method="ffill").fillna(False).astype(bool)
            pos["in unless weekly trend Q4 while monthly BROKEN"] = ~(df["tq"].eq(4) & m_broken)
            pos["in unless weekly trend falling while monthly trend Q4"] = ~(~t_up & m_trend_dn)
            pos["monthly not broken: always in; broken: in only while weekly trend rising"] = ~m_broken | t_up
    print(f"\n=== C. {tf} long/flat rules (signal at the bar close, held over the next bar; cash earns the 3-month bill; "
          f"total return from 1987, price only before) ===")
    print(f"  {'rule':70s} " + " | ".join(f"{e:^26s}" for e in ERAS) + " | time in, switches/yr")
    for lab, p in pos.items():
        held = p.shift(1).fillna(False).astype(bool)
        r = r_stock.where(held, rf)
        cells = [perf(r.loc[a:b], per) for a, b in ERAS.values()]
        sw = (held != held.shift(1)).loc["1987":].sum() / ((df.index[-1] - pd.Timestamp("1987-01-01")).days / 365.25)
        print(f"  {lab:70s} " + " | ".join(f"{c:^26s}" for c in cells) + f" | {held.loc['1987':].mean():4.0%} {sw:4.1f}")


def member_signals():
    f = CACHE / "qb_monthly_signals.pkl"
    if not f.exists():
        from research.trend_cycle.signals import monthly_signals
        monthly_signals().to_pickle(f)
    sig = pd.read_pickle(f)
    spx = sig["spx"]
    fwd = {h: spx.shift(-h) / spx - 1 for h in (3, 6, 12, 24)}
    heat = pd.Series([spx.iloc[i:i + 13].min() / spx.iloc[i] - 1 for i in range(len(spx))], index=spx.index)
    print(f"\n=== D. member-balance signals, monthly bars, {sig.index[0].date()} -> {sig.index[-1].date()} (today's constituents) ===")
    first = lambda m: m & ~m.shift(1, fill_value=False)  # noqa: E731
    peak6 = sig["cyc_q4"].rolling(6).max()
    conds = {
        "ANY MONTH (baseline)": pd.Series(True, index=sig.index),
        "BUY  washout: 50%+ of members in cycle Q4": sig["cyc_q4"] >= 50,
        "BUY  washout, first month": first(sig["cyc_q4"] >= 50),
        "BUY  washout turn: Q4 share down 15+ pts from a 6m peak of 45%+": first((peak6 >= 45) & (sig["cyc_q4"] <= peak6 - 15)),
        "BUY  35%+ of members in cycle Q1 (turning up below zero)": first(sig["cyc_q1"] >= 35),
        "BUY  35%+ of members in trend Q1": first(sig["trd_q1"] >= 35),
        "BUY  trend Q4 share above 40%": sig["trd_q4"] >= 40,
        "SELL 45%+ of members in cycle Q3 (rolling over)": first(sig["cyc_q3"] >= 45),
        "SELL 50%+ of members in trend Q3": first(sig["trd_q3"] >= 50),
        "SELL index trend Q2 but under 45% of members' trends rising": first(sig["idx_trend_q"].eq(2) & (sig["trd_q1q2"] < 45)),
        "SELL index within 3% of 12m high, 40%+ members cycle falling above zero": first((spx >= spx.rolling(12).max() * 0.97) & (sig["cyc_q3"] >= 40)),
        "SELL members rising (cycle) under 30% while index trend above zero": first((sig["cyc_q1q2"] < 30) & sig["idx_trend_q"].isin([2, 3])),
        "STATE members' trend Q4 share 20-30%": sig["trd_q4"].between(20, 30),
        "STATE members' trend Q3 share 40%+": sig["trd_q3"] >= 40,
    }
    for lab, m in conds.items():
        cells = []
        for era, (a, b) in list(ERAS.items())[1:]:
            idx = sig.index[m.fillna(False)]; idx = idx[(idx >= a) & (idx <= b)]
            if len(idx) < 4:
                cells.append(f"{era} n={len(idx):3d}: thin" + " " * 50); continue
            cells.append(f"{era} n={len(idx):3d}: " + " ".join(f"{h}m {fwd[h].reindex(idx).mean():+6.1%}" for h in fwd)
                         + f" | up12 {(fwd[12].reindex(idx).dropna() > 0).mean():4.0%} heat12 {heat.reindex(idx).mean():+5.1%}")
        print(f"  {lab:72s} " + " || ".join(cells))


def list_events(df, ev, keys, start="1950"):
    for k in keys:
        d = df.index[ev[k]]; d = d[d >= start]
        print(f"  {k}: " + ", ".join(x.strftime("%Y-%m") for x in d))


def main():
    close, vf, irx = load()
    print(f"S&P 500 {close.index[0].date()} -> {close.index[-1].date()}")
    out = {}
    for tf in ("M", "W"):
        bars = tc.to_bars(close, tf)
        bars = bars.iloc[:-1] if tf == "M" and close.index[-1] < bars.index[-1] else bars     # completed bars only for the monthly study
        df = states(bars); ev = events(df, tf); out[tf] = (df, ev)
        event_table(df, ev, tf)
    for tf, pct in (("M", 0.20), ("W", 0.10)):
        df, ev = out[tf]
        piv = turning_points(close, df, ev, tf, pct, "1952-01-01")
        if tf == "M":
            print("  20% turning points: " + ", ".join(f"{k} {d.strftime('%Y-%m')}" for d, k, _ in piv))
    print("\n  Monthly signal dates:")
    list_events(*out["M"], ["BUY  trend turns up below zero (->Q1)", "BUY  both rising, first bar, trend still below zero", "BUY  trend crosses above zero (->Q2)",
                            "SELL trend crosses below zero (->Q4)", "SELL both below zero, first bar (BROKEN)", "SELL trend ->Q3 after 12+ bars above zero"])
    rules(close, vf, irx, "M", out["M"][0])
    rules(close, vf, irx, "W", out["W"][0], out["M"][0])
    member_signals()
    pickle.dump({tf: out[tf][0] for tf in out}, open(CACHE / "qb_signal_states.pkl", "wb"))


if __name__ == "__main__":
    main()

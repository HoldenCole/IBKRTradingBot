"""Entry 95 — Bollinger bands on the S&P 500 and Nasdaq-100 over daily, weekly and monthly bars,
played through a 3x fund. See PREREGISTRATION_95.md.

    python3 -m research.swing.study_bb_index
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load, ohlc
from research.swing.lib import daily_features
from research.swing.study_standalone import run

LEV, COST = 3, 0.0009
FIN, FEE = 0.01, 0.0095
ERAS = {"1988-2006": ("1988-01-01", "2006-12-31"), "2007-2026": ("2007-01-01", "2026-12-31")}
INDEX = {"S&P 500": ("^GSPC", "SPY", 0.030), "Nasdaq-100": ("^NDX", "QQQ", 0.005)}


def total_return(idx: str, etf: str, dy: float) -> tuple[pd.Series, pd.Series]:
    px = ohlc(idx)["close"]
    r = px.pct_change()
    e = ohlc(etf)["close"].pct_change()
    r = r + dy / 252
    r.loc[e.dropna().index.intersection(r.index)] = e.dropna()
    return px, r.dropna()


def bar_ends(idx: pd.DatetimeIndex, tf: str) -> pd.DatetimeIndex:
    if tf == "D":
        return idx
    key = idx.to_period("W-FRI") if tf == "W" else idx.to_period("M")
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby(key).last().values)


def bands(px: pd.Series, tf: str, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    c = px.loc[bar_ends(px.index, tf)]
    mid = c.rolling(n).mean(); sd = c.rolling(n).std(ddof=0)
    return pd.DataFrame({"c": c, "mid": mid, "up": mid + k * sd, "lo": mid - k * sd}).dropna()


def state_machine(b: pd.DataFrame, rule: str, allow: pd.Series | None = None) -> pd.Series:
    """1 while held, at each bar end (decided at that bar's close)."""
    out, held = [], 0
    for d, row in b.iterrows():
        ok = True if allow is None else bool(allow.get(d, False))
        if rule == "above":
            held = int(row.c > row.mid)
        elif rule in ("dip_mid", "dip_up"):
            if not held and row.c < row.lo and ok:
                held = 1
            elif held and row.c >= (row.mid if rule == "dip_mid" else row.up):
                held = 0
        elif rule == "breakout":
            if not held and row.c > row.up:
                held = 1
            elif held and row.c < row.mid:
                held = 0
        out.append(held)
    return pd.Series(out, index=b.index)


def daily_position(px: pd.Series, rule: str, tf: str, n=20, k=2.0, combo: str | None = None) -> pd.Series:
    """Held flag for each day's return (signal at close t applies from day t+1)."""
    allow = None
    if combo:
        hb = bands(px, combo, n, k)
        above = (hb.c > hb.mid).reindex(px.index).ffill().fillna(False)
        allow = above
    b = bands(px, tf, n, k)
    h = state_machine(b, rule, allow).reindex(px.index).ffill().fillna(0)
    return h.shift(1).fillna(0)


def account(pos: pd.Series, r: pd.Series, rf: pd.Series, lev=LEV, cost=COST) -> pd.Series:
    pos = pos.reindex(r.index).fillna(0)
    f = rf.reindex(r.index).ffill().fillna(0) / 252
    a = pos * (lev * r - (lev - 1) * (f + FIN / 252) - (FEE / 252 if lev > 1 else 0))
    trades = pos.diff().abs().fillna(pos.iloc[0])
    return a - trades * cost


def perf(a: pd.Series, pos: pd.Series | None = None) -> dict:
    if len(a) < 20:
        return {}
    eq = (1 + a).cumprod()
    yrs = len(a) / 252
    d = {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "Sharpe": a.mean() / a.std() * np.sqrt(252) if a.std() > 0 else np.nan,
         "maxDD": (eq / eq.cummax() - 1).min()}
    if pos is not None:
        p = pos.reindex(a.index).fillna(0)
        d["in_market"] = p.mean()
        d["trades_yr"] = (p.diff() > 0).sum() / yrs
    return d


RULES = [(f"{tf} {name}", rule, tf, None) for tf in ("D", "W", "M")
         for name, rule in (("dip to middle", "dip_mid"), ("dip to upper", "dip_up"),
                            ("breakout", "breakout"), ("above middle", "above"))]
RULES += [("D dip to middle, weekly above middle", "dip_mid", "D", "W"),
          ("D dip to middle, monthly above middle", "dip_mid", "D", "M")]


def era_slice(a, era):
    s, e = ERAS[era]
    return a.loc[s:e]


def main():
    rf = ohlc("^IRX")["close"] / 100
    # model check
    for name, fund in (("S&P 500", "UPRO"), ("Nasdaq-100", "TQQQ")):
        px, r = total_return(*INDEX[name])
        act = ohlc(fund)["close"].pct_change().dropna()
        syn = account(pd.Series(1.0, index=r.index), r, rf, cost=0).loc[act.index[0]:]
        act = act.loc[syn.index[0]:syn.index[-1]]
        print(f"model check {fund} {act.index[0].date()}-{act.index[-1].date()}: actual CAGR {perf(act)['CAGR']:+.1%} "
              f"model {perf(syn.loc[act.index])['CAGR']:+.1%}; daily corr {np.corrcoef(act, syn.reindex(act.index))[0,1]:.3f}")
    rows = []
    for name in INDEX:
        px, r = total_return(*INDEX[name])
        bh = pd.Series(1.0, index=r.index)
        for lab, rule, tf, combo, lev in [("3x buy and hold", None, None, None, 3), ("1x buy and hold", None, None, None, 1)] + \
                [(l, ru, t, c, 3) for l, ru, t, c in RULES]:
            pos = bh if rule is None else daily_position(px, rule, tf, combo=combo)
            a = account(pos, r, rf, lev=lev)
            for era in ERAS:
                p = perf(era_slice(a, era), pos)
                rows.append({"index": name, "rule": lab, "era": era, **p})
            p = perf(a.loc["1999-03-11":], pos)
            rows.append({"index": name, "rule": lab, "era": "1999-2026", **p})
            if rule is not None:
                pos2 = pos.shift(1).fillna(0)
                a2 = account(pos2, r, rf)
                for era in ERAS:
                    rows.append({"index": name, "rule": lab, "era": era + " (one session late)", **perf(era_slice(a2, era), pos2)})
    res = pd.DataFrame(rows)

    # gates: beat 3x buy and hold on CAGR, Sharpe and maxDD in both eras
    def beats(name, lab, n=20, k=2.0):
        px, r = total_return(*INDEX[name])
        spec = next(x for x in RULES if x[0] == lab)
        pos = daily_position(px, spec[1], spec[2], n, k, spec[3])
        a = account(pos, r, rf)
        bh = account(pd.Series(1.0, index=r.index), r, rf)
        ok = True
        for era in ERAS:
            p, b = perf(era_slice(a, era)), perf(era_slice(bh, era))
            ok &= p["CAGR"] > b["CAGR"] and p["Sharpe"] > b["Sharpe"] and p["maxDD"] > b["maxDD"]
        return ok

    verdict = []
    for name in INDEX:
        for lab, *_ in RULES:
            base = beats(name, lab)
            nb = [beats(name, lab, n, k) for n, k in ((10, 2.0), (30, 2.0), (20, 1.5), (20, 2.5))] if base else []
            verdict.append({"index": name, "rule": lab, "beats_3x_bh_both_eras": base,
                            "neighbours_pass": f"{sum(nb)}/4" if base else "-", "passes": base and all(nb)})
    v = pd.DataFrame(verdict)

    # the live plan for comparison: test 79 at 3x, 9 bp, idle cash at zero
    data = load(); feats = daily_features(data)
    out, tr = run(data, feats, "UNION", ["SPY", "QQQ"], 2, "aligned+nofragile", cost_bps=COST * 1e4 / LEV)  # cost on the fund bought, not on 3x exposure
    f = rf.reindex(out.index).ffill().fillna(0) / 252
    sw = 3 * out["pos"] - out["expo"] * (2 * (f + FIN / 252) + FEE / 252)
    sw = sw.loc["1999-03-11":]
    swp = perf(sw)
    print(f"\ntest-79 swing account at 3x, 1999-2026: CAGR {swp['CAGR']:+.1%} Sharpe {swp['Sharpe']:.2f} maxDD {swp['maxDD']:+.0%}")
    corr = []
    for name in INDEX:
        px, r = total_return(*INDEX[name])
        for lab, rule, tf, combo in RULES:
            a = account(daily_position(px, rule, tf, combo=combo), r, rf).loc["1999-03-11":]
            corr.append({"index": name, "rule": lab, "corr_with_swing": a.corr(sw.reindex(a.index).fillna(0))})
    v = v.merge(pd.DataFrame(corr), on=["index", "rule"])
    res.to_csv("research/swing/bb_index_results.csv", index=False, float_format="%.4f")
    v.to_csv("research/swing/bb_index_verdicts.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 220)
    for era in ("1988-2006", "2007-2026", "1999-2026"):
        t = res[res.era == era].pivot_table(index="rule", columns="index", values=["CAGR", "maxDD", "Sharpe"], sort=False)
        print(f"\n=== {era} ===")
        print(t.round(3).to_string())
    late = res[res.era.str.contains("late")].pivot_table(index="rule", columns=["index", "era"], values="CAGR", sort=False)
    print("\n=== CAGR with execution one session late ===")
    print(late.round(3).to_string())
    inm = res[res.era == "1999-2026"].pivot_table(index="rule", columns="index", values=["in_market", "trades_yr"], sort=False)
    print(inm.round(2).to_string())
    print("\n", v.round(2).to_string(index=False))


if __name__ == "__main__":
    main()

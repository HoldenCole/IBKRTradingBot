"""Entry 79 checks on the selected standalone design (SPY+QQQ, RSI2<10 dip that is
either below the lower Bollinger band or above the 200d SMA; G/R quadrants only;
not fragile; exit close > 5d SMA or 10 days; two 50% slots).

    python3 -m research.swing.study_standalone_checks
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.swing.data import load
from research.swing.lib import ERAS, bollinger, daily_features, era_of, perf, rsi, simulate, sma
from research.swing import study_standalone as st
from research.swing import study_options as so


def main():
    data = load(); feats = daily_features(data)
    rf = (data["^IRX"]["close"] / 100 / 252).reindex(feats.index).ffill().fillna(0.0)
    U = ["SPY", "QQQ"]

    out, tr = st.run(data, feats, "UNION", U, 2, "aligned+nofragile")
    a = st.account(out, rf)
    ex = a - rf.reindex(a.index)
    yrs = len(a) / 252
    sh = ex.mean() * 252 / (a.std() * np.sqrt(252))
    print(f"=== K1 excess over T-bills: {ex.mean()*252:+.2%}/yr, vol {a.std()*np.sqrt(252):.1%}, excess Sharpe {sh:.2f}, t {sh*np.sqrt(yrs):.1f} over {yrs:.0f} yrs ===")
    for k, (x, y) in ERAS.items():
        e = ex.loc[x:y]
        print(f"   {k}: excess {e.mean()*252:+.2%}/yr  excess Sharpe {e.mean()*252/(a.loc[x:y].std()*np.sqrt(252)):.2f}")
    inpos = out["pos"][out["expo"] > 0]
    print(f"   return while invested: {out['pos'].sum()/out['expo'].sum()*252:+.0%} annualized on deployed capital; "
          f"days with any position {(out['expo']>0).mean():.0%}")

    print("\n=== K2 parameter neighbours (1x): CAGR / Sharpe / maxDD, and worst-era CAGR ===")
    base_sig = st.sig
    for th in (5, 10, 15, 20):
        for ex_n in (3, 5, 8):
            def sig(df, kind, th=th, ex_n=ex_n):
                c = df["close"]; mid, up, lo, pctb, bw = bollinger(c, 20, 2.0); r2 = rsi(c, 2)
                return (r2 < th) & ((c < lo) | (c > sma(c, 200))), c > sma(c, ex_n), 10, r2
            st.sig = sig
            o, t = st.run(data, feats, "UNION", U, 2, "aligned+nofragile")
            acc = st.account(o, rf); p = perf(acc)
            worst = min(perf(acc.loc[x:y])["CAGR"] for x, y in ERAS.values())
            print(f"   RSI2<{th:2d}, exit > SMA{ex_n}: {p['CAGR']:+.1%} / {p['Sharpe']:.2f} / {p['maxDD']:+.0%}   worst era {worst:+.1%}   "
                  f"expo {o['expo'].mean():.0%}  trades/yr {len(t)/(len(o)/252):.0f}  mean {t['ret'].mean()*1e4:+.0f}bp")
    st.sig = base_sig

    print("\n=== K3 extra era: SPY only, 1994-1998 (before QQQ existed), one 100% slot ===")
    st.START = "1994-01-01"
    o, t = st.run(data, feats, "UNION", ["SPY"], 1, "aligned+nofragile")
    acc = st.account(o, rf)
    for lab, (x, y) in {"1994-1998": ("1994-01-01", "1998-12-31"), **ERAS}.items():
        s = acc.loc[x:y]; p = perf(s); tt = t[(t["entry"] >= x) & (t["entry"] <= y)]
        b = perf(data["SPY"]["close"].pct_change().loc[x:y])
        print(f"   {lab}: {p['CAGR']:+.1%} / {p['Sharpe']:.2f} / {p['maxDD']:+.0%}  n={len(tt)} mean {tt['ret'].mean()*1e4:+.0f}bp win {(tt['ret']>0).mean():.0%}   (SPY b&h {b['CAGR']:+.1%} / {b['maxDD']:+.0%})")
    st.START = "1999-06-01"

    print("\n=== K4 MODEL-BASED options version of the same signal (SPY/QQQ, 30 DTE), risking a fixed share of the account per trade ===")
    ivs = {"SPY": 0.90 * (data["^VIX"]["close"] / 100).reindex(data["SPY"].index).ffill(),
           "QQQ": 0.90 * (data["^VXN"]["close"] / 100).reindex(data["QQQ"].index)}
    frag = (feats["spy_ext200"].between(0, 0.03)) & (feats["rvol20"] > 0.16)
    rows = []
    for s in U:
        df = data[s]; c = df["close"]; mid, up, lo, pctb, bw = bollinger(c, 20, 2.0); r2 = rsi(c, 2)
        e = (r2 < 10) & ((c < lo) | (c > sma(c, 200))) & feats["quad"].reindex(c.index).isin(["G", "R"]) \
            & ~frag.reindex(c.index).fillna(False) & ivs[s].reindex(c.index).notna()
        trd, _ = simulate(df, e, c > sma(c, 5), 10)
        for _, t_ in trd.iterrows():
            S0 = float(df["raw_close"].loc[t_["entry"]]); S1 = S0 * c.loc[t_["exit"]] / c.loc[t_["entry"]]
            v0 = ivs[s].loc[t_["entry"]]; v1 = ivs[s].reindex(c.index).ffill().loc[t_["exit"]]
            r = float((data["^IRX"]["close"] / 100).reindex(c.index).ffill().loc[t_["entry"]])
            cal = (t_["exit"] - t_["entry"]).days
            row = {"entry": t_["entry"], "exit": t_["exit"], "stock": t_["ret"]}
            for name, legs in so.STRUCTS.items():
                c0 = sum(sg * so.fill(so.price(S0, S0 * k, so.DTE, v0, r, call), sg > 0) for call, k, sg in legs)
                v = sum(sg * so.fill(so.price(S1, S0 * k, so.DTE - cal, v1, r, call), sg < 0) for call, k, sg in legs)
                risk = c0 if c0 > 0 else (max(k for _, k, _ in legs) - min(k for _, k, _ in legs)) * S0 + c0
                row[name] = (v - c0) / risk
            rows.append(row)
    T = pd.DataFrame(rows).sort_values("exit")
    T["era"] = T["entry"].map(era_of); T = T[T["era"].isin(ERAS)]
    yrs = (T["exit"].max() - T["entry"].min()).days / 365.25
    print(f"   n={len(T)} trades ({len(T)/yrs:.0f}/yr); stock version mean {T['stock'].mean()*1e4:+.0f}bp")
    for name in so.STRUCTS:
        r = T[name]
        line = f"   {name:30s} per trade on risk: mean {r.mean():+.1%} sd {r.std():.0%} win {(r>0).mean():.0%} worst {r.min():+.0%} | by era " \
               + " ".join(f"{T[T['era']==e][name].mean():+.1%}" for e in ERAS)
        for f in (0.05, 0.10):
            eq = (1 + f * r).cumprod()
            line += f" | risk {f:.0%}/trade: CAGR {eq.iloc[-1]**(1/yrs)-1:+.1%} maxDD {float((eq/eq.cummax()-1).min()):+.0%}"
        print(line)
    print("   (CAGR excludes T-bill interest on idle cash, ~+2%/yr historically; trades treated as sequential)")


if __name__ == "__main__":
    main()

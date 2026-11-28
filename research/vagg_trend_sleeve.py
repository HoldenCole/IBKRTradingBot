"""Entry 120 — a levered-fund trend sleeve as a satellite beside VAGG. See PREREGISTRATION_120.md.

    python3 -m research.vagg_trend_sleeve
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import research.engine as E  # noqa: E402
import research.engine_pre2007 as P  # noqa: E402
from research.swing.study_rotation_3x import UNI, month_paths, run, setup, trend_weights  # noqa: E402


def stats(r):
    r = r.dropna(); yrs = len(r) / 252
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    dn = r[r < 0].std() * np.sqrt(252); eq = (1 + r).cumprod()
    return {"CAGR": cagr, "Sortino": cagr / dn, "maxDD": float((eq / eq.cummax() - 1).min())}


def mix(a, b, wb):
    """Reset to (1 - wb, wb) at each month-end, drift within the month."""
    df = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    out = []
    for _, g in df.groupby(df.index.to_period("M")):
        path = (1 - wb) * (1 + g["a"]).cumprod() + wb * (1 + g["b"]).cumprod()
        out.append(path / path.shift(1).fillna(1.0) - 1)
    return pd.concat(out)


def main():
    pd.set_option("display.width", 200)
    # sleeves
    data, days, C, rf, R1, R3, M, trend, elig, vol3, feats = setup()
    paths = [p for p in month_paths(R3, M) if p[0] >= pd.Timestamp("1999-12-31")]
    t17 = run(paths, trend_weights(trend, elig, UNI), UNI)
    t1 = run(paths, lambda a: np.array([1.0 if (elig.loc[a, "SPY"] and trend.loc[a, "SPY"]) else 0.0]), ["SPY"])
    # VAGG, both engines
    px = E.load_all(); _, q, td, months = E.build(px)
    vm = td["VAGG"]
    pxo = P.load_all(); _, qo, tdo, monthso = P.build(pxo)
    vo = tdo["VAGG"].loc["2000-01-01":"2006-12-31"]
    print(f"modern window {vm.index[0].date()} to {vm.index[-1].date()}; earlier window {vo.index[0].date()} to {vo.index[-1].date()}")
    h = stats(vm)
    print(f"V0 reproduces the official engine: VAGG CAGR {h['CAGR']:+.1%} Sortino {h['Sortino']:.2f} maxDD {h['maxDD']:+.1%}\n")

    eras = {"2007-2026": vm, "2000-2006": vo}
    variants = {"V0 VAGG alone": (None, 0.0), "V1 80% VAGG + 20% T17": (t17, 0.2), "V2 70% VAGG + 30% T17": (t17, 0.3),
                "V3 80% VAGG + 20% T1 (SPY 3x trend)": (t1, 0.2), "T17 sleeve alone": (t17, 1.0), "T1 sleeve alone": (t1, 1.0)}
    rows = []
    for lab, (sl, w) in variants.items():
        row = {"variant": lab}
        for e, v in eras.items():
            a = v if sl is None else (sl.loc[v.index[0]:v.index[-1]] if w == 1.0 else mix(v, sl, w))
            s = stats(a)
            row.update({f"{e} CAGR": s["CAGR"] * 100, f"{e} Sortino": s["Sortino"], f"{e} maxDD": s["maxDD"] * 100})
        rows.append(row)
    t = pd.DataFrame(rows).set_index("variant")
    print(t.round(2).to_string())
    base = t.loc["V0 VAGG alone"]
    print("\nverdicts (both eras: higher CAGR and Sortino, drawdown no more than 2 points worse):")
    for lab in ("V1 80% VAGG + 20% T17", "V2 70% VAGG + 30% T17", "V3 80% VAGG + 20% T1 (SPY 3x trend)"):
        x = t.loc[lab]
        ok = all(x[f"{e} CAGR"] > base[f"{e} CAGR"] and x[f"{e} Sortino"] > base[f"{e} Sortino"]
                 and x[f"{e} maxDD"] >= base[f"{e} maxDD"] - 2 for e in eras)
        print(f"   {lab}: {'PASSES' if ok else 'fails'}")

    print("\ncorrelation of monthly returns with VAGG:")
    for e, v in eras.items():
        vm_m = (1 + v).resample("ME").prod() - 1
        for nm, sl in (("T17", t17), ("T1", t1)):
            sm = (1 + sl.loc[v.index[0]:v.index[-1]]).resample("ME").prod() - 1
            print(f"   {e} {nm}: {vm_m.corr(sm):+.2f}")

    print("\nmean monthly return by regime, 2007-2026 (%):")
    lab = pd.Series({st: l for st, l, w in months}).sort_index()
    mo = pd.DataFrame({"VAGG": (1 + vm).resample("ME").prod() - 1,
                       "T17": (1 + t17.loc[vm.index[0]:]).resample("ME").prod() - 1,
                       "T1": (1 + t1.loc[vm.index[0]:]).resample("ME").prod() - 1})
    mo["regime"] = [lab[lab.index < d].iloc[-1] if (lab.index < d).any() else None for d in mo.index]
    g = mo.groupby("regime")
    print((g[["VAGG", "T17", "T1"]].mean() * 100).round(2).assign(months=g.size()).to_string())

    print("\nworst VAGG months 2007-2026 and the sleeves the same month (%):")
    w5 = mo.sort_values("VAGG").head(6)
    print((w5[["VAGG", "T17", "T1"]] * 100).round(1).assign(regime=w5.regime).to_string())
    print("\npracticality: T17 holds up to 17 positions. At 20% of the account, one position is about 1.2% of the account;"
          "\nwith IBKR Pro's $1 minimum per order to stay near 0.1% per trade, each position needs about $1,000, i.e. an account"
          "\nof roughly $85,000. T1 is one position and works at any size.")


if __name__ == "__main__":
    main()

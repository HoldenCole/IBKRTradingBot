"""Fingerprint of the intra-month crash months. At each month-end stamp
classified risk-on (G or R), measure ex-ante features; relate to the
NEXT month's SPY/QQQ return and to the six crash months."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from research.engine import load_all, build, BREADTH
from src.data.yahoo import _get_json, _result

px = load_all(); rets, q, tier_daily, months = build(px)
labels = pd.Series({st: lab for st, lab, w in months}).sort_index()
spy, qqq = px["SPY"].dropna(), px["QQQ"].dropna()
CACHE = Path("research/cache"); vf = CACHE / "SPY_volume.csv"
if vf.exists():
    vol = pd.read_csv(vf, index_col=0, parse_dates=True).iloc[:, 0]
else:
    parts, cur, t1 = [], pd.Timestamp("2005-06-01"), pd.Timestamp("2026-12-31")
    while cur < t1:
        nxt = min(cur + pd.DateOffset(years=5), t1)
        p1 = int(cur.tz_localize("UTC").timestamp()); p2 = int(nxt.tz_localize("UTC").timestamp())
        res = _result(_get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1={p1}&period2={p2}&interval=1d"), "SPY")
        idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
        parts.append(pd.Series(res["indicators"]["quote"][0]["volume"], index=idx, dtype="float64")); cur = nxt; time.sleep(0.2)
    vol = pd.concat(parts).dropna(); vol = vol[~vol.index.duplicated()].sort_index(); vol.to_frame("volume").to_csv(vf)

m = spy.resample("ME").last(); sma10 = m.rolling(10).mean()
sect_m = {s: px[s].resample("ME").last().dropna() for s in BREADTH if s in px}
def breadth_at(st):
    flags = [float(sm.asof(st) > sm.loc[:st].tail(10).mean()) for sm in sect_m.values() if len(sm.loc[:st]) >= 10]
    return np.mean(flags) if flags else np.nan
dr = spy.pct_change()
rows = []
prev_lab = None; since = 0
for st in labels.index:
    lab = labels.loc[st]
    since = since + 1 if lab in ("G", "R") and prev_lab in ("G", "R") else (1 if lab in ("G", "R") else 0)
    prev_lab = lab
    if lab not in ("G", "R"): continue
    d = spy.loc[:st]
    nxt_idx = labels.index[labels.index > st]
    nxt = nxt_idx[0] if len(nxt_idx) else spy.index[-1]
    f = dict(stamp=st, cell=lab, since_reentry=since,
             breadth=breadth_at(st),
             mom1=float(m.asof(st) / m.loc[:st].iloc[-2] - 1), mom3=float(m.asof(st) / m.loc[:st].iloc[-4] - 1),
             mom6=float(m.asof(st) / m.loc[:st].iloc[-7] - 1), mom12=float(m.asof(st) / m.loc[:st].iloc[-13] - 1),
             ext=float(m.asof(st) / sma10.asof(st) - 1),
             rvol20=float(dr.loc[:st].tail(20).std() * np.sqrt(252)),
             dd_1m=float((d.tail(22) / d.tail(22).cummax() - 1).min()),
             off_high=float(d.iloc[-1] / d.tail(252).max() - 1),
             vol_ratio=float(vol.loc[:st].tail(20).mean() / vol.loc[:st].tail(200).mean()),
             next_spy=float(spy.asof(nxt) / spy.asof(st) - 1), next_qqq=float(qqq.asof(nxt) / qqq.asof(st) - 1))
    rows.append(f)
df = pd.DataFrame(rows).set_index("stamp")
df["crash"] = df.next_spy <= -0.05
CRASH = ["2015-07-31", "2015-12-31", "2018-09-30", "2018-11-30", "2020-01-31", "2022-11-30"]
feat = ["since_reentry", "breadth", "mom1", "mom3", "mom6", "mom12", "ext", "rvol20", "dd_1m", "off_high", "vol_ratio"]
print(f"risk-on month-ends: n={len(df)}; crash months (next SPY <= -5%): {int(df.crash.sum())}")
print("\n== fingerprint: percentile rank (within risk-on months) of each feature at the stamp BEFORE each crash month ==")
pct = df[feat].rank(pct=True)
hdr = f"{'stamp':>10} {'cell':>4} " + " ".join(f"{c:>9}" for c in feat)
print(hdr)
for c in CRASH:
    st = pd.Timestamp(c)
    if st in df.index:
        print(f"{c:>10} {df.loc[st,'cell']:>4} " + " ".join(f"{pct.loc[st, f]*100:>8.0f}%" for f in feat) + f"   next SPY {df.loc[st,'next_spy']:+.1%}")
print("\n== all crash months (next SPY <= -5%) share? mean percentile of each feature ==")
cr = pct[df.crash]; ok = pct[~df.crash]
for f in feat:
    print(f"  {f:>13}: crash-month mean pctile {cr[f].mean()*100:4.0f}  vs normal {ok[f].mean()*100:4.0f}")
print("\n== tercile splits: next-month QQQ mean / hit / crash rate ==")
for f in feat:
    t1, t2 = df[f].quantile([1/3, 2/3])
    lo, mid, hi = df[df[f] <= t1], df[(df[f] > t1) & (df[f] <= t2)], df[df[f] > t2]
    print(f"  {f:>13}: low {lo.next_qqq.mean():+.2%}/{100*(lo.next_qqq>0).mean():.0f}%/crash {100*lo.crash.mean():.0f}%   "
          f"mid {mid.next_qqq.mean():+.2%}/{100*(mid.next_qqq>0).mean():.0f}%/{100*mid.crash.mean():.0f}%   "
          f"high {hi.next_qqq.mean():+.2%}/{100*(hi.next_qqq>0).mean():.0f}%/{100*hi.crash.mean():.0f}%")
print("\n== months since re-entry ==")
for k in [1, 2, 3]:
    d = df[df.since_reentry == k]; print(f"  month {k}: n={len(d)} next QQQ {d.next_qqq.mean():+.2%} hit {100*(d.next_qqq>0).mean():.0f}% crash {100*d.crash.mean():.0f}%")
d = df[df.since_reentry >= 4]; print(f"  month 4+: n={len(d)} next QQQ {d.next_qqq.mean():+.2%} hit {100*(d.next_qqq>0).mean():.0f}% crash {100*d.crash.mean():.0f}%")
df.to_csv("research/cache/crash_fingerprint_modern.csv")

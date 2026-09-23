"""Re-fetch the pre-2007 proxy dataset (lost with the scratchpad) into
research/cache/. Fidelity Select sector funds stand in for sector ETFs
(daily NAVs back to the 1980s); VFINX/NDX/VUSTX/FKRCX/FSENX/FDFAX/FSAGX/
GSCI are the proxies the era-2 engine used; ^GSPC carries index volume."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.data.yahoo import fetch_yahoo_daily_window, _get_json, _result

CACHE = Path(__file__).resolve().parent / "cache"
SYMS = ["VFINX", "VUSTX", "FKRCX", "FSENX", "FDFAX", "FSAGX", "^SPGSCI", "^NDX", "^IRX", "^GSPC",
        # Fidelity Select sectors (breadth proxies)
        "FSPTX", "FSELX", "FBIOX", "FSRPX", "FIDSX", "FSPHX", "FSUTX", "FSNGX", "FSDPX", "FSCSX",
        "FSAIX", "FSRFX", "FSCHX", "FDLSX", "FSHOX", "FSTCX", "FSAVX", "FSLBX"]

def fetch_volume(symbol, start, end):
    parts = []
    cur, t1 = pd.Timestamp(start), pd.Timestamp(end)
    while cur < t1:
        nxt = min(cur + pd.DateOffset(years=5), t1)
        p1 = int(cur.tz_localize("UTC").timestamp()); p2 = int(nxt.tz_localize("UTC").timestamp())
        res = _result(_get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"), symbol)
        idx = pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert(None).normalize()
        parts.append(pd.Series(res["indicators"]["quote"][0].get("volume"), index=idx, dtype="float64"))
        cur = nxt; time.sleep(0.2)
    s = pd.concat(parts).dropna(); return s[~s.index.duplicated(keep="last")].sort_index()

CACHE.mkdir(exist_ok=True)
for sym in SYMS:
    f = CACHE / f"long_{sym.replace('^','')}.csv"
    if f.exists(): continue
    try:
        s = fetch_yahoo_daily_window(sym, "1984-01-01", "2007-12-31")
        s.to_frame(sym).to_csv(f); print(f"{sym}: {len(s)} rows from {s.index[0].date()}")
    except Exception as exc:
        print(f"{sym}: FAILED {exc}")
    time.sleep(0.3)
for sym, lo, hi, name in [("^GSPC", "1984-01-01", "2007-12-31", "long_GSPC_volume"), ("SPY", "2005-06-01", "2026-12-31", "SPY_volume")]:
    f = CACHE / f"{name}.csv"
    if not f.exists():
        v = fetch_volume(sym, lo, hi); v.to_frame("volume").to_csv(f); print(f"{name}: {len(v)} rows")
print("done")

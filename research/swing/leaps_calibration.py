"""Entry 117 check: today's real 1-year call quotes on the 3x funds vs the LEAPS model's assumptions.

    python3 -m research.swing.leaps_calibration
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.swing.study_3x_family import read  # noqa: E402

BULLS = "UPRO TQQQ UDOW URTY TECL SOXL FAS ERX LABU NUGT JNUG GUSH DRN CURE NAIL DPST RETL DUSL UTSL DFEN WEBL HIBL EDC YINN KORU TMF BULZ GDXU OILU".split()


def opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    try:
        op.open("https://fc.yahoo.com", timeout=20)
    except Exception:
        pass
    crumb = op.open("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=20).read().decode()
    return op, crumb


def main():
    op, crumb = opener()
    rows = []
    for s in BULLS:
        base = f"https://query2.finance.yahoo.com/v7/finance/options/{s}?crumb={crumb}"
        try:
            r = json.load(op.open(base, timeout=20))["optionChain"]["result"][0]
        except Exception as e:
            rows.append({"fund": s, "note": f"no chain ({str(e)[:30]})"}); continue
        S = r["quote"].get("regularMarketPrice")
        exps = r.get("expirationDates", [])
        now = time.time()
        far = [e for e in exps if (e - now) / 86400 >= 270]
        c = read(s)["close"]; lr = np.log(c).diff()
        rv60, rv252 = lr.tail(60).std() * np.sqrt(252), lr.tail(252).std() * np.sqrt(252)
        if not far:
            rows.append({"fund": s, "price": S, "longest expiry (days)": round((max(exps) - now) / 86400) if exps else 0,
                         "note": "no LEAPS (nothing 9+ months out)", "model IV 60d": rv60 * 1.1, "model IV 1y": rv252 * 1.1})
            continue
        e = min(far, key=lambda x: abs((x - now) / 86400 - 365))
        time.sleep(0.4)
        ch = json.load(op.open(base + f"&date={e}", timeout=20))["optionChain"]["result"][0]["options"][0]["calls"]
        atm = min(ch, key=lambda q: abs(q["strike"] - S))
        bid, ask = atm.get("bid", 0) or 0, atm.get("ask", 0) or 0
        mid = (bid + ask) / 2 if bid and ask else np.nan
        rows.append({"fund": s, "price": S, "expiry (days)": round((e - now) / 86400), "strike": atm["strike"],
                     "bid": bid, "ask": ask, "half-spread %": (ask - bid) / 2 / mid * 100 if mid == mid else np.nan,
                     "open interest": atm.get("openInterest", 0), "market IV": atm.get("impliedVolatility"),
                     "model IV 60d": rv60 * 1.1, "model IV 1y": rv252 * 1.1, "contract cost $": ask * 100})
        time.sleep(0.4)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(df.round(3).to_string(index=False))
    df.to_csv(ROOT / "research" / "swing" / "leaps_calibration.csv", index=False, float_format="%.4f")
    q = df.dropna(subset=["market IV"])
    q = q[q["bid"] > 0]
    print(f"\nwith two-sided quotes: {len(q)} funds; median market IV / model IV (60d) {np.median(q['market IV'] / q['model IV 60d']):.2f}, "
          f"/ model IV (1y) {np.median(q['market IV'] / q['model IV 1y']):.2f}; median half-spread {q['half-spread %'].median():.1f}%")


if __name__ == "__main__":
    main()

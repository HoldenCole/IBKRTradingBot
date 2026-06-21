"""LOCAL-RUN SCRIPT for the user's Windows machine (where NDU is installed).

Run this from a Windows command prompt or PowerShell after:
    pip install norgatedata

It pulls all 13 commodity continuous contracts from Norgate's local database
via the norgatedata Python package — no Exporter GUI, no c:\\NDExport, no
VirtualStore. Each instrument is saved as two CSVs:
    <ROOT>_norgate_backadj.csv   — back-adjusted continuous (the tradeable series)
    <ROOT>_norgate_unadj.csv     — unadjusted "current" continuous (cross-check
                                   against our Panama implementation)

Output folder is created next to this script: ./norgate_export/

Then zip that folder and upload it to the assistant.

If norgatedata is missing or NDU isn't running, the script prints a helpful
error and exits cleanly — won't write partial data.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# ---- 13 commodity instruments per the research spec ------------------------
# Norgate continuous-contract symbology: & prefix + root + adjustment suffix.
# _CCB = Continuous Contract Back-adjusted (Panama-style by default)
# _CCS = Continuous Contract Spliced (unadjusted "current" series, with gaps)
# Roots verified from Norgate's standard symbol table.
INSTRUMENTS = [
    # (Norgate root, our internal root, label, sector)
    ("CL",  "CL",  "WTI crude",        "Energy"),
    ("RB",  "RB",  "RBOB gasoline",    "Energy"),
    ("HO",  "HO",  "Heating oil",      "Energy"),
    ("NG",  "NG",  "Natural gas",      "Energy"),
    ("BRN", "BZ",  "Brent crude",      "Energy"),     # ICE — new
    ("GC",  "GC",  "Gold",             "Precious"),
    ("SI",  "SI",  "Silver",           "Precious"),
    ("HG",  "HG",  "Copper",           "Industrial"),
    ("ZC",  "ZC",  "Corn",             "Grains"),
    ("ZS",  "ZS",  "Soybeans",         "Grains"),
    ("ZW",  "ZW",  "Wheat",            "Grains"),
    ("SB",  "SB",  "Sugar #11",        "Softs"),      # ICE — new
    ("KC",  "KC",  "Coffee C",         "Softs"),      # ICE — new
]

START = "2000-01-01"
END   = "2026-06-30"   # Norgate updates through latest session — clamp upper

OUT_DIR = Path(__file__).resolve().parent / "norgate_export"


def main() -> int:
    # ---- Sanity: norgatedata available? --------------------------------
    try:
        import norgatedata as nd
    except ImportError:
        print("ERROR: 'norgatedata' package is not installed.")
        print("Install it first:  pip install norgatedata")
        return 2

    # ---- Sanity: NDU running? -----------------------------------------
    # norgatedata talks to a local service the NDU app provides. If NDU
    # isn't running we get a connection error on the first call.
    try:
        # A cheap probe: ask for the data range of WTI crude.
        nd.last_price_update("&CL_CCB")
    except Exception as exc:
        msg = repr(exc)[:200]
        print("ERROR: cannot reach Norgate Data via norgatedata.")
        print(f"  ({msg})")
        print()
        print("Make sure NDU (Norgate Data Updater) is running and your")
        print("subscription/trial is active. Then re-run.")
        return 3

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing CSVs to: {OUT_DIR}")
    print(f"Date range: {START} -> {END}")
    print(f"Instruments: {len(INSTRUMENTS)} continuous contracts, x2 variants each")
    print()

    summary = []
    fmt = "pandas-dataframe"

    for ng_root, our_root, label, sector in INSTRUMENTS:
        for variant in ("CCB", "CCS"):     # back-adjusted, then unadjusted
            symbol = f"&{ng_root}_{variant}"
            try:
                df = nd.price_timeseries(
                    symbol=symbol,
                    start_date=START,
                    end_date=END,
                    timeseriesformat=fmt,
                    # Use default padding (no fill) so we see the true series
                    padding_setting=nd.PaddingType.NONE,
                )
            except Exception as exc:
                print(f"  {symbol:<14} FAILED: {repr(exc)[:80]}")
                summary.append((our_root, variant, "FAIL", 0, "", ""))
                continue

            if df is None or len(df) == 0:
                print(f"  {symbol:<14} EMPTY")
                summary.append((our_root, variant, "EMPTY", 0, "", ""))
                continue

            # Normalize column names to lowercase + canonical order
            df = df.rename(columns=str.lower)
            keep = [c for c in ("open", "high", "low", "close", "volume",
                                "open interest", "delivery month")
                    if c in df.columns]
            df = df[keep]
            df.index.name = "date"

            tag = "backadj" if variant == "CCB" else "unadj"
            out_path = OUT_DIR / f"{our_root}_norgate_{tag}.csv"
            df.to_csv(out_path)
            first = df.index[0].date().isoformat()
            last  = df.index[-1].date().isoformat()
            summary.append((our_root, variant, "OK", len(df), first, last))
            print(f"  {symbol:<14} -> {out_path.name:<28} {len(df):>5} bars  "
                  f"{first}..{last}")

    # ---- Summary ------------------------------------------------------
    print()
    print("=" * 78)
    print("# SUMMARY")
    print("=" * 78)
    ok = sum(1 for r in summary if r[2] == "OK")
    print(f"  {ok} of {len(summary)} CSVs written successfully "
          f"({len(INSTRUMENTS)} instruments x 2 variants = {len(summary)} expected)")
    if ok < len(summary):
        print("  Failures:")
        for r in summary:
            if r[2] != "OK":
                print(f"    {r[0]} {r[1]} -> {r[2]}")

    print()
    print(f"Output folder: {OUT_DIR}")
    print("Next step: zip that folder and upload to the assistant.")
    return 0 if ok == len(summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())

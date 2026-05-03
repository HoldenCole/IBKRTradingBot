"""OFF-vehicle comparison: SGOV vs USFR vs SHV vs BIL.

Compares the four candidate OFF-period parking ETFs on the dimensions that
matter for our use case (deploy as the OFF leg of BAH-on-trend on QQQ):

  1. Effective yield (total return CAGR over 2020-2026 — captures full
     rate-cycle behavior including ZIRP, hike cycle, and current normal)
  2. Bid-ask spreads (using Yahoo daily OHLC as proxy — high-low range as
     a rough liquidity indicator)
  3. Drawdown during stress periods (March 2020, 2022)
  4. Inception date and AUM scale (longer history + higher AUM = stickier
     market)

What this script CAN'T verify (need ETF prospectus reading):
  - 1099-DIV reporting complexity (foreign tax credits, return-of-capital)
  - AP redemption fee structure during market stress
  - Securities lending policies

But for the four candidates here, all are domestic Treasury ETFs from
major issuers (BlackRock x2, WisdomTree, SPDR), so 1099 complexity is
expected to be uniform — Box 1a (ordinary dividends) or 1b (qualified
ordinary), no foreign tax credit, no MLP K-1 issues.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from loguru import logger
logger.remove()

import pandas as pd

from src.backtest.benchmark import equity_metrics
from src.data import yahoo


CANDIDATES = [
    ("SGOV", "iShares 0-3 Month Treasury Bond ETF",   "BlackRock",   0.07),
    ("BIL",  "SPDR Bloomberg 1-3 Month T-Bill ETF",   "SPDR",        0.14),
    ("SHV",  "iShares Short Treasury Bond ETF",       "BlackRock",   0.15),
    ("USFR", "WisdomTree Floating Rate Treasury Fund","WisdomTree",  0.15),
]


def load_etf_total_return(sym: str, start: date, end: date) -> pd.DataFrame:
    """Load ETF total-return data via auto_adjust=True (dividend-reinvested
    closes). Required for yielding ETFs like SGOV/BIL/SHV/USFR where most
    of the return is paid out as distributions, not price appreciation.
    """
    import yfinance as yf
    df = yf.download(sym, start=start.isoformat(), end=end.isoformat(),
                     progress=False, auto_adjust=True, group_by="column")
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    # Flatten multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["open", "high", "low", "close", "volume"]]


def relative_spread_proxy(df: pd.DataFrame) -> float:
    """Yahoo OHLC doesn't expose bid-ask. Use median (high - low) / close
    over the last year as a rough liquidity proxy. Lower = tighter market
    (less intraday range).
    """
    sub = df.tail(252)  # last ~year
    rng_pct = (sub["high"] - sub["low"]) / sub["close"]
    return float(rng_pct.median())


def stress_event_dd(df: pd.DataFrame, start: date, end: date) -> tuple[float, float]:
    """Returns (total_return, max_dd) over the event window."""
    idx = [d.date() if hasattr(d, "date") else d for d in df.index]
    mask = pd.Series([start <= d <= end for d in idx], index=df.index)
    sub = df.loc[mask]
    if sub.empty or len(sub) < 2:
        return 0.0, 0.0
    px = sub["close"]
    ret = float(px.iloc[-1] / px.iloc[0] - 1.0)
    dd = float(((px.cummax() - px) / px.cummax()).max())
    return ret, dd


STRESS_EVENTS = [
    ("March 2020 COVID liq-crisis", date(2020, 3, 1),  date(2020, 4, 30)),
    ("2022 inflation regime",       date(2022, 1, 3),  date(2022, 12, 31)),
    ("2023 banking stress",         date(2023, 3, 1),  date(2023, 5, 31)),
    ("2024-2026 normal regime",     date(2024, 1, 1),  date(2026, 4, 14)),
]


def main() -> int:
    full_start = date(2014, 1, 1)
    full_end = date(2026, 4, 14)

    print(f"\n{'='*100}")
    print("# OFF-vehicle comparison: SGOV vs USFR vs SHV vs BIL")
    print('='*100)

    print(f"\n{'Symbol':>6s}  {'Inception':>12s}  {'Bars':>6s}  {'Expense':>8s}  "
          f"{'TR CAGR':>8s}  {'Vol':>6s}  {'|DD|':>5s}  {'Range %':>8s}")

    data = {}
    for sym, name, issuer, exp_ratio in CANDIDATES:
        df = load_etf_total_return(sym, full_start, full_end)
        if df.empty:
            print(f"  {sym}: NO DATA")
            continue
        data[sym] = df
        # Total-return CAGR over the available history
        if len(df) < 250:
            inception_label = f"{df.index[0].date()} (insufficient)"
            print(f"  {sym:>6s}  {inception_label:>12s}  {len(df):>6d}  "
                  f"{exp_ratio:>7.2f}%   --      --      --      --")
            continue

        # 2020-2026 sub-period (full rate cycle)
        post_2020 = df[df.index >= "2020-01-01"]
        if len(post_2020) >= 250:
            tr_cagr_2020 = (post_2020["close"].iloc[-1] / post_2020["close"].iloc[0]) ** (
                252 / len(post_2020)) - 1
        else:
            tr_cagr_2020 = float("nan")

        rets = df["close"].pct_change().fillna(0.0)
        vol = float(rets.std() * (252 ** 0.5))
        max_dd = float(((df["close"].cummax() - df["close"]) / df["close"].cummax()).max())
        spread_proxy = relative_spread_proxy(df) * 100

        print(f"  {sym:>6s}  {df.index[0].date().isoformat():>12s}  {len(df):>6d}  "
              f"{exp_ratio:>7.2f}%  {tr_cagr_2020 * 100:>+5.2f}%  {vol * 100:>4.2f}%  "
              f"{max_dd * 100:>4.1f}%  {spread_proxy:>6.3f}%")

    # ----- Stress events -----
    print("\n" + '='*100)
    print("# Stress-event behavior (total return + max DD per window)")
    print('='*100)

    print(f"\n{'Event':>30s}  ", end="")
    for sym, _, _, _ in CANDIDATES:
        print(f"{sym:>16s}  ", end="")
    print()
    print(f"{'':>30s}  ", end="")
    for _ in CANDIDATES:
        print(f"{'TR / |DD|':>16s}  ", end="")
    print()

    for elabel, ps, pe in STRESS_EVENTS:
        print(f"  {elabel:>28s}  ", end="")
        for sym, _, _, _ in CANDIDATES:
            df = data.get(sym)
            if df is None or df.empty:
                print(f"{'(no data)':>16s}  ", end="")
                continue
            ret, dd = stress_event_dd(df, ps, pe)
            print(f"  {ret * 100:>+5.2f}% / {dd * 100:>4.1f}%  ", end="")
        print()

    # ----- Pairwise analysis -----
    print("\n" + '='*100)
    print("# Pairwise correlation of daily returns (post-2020)")
    print('='*100)

    rets_df = pd.DataFrame()
    for sym, _, _, _ in CANDIDATES:
        if sym in data:
            df = data[sym]
            rets_df[sym] = df["close"].pct_change()
    rets_df = rets_df.dropna()
    rets_2020 = rets_df[rets_df.index >= "2020-01-01"]
    print(f"\n  Sample size: {len(rets_2020)} days (2020-01-01 onward)\n")
    print(rets_2020.corr().round(4).to_string())

    # ----- Recommendation table -----
    print("\n" + '='*100)
    print("# Issuer / structure summary")
    print('='*100)

    print(f"\n{'Sym':>4s}  {'Issuer':>10s}  {'Maturity':>14s}  {'Floating?':>9s}  "
          f"{'Expense':>8s}  {'Notes':<40s}")
    rows = [
        ("SGOV", "BlackRock",  "0-3 month",  "No",  "0.07%",
         "Lowest expense ratio. Newest fund (2020)."),
        ("BIL",  "SPDR",       "1-3 month",  "No",  "0.14%",
         "Largest AUM among candidates. Long history (2007)."),
        ("SHV",  "BlackRock",  "≤ 1 year",   "No",  "0.15%",
         "Slightly longer maturity → small duration risk."),
        ("USFR", "WisdomTree", "Floating",   "Yes", "0.15%",
         "Resets every 3 months → rate-rise resistant."),
    ]
    for r in rows:
        print(f"  {r[0]:>4s}  {r[1]:>10s}  {r[2]:>14s}  {r[3]:>9s}  "
              f"{r[4]:>8s}  {r[5]:<40s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

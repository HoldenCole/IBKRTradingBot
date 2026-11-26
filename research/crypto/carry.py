"""C1 — funding carry, measured (CRYPTO.md, study 1). Descriptive, not a rule test.

The trade: hold the coin spot and short the same amount of its perpetual future, so the price moves
cancel and the short collects funding when funding is positive (and pays when negative).

Measured on Binance USD-M perpetuals (2020 on; a US person cannot trade there, but it is the deepest
record of what the market pays), Hyperliquid (2023 on) and Kraken futures (last 12 months).

Costs: one round trip of both legs. "low" = 0.25% a side on spot plus 0.05% on the perp (IBKR-like
spot), 0.60% a round trip; "high" = 0.40% plus 0.05% (Kraken Pro entry tier), 0.90%.
Capital: the spot leg is paid in full and the perp short needs margin, so the return on capital is
funding / (1 + 1/L) for a perp margined at L times. At L = 1 the capital earns half the funding.

    python3 -m research.crypto.carry
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.crypto.data import COINS, binance_funding, hyperliquid_funding, kraken_funding

RT = {"low": 0.006, "high": 0.009}


def yearly(fr: pd.DataFrame) -> pd.DataFrame:
    y = fr.groupby(fr.time.dt.year)["rate"]
    return pd.DataFrame({"funding": y.sum(), "negative_share": y.apply(lambda s: (s < 0).mean()), "events": y.size()})


def switched(fr: pd.DataFrame, events_per_day: int, on=0.10, off=0.0, rt=0.006) -> pd.DataFrame:
    """On when the trailing 7-day funding, annualised, is above `on`; off when it falls below `off`.
    Decided on past funding only; each switch on or off pays half a round trip."""
    r = fr.set_index("time")["rate"]
    w = 7 * events_per_day
    ann = r.rolling(w).mean().shift(1) * events_per_day * 365
    held = np.zeros(len(r)); h = 0
    for i, a in enumerate(ann.values):
        if not np.isfinite(a):
            continue
        if not h and a > on:
            h = 1
        elif h and a < off:
            h = 0
        held[i] = h
    held = pd.Series(held, index=r.index)
    pnl = held * r - held.diff().abs().fillna(held.iloc[0]) * rt / 2
    g = pnl.groupby(pnl.index.year)
    return pd.DataFrame({"net": g.sum(), "time_on": held.groupby(held.index.year).mean()})


def main():
    pd.set_option("display.width", 220)
    tab, sw = {}, {}
    for c in COINS:
        fr = binance_funding(c)
        per_day = int(round(len(fr) / ((fr.time.iloc[-1] - fr.time.iloc[0]).days)))
        tab[c] = yearly(fr)["funding"]
        sw[c] = switched(fr, max(per_day, 3), rt=RT["low"])["net"]
    t = pd.DataFrame(tab).T
    print("Binance USD-M perpetuals: funding collected by a short, % of notional per calendar year (2026 to date)")
    print((t * 100).round(1).to_string())
    print("\nmedian across the ten coins:", (t.median() * 100).round(1).to_dict())
    print("\nAlways on, after one round trip a year (low / high cost), median coin, % of notional:")
    print(f"   low  {((t.median() - RT['low']) * 100).round(1).to_dict()}")
    print(f"   high {((t.median() - RT['high']) * 100).round(1).to_dict()}")
    s = pd.DataFrame(sw).T
    print("\nSwitched (on above 10% a year trailing 7 days, off below 0), net of switching costs, % of notional:")
    print((s * 100).round(1).to_string())
    neg = pd.DataFrame({c: yearly(binance_funding(c))["negative_share"] for c in COINS}).T
    print("\nShare of funding events that were negative (the short pays):")
    print((neg * 100).round(0).to_string())

    for c in ("BTC", "ETH"):
        h = hyperliquid_funding(c)
        print(f"\nHyperliquid {c} (hourly funding), % of notional per year: {(yearly(h)['funding'] * 100).round(1).to_dict()}")
    for sym in ("PF_XBTUSD", "PF_ETHUSD", "PF_SOLUSD"):
        try:
            k = kraken_funding(sym)
            span = (k.time.iloc[-1] - k.time.iloc[0]).days
            print(f"Kraken {sym}: last {span} days, funding {k.rate.sum() * 100:+.2f}% of notional "
                  f"(annualised {k.rate.sum() * 365 / span * 100:+.1f}%), negative {(k.rate < 0).mean():.1%} of hours")
        except Exception as e:
            print(f"Kraken {sym}: {e}")
    def _last12(c):
        f = binance_funding(c)
        return f[f.time > f.time.iloc[-1] - pd.Timedelta(days=365)].rate.sum()
    last12 = {c: _last12(c) for c in COINS}
    print("\nBinance, last 12 months of data, % of notional:", {k: round(v * 100, 1) for k, v in last12.items()})
    print("Return on capital = funding / (1 + 1/L): at L=1 half the funding, at L=3 three quarters.")
    t.to_csv("research/crypto/carry_binance_yearly.csv", float_format="%.5f")


if __name__ == "__main__":
    main()

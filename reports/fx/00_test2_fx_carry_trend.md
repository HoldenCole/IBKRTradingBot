# FX Test 2 — Carry + Trend on G6 CME FX futures

**Date:** 2026-06-22
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_fx_test2.py`
**Raw output:** `RESULTS_test2.txt`
**Universe:** 6E (EUR), 6J (JPY), 6B (GBP), 6A (AUD), 6C (CAD), 6N (NZD)
— Databento 2010-2026

## Verdict — TIER D across the board, all three lines fail

| Strategy | CAGR | Sortino | MaxDD | Stress wins (of 5) | Equity corr | Tier |
|---|---:|---:|---:|:--:|---:|:--:|
| Trend 50/200 (long-flat) | −2.0% | −0.62 | 34% | 3/5 | +0.15 | **D** |
| Carry (long-short, basis-driven) | −4.0% | −0.82 | 58% | **1/5** | +0.12 | **D** |
| Combined 50/50 | −2.9% | −0.99 | 46% | 2/5 | +0.17 | **D** |

All three lose money over 2010-2026. Correlations with equities are slightly
positive (the *wrong* sign for a diversifier — we wanted negative). The
locked Tier-A criterion required Sortino > 1.0, ≥3 of 5 stress wins, and
correlation < 0.3; none of the three came close.

## The textbook FX-carry failure mode is in the data

Pre-flight sanity check confirmed the signal direction is correct (AUD =
positive basis = long the high-yielder; JPY = negative basis = short the
low-yielder, classic carry positioning). The signal isn't bugged. Carry is
genuinely losing money the way it's expected to lose money:

| Equity-stress window | Carry P&L | Equity P&L |
|---|---:|---:|
| 2018-Q4 correction | **+3.5%** | −22.8% |
| 2020 March COVID | **−2.7%** | −16.3% |
| 2022 inflation bear | **−6.9%** | −32.4% |
| 2024-Aug yen unwind | **−2.0%** | +3.8% |
| 2025 Liberation Day | −1.1% | +2.3% |

Carry made money in only 1 of 5 stress windows, and it **lost in all three
of the actual risk-off episodes** (COVID, 2022, yen unwind). This is the
canonical FX-carry behavior: long high-yielders / short low-yielders pays
slowly for years, then crashes catastrophically when risk-off forces
unwinds. The 2010-2026 window happened to be one where the crashes
exceeded the carry, netting −4% CAGR. **And critically, the crashes happen
exactly when equities are also down** — which is the opposite of what a
diversifier needs.

The Aug 2024 yen unwind (specifically called out in the spec) shows the
mechanism in microcosm: −2.0% in a few days while equities barely moved.

## Trend on FX also doesn't work

Trend lost −2% CAGR over the 16 years. The 50/200 rule that works on
equities and (partially) on commodities doesn't transfer to FX — currency
pairs are largely mean-reverting around interest-rate-differential anchors,
with no structural drift for trend to capture. Vol is low (4%) but the
calm-period whipsaws still outpace the small wins, much like the bond
trend result.

The trend signal *did* manage 3/5 stress wins (it sits in cash during
choppy crisis periods) but only by tiny amounts (+0.5%, +0.6%, +1.1%) — and
even those barely-positive results are noise around zero. It's not really a
diversifier; it's a do-nothing strategy.

## What this confirms about the broader diversifier search

This was Test 2 of a sequential gate: bonds (Test 1) failed Tier B, FX
(Test 2) was the conditional next candidate, and FX has now also failed
Tier B. Combined with everything before it, the project has tested **roughly
9-10 separate diversifier candidates** under disciplined methodology:

- IBS long-short / overnight drift / VIX spike fade (early equity rounds)
- Inverse-ETF OFF / IBS shorts overlay (equity rounds)
- Commodity trend long-flat (V1 SMA / V2 Donchian / V3 vol-adj momentum)
- Commodity trend long-short (V3 LS)
- Commodity carry
- Bond trend
- FX trend / FX carry / FX combined

**All but one failed Tier B as standalone deployables.** The single
near-miss was long-short V3 commodity trend, deferred to the $25k+ multi-
strategy point but explicitly not classified as Tier-B-clean.

## The honest conclusion

Per the master plan I locked at the start of this two-test round:

> If both bonds and FX fail to clear Tier B, that's a meaningful negative
> finding. It would suggest finding clean equity-stress diversifiers among
> the asset classes available to retail systematic trading is genuinely
> hard. The multi-strategy book is going to be two long-biased components
> (equity trend, BTC trend) plus T-bills during OFF periods, with no
> separate crisis hedge. That's an acceptable outcome — it would just mean
> the portfolio drawdown profile during equity bears is "both strategies in
> T-bills earning yield" rather than "diversifier strategy actively
> profiting."

**This outcome has now happened.** Take the pre-committed conclusion: the
deployable portfolio is **equity trend (QQQ 50/200, T-bill OFF) + BTC trend
(50/200, T-bill OFF, deployed via IBIT now, MBT at $25k+)**. There is no
separate crisis-hedge sleeve. During equity bears, both strategies sit in
T-bills earning yield — which is a defensible, low-drawdown profile, just
not the "diversifier actively profiting" profile we hoped to find.

## Caveats and honest limitations

- **2010-2026 is a low-rate-differential era for FX** (most of the period
  had near-zero developed-market rates, compressing carry). Pre-2008 had
  bigger rate differentials and stronger carry returns. Our data can't
  reach that period.
- **The locked carry threshold (±5 bps monthly)** is symmetric and may be
  suboptimal for the very small post-2015 rate differentials. Per one-look
  discipline, no tuning. A second-look round might find a less-bad
  parameter, but the *direction* of the result (loses in stress) is
  structural to carry and won't be tuned away.
- **Trend on FX is well-known to be weak academically** (e.g., Asness et
  al.); this is a confirmation, not a surprise.
- **Survivorship of paired currencies** isn't an issue here — these six
  are the same major-rate pairs through the whole period; no selection
  bias.

## Status

FX Test 2 closed. Sequential gate complete: bonds Tier D, FX Tier D, no
deployable equity-stress diversifier found. Move to deployment focus on
the equity + BTC sleeves with T-bill as the OFF treatment.

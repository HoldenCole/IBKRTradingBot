# CL Surge → USO Calls (the hand-trade, systematized)

Origin: the user's discretionary trade — "if CL1 trades up more than a certain percent, buy USO calls $1–2 OTM at a mid limit and wait" — which made money traded by hand. This doc records the investigation that validated *when* that rule works, and the v1 spec that systematizes it.

Status: **candidate — signal module built, awaiting parameter confirmation + paper validation.** Not live. See "Evidence" for exactly how strong (and weak) the statistics are.

---

## What the investigation found (2026-08-17)

Tested on ~580 trading days of hourly data (2024-03 → 2026-08) and 10 years of daily data. Full detail in the session that produced this doc; headline numbers:

### The raw hand-rule works — but only in the current regime

USO forward returns after an overnight CL up-move (non-overlapping events, 5-session holds):

| Sample | Trigger | n | Mean 5d return | t |
|---|---|---|---|---|
| 2024–2026 (precise overnight) | CL up >1% | 66 | +77 bps | 1.09 |
| 2024–2026 | CL up >2% | 30 | +204 bps | 1.44 |
| 10y daily (stale trigger) | CL up >2% | 228 | **−11 bps** | −0.28 |

Per-year (2024–2026 sample, >1% trigger): 2024 +45 bps, 2025 −3 bps, **2026 +213 bps**. The hand-trading profits are real and consistent with the data — they came from 2026's strong oil uptrend. Unfiltered across a decade, the rule has no edge (2020–22: −62 bps/event).

- Same-day holds are ~zero at every threshold — **the "wait" (multi-day hold) is essential**.
- Symmetry check: after CL *down* >1%, forward returns ≈ baseline — the continuation is asymmetric (up-moves only), consistent with trend persistence rather than a generic lag.

### A trend filter makes it era-stable

Same 10-year test, trigger CL up >2%, hold 5 sessions, non-overlapping:

| Filter | n | Mean | 2016-19 | 2020-22 | 2023-26 | t |
|---|---|---|---|---|---|---|
| none | 228 | −11 bps | +9 | −62 | +28 | −0.28 |
| CL > SMA50 | 142 | +36 bps | −8 | +68 | +34 | 0.82 |
| **CL > SMA50 AND SMA50 > SMA200** | **77** | **+65 bps** | **+102** | **+58** | **+46** | **1.08** |

The uptrend filter alone (no surge trigger) yields only +10 bps/5d — the surge adds real selection within uptrends. Positive in all three eras is the key property; none of the unfiltered variants achieve it.

### Honest statistical assessment

t ≈ 1.1 with 77 events in 10 years is **suggestive, not significant**. The economics are plausible (this is energy trend-following with a breakout trigger — the mechanism behind 50 years of CTA returns, and the same family as `New Trading Strats`' Variant 2). The options expression adds convexity: modeled OTM calls turned the 2024–26 sample's drift into ~$250–550 avg per $1k premium per event (t ≈ 2.2–2.4 *with overlapping events* — the non-overlap t is the honest one). This must earn its way through paper trading; the backtest alone does not justify live capital.

---

## v1 Specification

### Signal (evaluated once daily at 9:30 ET)

ALL required:

1. **Surge:** overnight CL1 return (prior 16:00 ET → 9:30 ET) > **+2.0%**
2. **Trend:** CL close > SMA(50) AND SMA(50) > SMA(200) on daily closes
3. Not already holding a position from a prior signal (one position at a time)
4. Daily-loss kill switch not tripped; weekly budget has room

### Execution

- Buy **USO calls, strike ≈ spot + $1.50** (nearest listed strike $1–2 OTM)
- **Target DTE 14** (min 10) — must cover the 5-session hold without gamma-bleed panic
- **LIMIT at mid** (the user's hand practice; chase ladder per STRATEGIES.md if unfilled)
- Premium budget per trade: **$1,000** → contracts = floor(budget / (premium × 100))

### Exits (first applicable)

1. **−50% premium stop** (checked daily at close; the one addition to the hand rule — "wait" must not mean "ride to zero")
2. **+100% premium → sell half**, let the rest run to the time exit
3. **Time exit: close of the 5th session** after entry
4. Hard exit at 5 DTE regardless (never hold into expiry week)

### Open questions for the user (blocking go-live, not blocking paper)

- Surge threshold: analysis supports 2%; is that what you used by hand?
- Confirm the trend filter is acceptable — it will make the bot *decline* trades you might have taken by hand in downtrends. That filter is where the 10-year survivability comes from.
- Hold length: analysis used 5 sessions; drift keeps accruing to ~10 but with much lumpier outcomes (win rate drops to ~34%, tail-driven).

### Validation gate

1. ≥ 15 paper trades (at ~8 filtered events/year, seed paper with smaller 1% threshold to accumulate sample faster, then tighten)
2. Positive expectancy after real option spreads/fills
3. At least one −50% stop and one +100% scale-out observed working

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

### The intraday-only variant (the user's actual hand trade)

Clarified 2026-08-17: the hand trade is intraday — CL1 crosses +X% *during the session*, buy the calls, out same day. Tested as: first intraday crossing of +1/1.5/2% (vs prior 16:00 ET CL) → buy USO at that bar → exit EOD or +2h.

| Sample | Cross +1.5% → EOD | n | Win |
|---|---|---|---|
| Last 20 days (1-min) | **+61 bps** | 10 | 70% |
| Last 60 days (30-min) | **+67 bps** | 18 | 61% |
| Full 2.4 years (hourly) | **−0.0 bps** | 182 | 54% |

- By year (2.4y sample): 2024 +9 bps, 2025 −6 bps, **2026 full-year −1 bps** — even 2026 as a whole is flat; the profits are concentrated in roughly the last two months (July–Aug 2026 oil tape).
- Methodology checks: hourly data on the last 60 days reproduces the recent edge (+46 bps), so the flat long-run result is not a granularity artifact. Entry speed matters — the edge decays +61 → +33 → +16 bps with 0/30/60-min entry delays — so an automated version must buy within minutes of the crossing.
- The trend filter does **not** rescue the intraday variant (uptrend days: +0.4 bps over 2.4y). Unlike the multi-day hold, same-day continuation has no era-stable expression found in this analysis.

#### The same-hour scalp variant (full hand-trade mechanics)

Further clarified: the actual hand trade uses *small* triggers (~0.5% or less), exits the moment CL turns, adds when CL dips and resumes, holds usually within the hour, max 4 hours. Mechanical translation tested:

- **CL-flip exit** (close when CL retraces 0.2–0.3% from its post-entry high): fires on noise within a median of 5–17 minutes on every event — captures ~0 bps even on the favorable recent tape. CL's routine minute-scale wiggle is the same size as the exit trigger; "the trend changed" cannot be distinguished from noise at this threshold mechanically.
- **Control on the same entries** (recent 20 days): plain 1–2h fixed holds made +31 to +51 bps — on this tape, the sitting was the profit, and the fast exit was a cost.
- **Long-run, short holds** (2.4y, entry at +0.5% intraday crossing): 1h hold **−6.7 bps**/event (t=−1.7), 2h hold −6.2 bps — negative in *every year*, including 2026. After option spreads, decisively negative.

**Verdict on the same-hour scalp:** no mechanical edge found in any sample, including the period where the hand trading was profitable. The hand P&L is attributable to discretionary tape/day selection (plus favorable limit fills) on a small number of trades in a hot tape — which is a skill, but not one this rule specification captures. Do not automate as described.

**Verdict on intraday-only:** the recent hand-trading profits are genuine — the last ~2 months paid this trade well — but 2.4 years of data says it is a hot streak in a favorable tape, not a durable standalone edge. After option spreads it is net-negative in expectation over the full sample. The durable expression of the same instinct is the multi-day trend-filtered version above. Recommended path: paper-trade both variants in parallel and let live forward data decide; do not put real money on the intraday variant on the strength of the recent streak.

### Systematic grid sweep (2026-08-17)

264 variants tested on the 2.4y hourly sample (`research/grid_2024_2026_hourly.csv`): direction families {follow-long, follow-short, fade-long, fade-short} × trigger {move since prior 16:00, rolling 1h move} × thresholds {0.3–2%} × exits {1h/2h/4h/EOD holds, 0.5%/1% trailing stops}. Pre-registered pass rule: positive in every year, not just overall. At |t|>2, ~13 false positives are expected by chance from a grid this size.

**Family verdicts:**

- **Follow (CL up → long USO / CL down → short USO)** — the lead-lag thesis: no era-stable variant above +12 bps; the core cells are flat to negative every year. Trailing stops do not rescue it. Leverage/size scale PnL linearly and cannot change its sign.
- **Fade-short (CL up → short USO):** weakly positive (+4–7 bps/event), not compelling after costs.
- **Fade-long (CL down ≥1–2% intraday → long USO, hold to EOD):** the only strong cluster — +43 bps/event at the 2% threshold (t=3.2, n=131, win 60%, positive all three years: +26/+34/+63), robust across thresholds and every exit style including trailing stops (+34 bps, t=2.5). BUT: (a) the 2.4y sample contains no crash regime, and fading oil selloffs is precisely the trade that dies in one; (b) the 10-year daily cousin (CL down >2% yesterday → long USO open→close) is negative in **every era** with a worst day of −7.2%; (c) the recent 60 days confirm only weakly (+11 bps). Status: **research candidate only.** Requires 5+ years of intraday data (through 2020 and 2022) before any capital, paper included.
- **Pair spread (long USO / short CL exposure on z-divergence):** already tested exhaustively as the original strategy — no edge; USO/CL 1-min correlation 0.988 with zero lead-lag at every offset tested (±5 min, ±hours).

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

# Biotech Catalyst Research — Project Spec

Status: **research spec — no code, no backtest yet.** Explicitly a satellite idea: capped at a few % of portfolio if anything ever validates, never part of the quadrant rotation. This document locks the hypotheses, data plan, and decision criteria before any results exist (house rule).

## Compliance line (non-negotiable)

Every signal uses **public data only**: ClinicalTrials.gov registry updates, SEC filings (8-K announcements, Form 4 insider transaction reports), published results, and public media coverage. "Insider activity" means legally-filed Form 4 open-market transactions, nothing else. No MNPI, ever.

## What the literature already establishes

1. **The pre-catalyst run-up is real and large**: ~74% of the cumulative abnormal return around clinical-trial announcements accrues in the ~20 days BEFORE the announcement (Aalto event study). Small/mid-cap run-ups of 20–40% into PDUFA dates are commonly documented.
2. **The classic expression avoids the binary**: buy the run-up window, **exit before the readout** — capturing drift without predicting outcomes. "Sell the news" declines after positive events are well documented.
3. **Large caps move far less on readouts** (median announcement-day CAR +0.8% positive / −2.0% negative, PLOS One): the user's "weight toward larger companies" gets safety but must fight much smaller effect sizes. Test both cap tiers; expect the tradeable run-up to live in mid-caps.
4. **Execution drift leaks early**: enrollment shortfalls and timeline slips appear in registry updates weeks–months before companies admit problems (75% enrollment shortfall → ~53% termination odds). This is primarily an AVOID filter for longs (shorting binary-event biotech is not for this account).

## Data availability (verified live, 2026-08-21)

| Source | Verified | Gives us |
|---|---|---|
| ClinicalTrials.gov API v2 | ✓ free, structured | phase, sponsor, status, primary-completion dates (the catalyst calendar), results-posted dates, update history (execution-drift signal), enrollment |
| EDGAR full-text search (efts.sec.gov) | ✓ free | historical 8-K "topline results" announcements with dates → the backtest event dataset (~129 hits/2mo for one phrase → thousands over a decade) |
| EDGAR submissions/Form 4 | ✓ free | insider open-market buys per company |
| GDELT / news volume | not yet probed | media-attention leg (the user's "trending in the news" signal) |
| PDUFA calendars | partial/paid | supplement from 8-K/press releases where possible |

## Pre-registered hypotheses

- **H1 — Run-up harvest (core)**: a diversified basket long each name in a T−30→T−5 trading-day window before scheduled phase-3 primary-completion/PDUFA catalysts, exiting BEFORE the event, beats XBI after costs. (No outcome prediction required.)
- **H2 — Momentum-into-catalyst (the Moderna pattern)**: names with a prior positive readout in the same program + building media coverage outperform into the NEXT catalyst. (Continuation, not reversal.)
- **H3 — Execution-drift filter**: excluding names whose registry history shows timeline slips/enrollment shortfalls improves H1's hit rate.
- **H4 — Insider confirmation**: H1 names with officer/director open-market Form 4 buys in the prior 6 months outperform H1 names without.
- **H5 — Cap-tier split**: effect sizes by market cap (small/mid/large). Expectation from literature: mid-caps tradeable, large-caps muted.

## Decision criteria (locked before results)

Deployment candidate requires ALL: ≥100 events in the backtest; after-cost Sharpe > 0.7 vs XBI-hedged; no single event > 10% of total PnL; positive in both halves of the sample; H1 must pass before any overlay (H3/H4/H5) is credited. Anything less = interesting research, no money.

## Sizing & risk (if it ever deploys)

Satellite book: ≤ 5% of portfolio, no leverage, no options initially, position caps such that a −60% single-name event costs < 0.5% of portfolio, separate ledger. This strategy NEVER holds through a readout in v1.

## Honest effort estimate

The long pole is the **event dataset**: parsing dated 8-K announcements, linking to tickers/caps, and joining ClinicalTrials.gov histories — est. 2–3 working sessions before the first hypothesis test. Each hypothesis test after that: ~1 session. Recommend building H1's dataset first and stopping for review before overlays.


---

## Stage 1 results: event dataset + first event study (2026-08-21)

**Dataset built** (`research/biotech_events.csv`, `research/biotech_event_study.csv`): 1,640 dated topline-result 8-K events, 2017–2026, 344 biotech/pharma tickers (SIC-filtered), from EDGAR full-text search on four result phrases. 1,342 events had full price windows. Known biases, disclosed: 61 tickers unresolvable (delisted — mostly blowups; this biases results UPWARD, strengthening any negative finding); 9:1 pos/neg label skew (companies trumpet wins in 8-K language; failures use softer wording).

**Abnormal returns vs XBI:**

| Window | All events | Positive | Negative |
|---|---|---|---|
| T−30..T−5 (run-up) | −1.61% (t=−1.95) | −0.98% | **−7.91% (t=−2.10)** |
| T0..T+1 (announcement) | −1.27% | +1.79% (t=+2.54) | **−31.9% mean / −3.8% median** |
| T+2..T+20 (post) | **−3.52% (t=−6.00)** | **−3.09% (t=−5.18)** | −7.77% (t=−3.19) |

**Findings:**

1. **H1 (naive run-up harvest) FAILS on this design.** There is no positive pre-announcement drift on realized 8-K announcement dates — the literature's run-up applies to SCHEDULED, anticipated catalysts (PDUFA dates, guided readout windows), not to announcements-in-general, many of which are unscheduled. Stage 2 must use ex-ante scheduled dates (ClinicalTrials.gov completion dates / PDUFA calendar) before H1 can be judged; on this evidence the naive version is dead.
2. **Failures leak.** Names underperform XBI by ~8% in the month BEFORE a failure announcement — direct support for H3 (execution-drift/leakage) and for the AppliedXL thesis. The market smells bad trials.
3. **The strongest effect in the data is "sell the news" — even for good news.** After ANY topline announcement, names lag XBI by ~3–3.5% over the next month (t=−6.0, the most robust statistic in this study); after positive announcements specifically, −3.1% (t=−5.2). Tradeable implications: never buy the post-announcement pop; for holders, exiting into announcement strength beats holding for a month. As a systematic short it would need borrow-cost analysis — parked.
4. **The binary is as brutal as advertised**: negative announcements average −32% in two days (median −3.8%, i.e., catastrophic tails). The "never hold through a readout" sizing rule is quantitatively justified.

**Stage 2 (next):** build the SCHEDULED-catalyst calendar (ClinicalTrials.gov primary-completion dates joined to tickers) and re-test H1 on anticipated events only — the only version of the run-up hypothesis this data leaves alive.

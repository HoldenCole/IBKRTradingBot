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

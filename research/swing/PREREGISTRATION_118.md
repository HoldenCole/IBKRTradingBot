# Trend-following LEAPS on SOXL and TQQQ only: pre-registration (entry 118)

Written 2026-11-27 before any two-fund result below was computed. Nothing below may change after results are seen.

User direction: try LEAPS on just SOXL and TQQQ.

**Selection warning.** Entry 117 already showed these two among the best single-fund LEAPS results (SOXL +46%,
TQQQ +28% a year at 50% of the account). Picking them after seeing that makes every figure below optimistic. This
entry describes how the strategy behaves on them, what it would cost to buy today, and how much the result depends on
the pricing assumptions; it cannot confirm that the strategy works.

## Strategy (entry 117's L)

At a month-end close when the fund's close is above the average of its last 10 month-end closes and no calls are held,
put a fixed share of the sleeve into 12-month calls; sell at the first month-end when the trend is off or after 6
months held, and buy again if it is still on. Two sleeves, SOXL and TQQQ, equal weight, reset monthly. Idle cash earns
nothing. Black-Scholes with the entry 77 skew, half-spread 6.5% each side (entry 117's measured median), fractional
contracts.

Grid (all reported, 2011-2026 and the halves 2011-2017 and 2018-2026):
- share of the account in calls: 25%, 50%, 100%;
- strike: at the money, 20% out of the money;
- implied vol: 1.1 x 60-day realized, and 1.1 x 1-year realized.

Comparisons over the same days: buy and hold, the 10-month trend held in the funds themselves, and the live swing plan
through real UPRO/TQQQ.

## Checks

1. Today's quotes: the ask of TQQQ and SOXL calls about 12 months out at 100%, 110%, 120%, 130% and 150% of spot, and
   the model's price at the same strikes. This tests the skew assumption and shows what one contract costs.
2. A $1,000 account with $150 added each month, whole contracts only, TQQQ and SOXL ATM and 20% OTM with 1-year vol
   pricing: how often the plan could have bought even one contract.

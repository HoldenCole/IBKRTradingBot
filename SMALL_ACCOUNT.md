# The small live account: goal, evidence and where it stands

Last updated 2026-11-26. Evidence lives in `TESTS.md` (one line per test) and `PORTFOLIOS.md` (tables),
entries 89 to 100.

## The goal

- A separate IBKR account, funded with $1,000, plus about $150 a month.
- High risk and high return. Always levered, 3x by default (README working rule 8).
- Milestones: $50, then $100, then $200 a month in gains. $200 a month is the point where the account
  pays for itself.
- Constraints: IBKR still applies the $25,000 pattern-day-trader rule, so nothing that opens and closes on the
  same day in a margin account. Never short the broad US market. No margin account below $2,000.

## The arithmetic that decides the milestones

Return a year needed for each milestone (gain a month = balance x return / 12):

| balance | $50 a month | $100 a month | $200 a month |
|---|---|---|---|
| $2,000 | 30% | 60% | 120% |
| $5,000 | 12% | 24% | 48% |
| $10,000 | 6% | 12% | 24% |
| $20,000 | 3% | 6% | 12% |

Balance from $1,000 plus $150 a month:

| return a year | after 1 year | after 3 years | after 5 years |
|---|---|---|---|
| 12% | $3,017 ($30 a month) | $7,806 ($78) | $13,814 ($138) |
| 25% | $3,248 ($68) | $9,570 ($199) | $19,449 ($405) |
| 50% | $3,682 ($153) | $13,741 ($573) | $36,374 ($1,516) |

In the first two years the contributions move the balance more than any strategy does. Reaching $200 a month
inside about three years needs roughly 25% a year, held steadily.

## What was tested (entries 89 to 100)

| test | idea | best result | verdict |
|---|---|---|---|
| 89 | Swing plan (test 79) at $1,000 costs, 1x to 6x | 3x +14.4% CAGR / -38% max drawdown (with T-bill interest on idle cash; +12.4% / -39% without, as entry 95 found) | the live plan |
| 90, 91 | Options on UPRO and TQQQ instead of the funds, 30-day and weekly | best +$67.6k vs the fund's $86.7k from the same deposits, with a -72% drop | no: decay and spread eat the edge |
| 92, 93 | Fading big single-stock moves by news type, time and price exits | earnings moves continue; no-news gap fades +0.7% a trade but noisy | no; one lead (lone no-news gap-up, faded open to close) |
| 94 | Leverage on that fade | growth peaks near 3x at +9.3% / -62% | no |
| 95 | Index Bollinger bands, daily / weekly / monthly, at 3x | monthly "above the 20-month average" +15-27% but -52% to -93% drops | no |
| 96 | The same on nine sector ETFs at 3x | monthly trend +11.5% / -58% | no |
| 97 | Monthly sector trend at 2x; half with the swing plan | +9.9% / -33%; half and half +10.7% / -31% | lead |
| 98 | Few all-in 3x bets on Quadrant Balances monthly bottoms | 88% of 12-month trades win, median +67%, but one -63%; account +9.5% / -76% | no; kept as an alert |
| 99 | Trailing stops on those bets | 30% stop with re-entry +16.2% / -69%; nothing inside -25% | 2 pass the gates; none meets the 25% limit |
| 100 | The same at 1x and 2x | 2x, 30% stop: +12.5% / -50% | lead |

## What the evidence says

1. Every design built on the S&P 500 and the Nasdaq lands near 12-16% a year. The index earns about 10%, and
   leverage stretches that only until volatility drag takes over, near 2x to 3x.
2. More leverage and more concentration widen the spread of outcomes. They do not raise the typical outcome.
3. A trailing stop limits each trade, not the account. At 3x, a 25% stop is an 8% index pullback, so it fires
   often, and repeated stops compound.
4. A reliable 30%+ a year from a rule anyone can run in a liquid market would be competed away. Backtests
   that show it are usually luck or overfitting.

## Decision (2026-11-26)

- The swing plan at 3x (UPRO / TQQQ, market-on-close orders, cash account) is the engine when the account is
  funded. Tooling is ready: `src/portfolio/swing_live.py`; the daily 15:40 New York order message and the
  after-close settle start on the funding date.
- Research moves to crypto, looking for an engine that is not US equity beta (see `CRYPTO.md`).
- Leads parked, not adopted: the lone no-news gap-up fade (92), the 2x monthly sector trend (97, 100), and the
  Quadrant Balances monthly bottom as an alert for a rare large bet (98), which is not armed now.
- Raising the monthly contribution is the most reliable lever on the milestones.

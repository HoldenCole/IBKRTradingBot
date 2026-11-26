# Bollinger bands on sector ETFs, played through 3x sector funds: pre-registration (entry 96)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User request: the entry-95 test on sector ETFs instead of the broad indices. Long or flat only.
Earlier evidence, disclosed: daily lower-band dip-buys on sector ETFs were positive per trade at
1x (test 75); weekly sector rules lost to equal weight (76); widening the swing plan from SPY and
QQQ to 20 ETFs hurt at the account level (79); entry 95 found nothing on the indices.

## Data

- The nine original Select Sector SPDRs: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY. Signals use
  each fund's dividend-adjusted close on daily, weekly and monthly bars.
- 3x fund returns: the entry-95 model (3 x daily total return, less 2 x (T-bill + 1%) and 0.95% a
  year). It is checked against TECL (XLK), FAS (XLF) and CURE (XLV). Listed 3x funds exist for XLK,
  XLF, XLV, XLU, XLI and XLY; XLB and XLP have none and ERX (XLE) is now 2x, so those three are
  model-only.
- Idle cash earns nothing.
- Common start 2000-09-01, when the monthly bands are warm. Eras: 2000-09 to 2006, 2007-2016,
  2017-2026 (to 2026-11-25).

## Rules

The 14 rules of entry 95 (Bollinger 20, 2; dip to middle, dip to upper, breakout, above middle on
D, W and M; daily dip to middle with a weekly or a monthly above-middle filter), run on each sector.

## Accounts (two ways to combine the sectors, both at 3x)

- Sleeves: each sector holds a fixed ninth of the account and runs its rule; an idle ninth is cash.
  Cost at $1,000: $0.35 on a $111 order is 32 bp, plus 5 bp spread = 37 bp per side.
- Two slots: at most two sectors at once, each half the account (rebalanced daily). When more
  sectors signal than there are free slots, the slot goes to the lowest daily %b at that close
  for the dip rules, and the highest for breakout and above-middle rules. Cost at $1,000: $0.35 on
  $500 = 7 bp plus 5 bp = 12 bp per side.

28 trials (14 rules x 2 accounts).

## Benchmarks

- 3x equal-weight buy and hold of the nine sectors (rebalanced daily, no trading cost).
- 1x equal-weight buy and hold.
- The test-79 swing plan at 3x (idle cash at zero, entry-95 costing), from 2000-09.

## Gates

A trial passes if, in ALL THREE eras, it beats 3x equal-weight buy and hold on CAGR, Sharpe and
maximum drawdown, and still does so with the band length at 10 and at 30.

A passer is a candidate for the small account only if, over 2000-09 to 2026, it beats the swing plan
on CAGR and maximum drawdown, or its daily returns correlate with the swing plan below 0.5. Adopting
anything is the investor's decision.

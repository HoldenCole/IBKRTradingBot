# Crypto C5: the swing plan and the bitcoin 10-month rule in one account: pre-registration (entry 105)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

Idea: the 3x swing plan (test 79, the live plan) holds positions about 11% of the time and its idle cash earns
nothing. The bitcoin 10-month rule (entry 104, a post-hoc lead) is in the market about 70% of the time and is
unrelated to US equity dips. Running both in one account aims directly at absolute return.

Disclosed: the 10-month rule was found after looking at the data in entry 104, so its standalone numbers are
optimistic; this test is about the combination, judged against each part on the same data.

## Components

- Swing plan: test 79's signals (SPY/QQQ dip-buys, two slots, regime gate), each position in a 3x fund (the
  entry 95-98 model: 3 x daily return less 2 x (T-bill + 1%) and 0.95% a year), 9 bp a side on the fund bought.
  Exposure on day t = the share of equity in the swing positions after day t's close.
- Bitcoin rule: at each month-end close, ON if bitcoin closes above the average of its last 10 month-end closes.
  Bitcoin is held at 1x, 0.25% a side (IBKR crypto commission plus spread). Coinbase BTC-USD daily closes,
  sampled on US trading days.

## Designs

- V0 swing plan alone, idle cash earns nothing.
- V1 bitcoin rule alone, the whole account.
- V2 swing plan, with bitcoin on the idle cash when the rule is ON: bitcoin share = (1 - swing exposure) on ON
  months, 0 otherwise. Swing entries sell bitcoin; swing exits buy it back.
- V3 swing plan, with bitcoin held on the idle cash at all times (no rule): checks whether the rule matters.
- V4 fixed halves: half the account runs the swing plan (its slots sized off its half), half runs the bitcoin rule,
  rebalanced to 50/50 at each month end.

## Sample

2016-06-01 (the 10-month average needs ten month-ends of Coinbase data) to the last close. Halves: 2016-06 to
2020-12 and 2021-01 to the end.

## Gate

V2 passes if its CAGR is above both V0 and V1 in each half, and its maximum drawdown is shallower than V1's over
the whole sample. V3 and V4 are reported for comparison; the investor decides.

Also reported: final multiple of a $1,000 start with $150 added each month, maximum drawdown, worst calendar
year, and the share of time with any position.

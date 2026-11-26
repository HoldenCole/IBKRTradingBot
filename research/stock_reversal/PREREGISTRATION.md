# Fading big single-stock moves: pre-registration (entry 92)

Written 2026-11-26 and committed before any event was measured. Nothing below may change after
results are seen. A later idea is a new entry with its own date.

User request: mean-reversion trades on single stocks that pop or crash on earnings, that move on
little or no news, and that move too much on news. The example was a short-dated put bought on a
stock up 34% on the day and sold when the gain had shrunk to 30%: a small correction move.

## What the literature expects

- Earnings moves tend to continue, not reverse (post-earnings-announcement drift, Bernard and
  Thomas 1989), though the drift has weakened in large caps.
- Big moves with no identifiable news tend to reverse; moves with news tend to continue (Chan 2004,
  "Stock price reaction to news and no-news"; Savor 2012, "Stock returns after major price shocks").
- Short-term reversal in large caps is mostly a payment for providing liquidity and is small after
  costs (Nagel 2012).

The expected outcome is that the earnings fades fail, and that any no-news reversal is too small
to cover costs. A strongly positive result is treated first as a bug or a data leak.

## Data

- Universe: point-in-time S&P 500 members (github.com/fja05680/sp500, MIT licence). A stock is
  eligible on day t only if it was a member on day t.
- Prices: Yahoo daily bars, dividend-adjusted. Yahoo has no delisted symbols, so failed members
  are missing (survivorship bias). The share of member-days with prices is reported by year.
  A ticker's bars are used only if its Yahoo history starts at least 60 days before the start of
  the membership window being used (or before 2004-06-01), which guards against a ticker that
  was later reused by another company.
- Filters on day t: prior close at least $5; 20-day median dollar volume at least $20 million.
- News proxy: SEC 8-K filings (acceptance time, New York). Item 2.02 marks an earnings release.
  This is a filing proxy, not a news feed: analyst calls, product news, macro and sector news are
  invisible to it.
- Development sample: 2005-01-01 to 2023-12-31. Eras: 2005-2014 and 2015-2023.
- Hold-out: 2024-01-01 to the end of the data. The event builder refuses it without a flag that
  is used once, only for a rule that has passed every development gate.

## Event definitions

All returns are excess over SPY over the same interval.

- sigma: standard deviation of the stock's daily excess return over the 60 sessions before t.
- Gap move g: open on t over close on t-1, minus SPY's.
- Day move d: close on t over close on t-1, minus SPY's.
- Size L (large): |move| at least 5% and at least 3 sigma.
- Size X (extreme): |move| at least 10% and at least 5 sigma.

News buckets. For the open-entry horizon the window ends at 09:30 on t; for the close-entry
horizons it ends at 16:00 on t.

- E (earnings): an 8-K with Item 2.02 accepted after 16:00 on t-1 and before the window end.
- EX (too much on earnings): E events whose |move| is more than twice the median |move| of that
  stock's previous 8 E events of the same kind (at least 4 needed). A subset of E.
- F (other filing): not E, and some other 8-K accepted after 16:00 on t-1 and before the window end.
- N (no filing): no 8-K of any kind accepted from 16:00 five sessions before t to the window end,
  and t is not within 5 sessions after an E event.

## Trades

The trade fades the move: short after a rise, long after a fall. Return is in the fade direction,
excess over SPY.

- H0: enter at the open of t, exit at the close of t. Event defined on the gap g.
- H1: enter at the close of t, exit at the open of t+1. Event defined on the day move d.
- H2: enter at the close of t, exit at the close of t+1. Event on d.
- H3: enter at the close of t, exit at the close of t+5. Event on d.

Close entries assume a market-on-close order sent shortly before the close using the price then;
the test uses the close itself.

Trials: 4 buckets (E, EX, F, N) x 2 directions (fade a rise, fade a fall) x 4 horizons x 2 sizes = 64.

## Costs

10 bp per side (event-day spread for S&P 500 names plus commission), stress 20 bp. No borrow fee
(S&P 500 names are easy to borrow; 5 days at general collateral rates is under 1 bp).

## Gates (every one must pass on development data, at base cost)

1. At least 300 events.
2. Mean net excess return above zero.
3. Mean net above zero in both eras.
4. t-statistic at least 3, with standard errors clustered by event date.
5. Holm-Bonferroni across all 64 trials at a family-wise 5% level (two-sided p from the clustered t).
6. Cost ratio at least 2: mean gross return at least twice the 20 bp round trip.

A rule passing every gate has its hold-out opened once. It passes if mean net excess return is
above zero with a one-sided p below 0.05. Only then does it go on to stage 2: an intraday test of
entry after the stock is already extended (Yahoo hourly bars, inside the hold-out period), and
an options model.

Any trial failing a gate is abandoned with no re-tuning.

## Reported for every trial

Events, mean gross and net, median, win rate, both eras, clustered t, Holm-adjusted p, and the
raw (not market-adjusted) net return. Results for fading falls (buying crashes) carry the
survivorship warning, since the missing delisted names are disproportionately crashes that kept
falling.

## Amendment 1 (2026-11-26, before any event was measured)

Filings are matched to stocks through the company's current SEC registrant number. A company that
changed registrant (for example Google to Alphabet in 2015) has earlier filings under another
number, and its earnings days would wrongly fall into bucket N. Rule: a stock-day is used only
if that stock has an Item 2.02 filing accepted in the 130 sessions before t, which shows its
filings are being seen.

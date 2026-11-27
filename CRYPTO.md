# Crypto: the plan

Started 2026-11-26, after the small-account review (`SMALL_ACCOUNT.md`) concluded that levered US equity beta
tops out near 12-16% a year. The aim is an engine that is not US equity beta, run by a bot with no daily input.

Background: `reports/Crypto trading bot open source survey.md` (the earlier survey in this project).

## What the survey already established

- Tooling is mature and free (freqtrade, Hummingbot, NautilusTrader, LEAN, CCXT). None of it supplies an edge.
- US access decides the venue. Binance, Bybit, OKX and Hyperliquid are closed to US persons. US-legal options:
  spot on Coinbase, Kraken, Gemini, Binance.US and Interactive Brokers; CFTC-regulated perpetual-style futures
  on Coinbase (nano BTC and ETH, from July 2025) and Kraken (from June 2026, listed on Bitnomial); CME futures
  through IBKR.
- Entry-tier spot costs: about 1.8% a round trip at Coinbase, 1.6% at Kraken, about 0.36% at IBKR (where the
  $1.75 minimum dominates below about $970 an order).
- Sub-hour signals are worth 0-2 bp and cannot pay taker fees. Daily trend following has the best published
  support (a Donchian-breakout ensemble on the top 20 coins, volatility-targeted, Sharpe above 1.5 net reported).
- Carry (long spot, short perpetual) was the best risk-adjusted crypto trade of 2020-2024 (gross Sharpe 6.45)
  and turned negative in 2025; bitcoin funding fell from 11.0% a year in 2024 to 2.2% in 2026 to August.

## Data reachable from this environment (checked 2026-11-26)

| source | what | span |
|---|---|---|
| data.binance.vision (bulk files) | spot daily and intraday candles; USD-M perpetual funding | spot from 2017, funding from 2019-20 |
| Kraken futures API | hourly funding, PF_XBTUSD and others | last 12 months |
| Hyperliquid info API | hourly funding by coin | from 2023 |
| OKX public API | funding | recent months |
| Coinbase Exchange, Kraken spot APIs | daily candles | Coinbase BTC from 2015 |

Binance's trading API (451) and Bybit (403) are blocked here; neither is usable by a US person anyway.

## Studies, in order

1. **Funding carry, measured (C1). Done, entry 101: collapsed to 2-4% a year since 2025 (about 2% on capital);
   pays only in manias. No bot; an alert at most.** Is the long-spot / short-perpetual trade still paying, by year and by coin,
   after the costs of both legs? Descriptive; it decides whether a carry bot is worth building. The live venue
   would have to be a US one (Coinbase or Kraken perpetual-style futures), whose funding history is short.
2. **Daily trend following (C2). Done, entry 102: the published method replicates on bitcoin, but on Binance
   2018-2025 it is weaker than published (Sharpe 0.94-1.18) and since publication it has earned about nothing;
   fails its gates. Kept as a paper-trading watch, not a bot.** Pre-registered replication of the Donchian ensemble on liquid coins, long-only
   spot at US costs, with the two-era and hold-out discipline used elsewhere in this project. Risk: bitcoin's
   volatility is about 3 to 4 times the S&P 500's, so crypto at 1x already carries 3x-fund risk; leverage is a
   separate question.
3. **Short-term BTC-led signals, levered (C3). Done, entry 103 (corrected): every short-term signal loses; the BTC daily trend first appeared to pass but that was a look-ahead bug; corrected, it trails holding and leverage wipes it out. 0 of 30 pass.**
4. **Do the project's signals predict bitcoin (C4)? Done, entry 104: the equity signals do not; bitcoin's own 10-month average does, a little. Post-hoc lead: a manual monthly rule (hold BTC while above its 10-month average), 1x.**
5. **The swing plan and the bitcoin rule in one account (C5). Done, entry 105: bitcoin on the swing plan's idle cash
   fails; a fixed half-and-half split was the best 2021-26 combination (+31% a year, -24% max drawdown).**
6. **Kalshi favourite-longshot bias (entry 106). Done: no edge after fees in a thin 2026 sample.**
7. **Kalshi weather, forecast model vs prices (entry 108). Done: the market is better calibrated than a free forecast model; no edge.**
8. Only a design that passes goes to paper trading, then to a small live account with the safety controls listed
   in the survey (kill switch, position limits, reconciliation, exchange-resident stops).

## Standing rules carried over

Pre-register before results. Record every test in `TESTS.md` and `PORTFOLIOS.md`, verdict included. Paper first.
No keys or credentials in the repository.

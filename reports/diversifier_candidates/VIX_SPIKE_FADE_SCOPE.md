# Diversifier candidate — VIX spike fade

**Date:** 2026-05-02
**Status:** scoping notes, not built. Scoped for execution after Phase 5.

## Why a fourth candidate is needed

The 2018-2026 backtest has shown that strategies in the
"long-biased mean-reversion on SPY/QQQ" family cannot beat
buy-and-hold of the same instruments:

- IBS-LS on QQQ shares (Phase 1.5): full-period Sortino 0.59,
  return +83% vs QQQ buy-and-hold +302%. Drops to 0.32 Sortino
  out-of-sample.
- Overnight drift on QQQ: Sortino 0.55 vs QQQ buy-and-hold 1.08;
  return +60% vs +302%. Negative lift in every slice.
- Afternoon reversion (Phase 5, pending data): expected to be
  another long-biased mean-reversion candidate; will be evaluated
  the same way.

A multi-strategy portfolio composed entirely of long-biased equity
mean-reversion strategies on QQQ does not solve the bear-regime
drawdown problem. We need a **genuinely uncorrelated return stream**
to clear Tier B at the portfolio level.

## Candidate: VIX spike fade

### Strategy concept

When VIX rises sharply (e.g., +20% in a day, or absolute level above
some threshold), enter a long-volatility position via VXX shares (or
short SVXY, mathematically equivalent). Exit when VIX normalizes or
after a short time stop.

### Why this candidate

1. **Long volatility = uncorrelated with long equity.** VIX rises
   when SPY falls; VXX/long-vol positions appreciate during equity
   drawdowns. Adds genuine diversification to a long-equity book.
2. **Style-different from existing candidates.** Not mean reversion,
   not momentum, not always-long. Event-driven on volatility regime
   shifts.
3. **Free data.** VIX from FRED (https://fred.stlouisfed.org/series/VIXCLS).
   VXX/SVXY daily bars from FMP (already integrated).
4. **Simple signal logic.** No regime classification, no IV surface
   modeling. Threshold + time stop.

### Risks and caveats

- **Volatility ETPs have negative roll yield.** VXX loses ~30-50%
  per year structurally due to contango in VIX futures. Holding too
  long destroys returns. Strategy must be quick: enter on spike, exit
  when normalized, never carry past a few days.
- **Short-vol blowups are catastrophic.** Feb 2018 ("volmageddon")
  vaporized inverse-vol funds in a day. Aug 2024 carry-trade unwind
  similar. SVXY shorts (or any structurally-short-vol position) need
  position limits and circuit breakers.
- **Long-vol bleeds during normal markets.** Most days are calm;
  VIX gradually mean-reverts down. The strategy must trigger only on
  spikes and exit fast.

### Specific signal proposals to test

**v0** — VIX threshold trigger:
- Entry: VIX_today > 25 AND VIX_today > 1.2 × VIX_5d_ago
- Instrument: long VXX (or short SVXY equivalent)
- Exit: VIX_today < 20 OR 5-day time stop

**v1** — Spike-rate trigger:
- Entry: (VIX_today / VIX_yesterday) > 1.20 (one-day jump > 20%)
- Instrument: long VXX
- Exit: 3-day time stop OR VIX returns within 10% of pre-spike level

**v2** — SPX-down + VIX-up combined:
- Entry: SPY one-day return < −2% AND VIX > 22
- Instrument: long VXX
- Exit: 5-day time stop

Test all three; pick the best Sortino with stable train/test profile.

### Data scope

| Need | Source | Cost | Effort |
|---|---|---|---|
| VIX daily history 2018-2026 | FRED `VIXCLS` series | Free | 1 hour to integrate (CSV download or FRED API) |
| VXX daily OHLCV 2018-2026 | FMP `historical-price-eod/full` | Free | None — already pulling other tickers |
| SVXY daily history (alternative leg) | FMP same endpoint | Free | None |
| (Optional) VIX intraday for finer timing | FRED has none; would need IBKR | TBD | Defer to v2 |

### Engineering scope

- New strategy class `VixSpikeFadeStrategy` emitting Signals on VIX
  threshold breaches at daily close. ~30 LOC.
- Engine: SharesBacktestEngine handles it natively (long shares of VXX
  on entry signal, exit on signal exit or time stop). No engine changes.
- Benchmark comparison: VXX buy-and-hold (which is structurally
  negative). Benchmark for "is the timing strategy better than
  always-long-VXX?" — yes if positive return; vs "is it better than
  cash?" — needs cash return = 0% comparison.
- Walk-forward train/test 2018-2022 vs 2023-2026 same as other
  candidates.

### Effort estimate

**~1 day total.**
- VIX data fetch + cache: 1-2 hours
- Strategy class + engine integration: 2-3 hours
- 3 signal variants × full diagnostic: 2-3 hours
- Findings write-up: 1 hour

### Decision criteria

Apply same v2 tier rule with two adjustments:

1. **Benchmark for VIX strategies is cash (0% return), not SPY.**
   A long-vol strategy that loses less than VXX buy-and-hold and
   produces positive Sortino in equity-drawdown periods is doing
   its job, even if absolute return is small.

2. **Correlation with the existing long-equity book is the primary
   metric, not standalone Sortino.** A VIX strategy with Sortino
   0.4 standalone but −0.5 correlation to IBS in drawdown regimes
   is more valuable than a strategy with Sortino 0.7 that correlates
   +0.3. The portfolio metric matters.

   To compute: run VIX strategy and IBS-LS in the same period,
   compare daily-return correlations during SPY drawdowns >5%.

## Alternative diversifying candidates (not pursued now)

| Candidate | Style | Data needs | Why deprioritized |
|---|---|---|---|
| Bollinger squeeze straddle on QQQ | Long vol | QQQ daily bars + options | Multi-leg options pricing — defer until needed |
| Trend continuation on TQQQ | Momentum | TQQQ daily bars | Probably correlated with bull regimes; not orthogonal to existing book |
| Defensive rotation (gold, bonds) | Asset allocation | GLD, TLT bars | Not a "trading strategy" — beyond v2 scope |
| Pairs trading SPY/QQQ | Stat arb | Both already pulled | Likely correlated to mean reversion family |

## Sequence

1. Phase 5 (afternoon reversion) — pending IBKR 5-min cache
2. **VIX spike fade** — start when Phase 5 result is in
3. Regime model integration — when user delivers
4. Phase 2 (options leverage) — gated on at least one Tier C strategy
   with regime filter applied

# BAH-on-trend-ON-days — out-of-sample VALIDATION PASSED

**Date:** 2026-05-02
**Rule:** Hold QQQ when (close > SMA(50)) AND (SMA(50) > SMA(200)).
Cash (0% return) otherwise. Daily flag, no MA window tuning.

## Verdict — real candidate, not sample-specific

The simple trend-gated buy-and-hold lifts substantially over QQQ
buy-and-hold across **26 years and three different macro regimes**.
Each held-out period exceeds the in-sample Sortino lift, not falls
short of it.

| Period | Strat return | BAH return | Sortino lift | Final $ | DD lift |
|---|---|---|---|---|---|
| **2018-2026 (in-sample)** | **+881%** | +302% | **+2.60** | $78,494 | +24.8pp |
| **2010-2017 (held-out)** | **+590%** | +236% | **+3.05** | $55,233 | +12.1pp |
| **2000-2009 (different regime)** | **+401%** | **−51%** | **+2.86** | $40,105 | +75.9pp |

Per the user's locked decision criterion (each held-out lift within
50% of in-sample = within ±1.30): both held-out periods PASS. Lifts
are 117% and 110% of the in-sample value respectively — held-out
performance was **better**, not worse.

## The 2000-2009 result is the strongest signal

QQQ buy-and-hold lost **51%** over the 2000-2009 decade with a
peak-to-trough drawdown of **83%** (dot-com bust + GFC). The
trend-gated strategy returned **+401%** with a max drawdown of
**7.1%**.

Mechanism, visible in the per-year breakdown:
- **2000, 2001, 2002**: strategy 0.0% (cash), QQQ −38%, −33%, −37%
- **2003-2007**: strategy gains during the recovery + bull
- **2008**: strategy 0.0% (cash), QQQ −42%
- **2009**: strategy +38% (vs QQQ +55%) — entered late in the
  recovery; missed the early bounce because SMA50/SMA200 cross lags

The cost of the rule is **missing part of the early-recovery move**
each cycle. The benefit is **completely avoiding sustained bear
markets**. Over multi-year periods the trade-off is dramatically
favorable.

## Sortino formula audit (user-requested verification)

The user flagged a possible bug where cash-day handling could
artificially inflate Sortino. Audit done:

- **Cash days correctly handled.** Filter-OFF days produce 0% return
  in the daily-return series, included in the Sortino calculation.
  Not "no observations exist."
- **Prior Sortino formula was non-standard but conservative.** Earlier
  reports used `std-of-negatives` with N_negative denominator. Standard
  Sortino convention uses `sqrt(sum-of-squares-of-negatives / N_total)`
  with target=0. On the 2018-2026 BAH-on-ON-days data: prior method
  gave Sortino 2.65; standard method gives 3.77. **Prior method
  understated Sortino by ~30% in cash-heavy strategies, didn't
  inflate it.**
- **Switched to standard formula globally** in `src/backtest/benchmark.py`.
  All future Sortino numbers use the standard convention; prior
  reports' Sortino values are slightly conservative vs current.

## Why this is the buy-and-hold-lift component the portfolio thesis needs

The user articulated earlier:
> "The portfolio thesis is becoming clearer: we need at least one
> buy-and-hold-lift strategy AND at least one diversifier."

This rule clears the bar by a wide margin:

| Rule 1 criterion | In-sample | 2010-2017 | 2000-2009 |
|---|---|---|---|
| Strategy Sortino > Bench Sortino | 3.77 > 1.17 ✓ | 4.48 > 1.42 ✓ | 2.81 > −0.05 ✓ |
| Strategy return ≥ Bench return | +881% > +302% ✓ | +590% > +236% ✓ | +401% > −51% ✓ |

Tier classification: **A** in all three slices (Sortino > 1.5, |DD| <
25%, return ≥ benchmark). This is the first lift candidate to clear
Tier A in the v2 work.

## What's NOT yet done — discipline reminders

1. **No MA window tuning.** Fixed at 50/200 per the prior finding.
   Don't iterate. The point of the validation was specifically to
   not introduce free parameters.
2. **No transaction cost modeling.** Each filter cross is a buy or
   sell of QQQ shares. With ~5-15 crosses per year, even at 1bp
   slippage the drag is small. Need to verify when implementing.
3. **No tax modeling.** Each cross is a taxable event in non-IRA
   accounts. Long-term capital gains rate may apply if held >1 year;
   short-term otherwise. Tax-deferred account preferred for
   deployment.
4. **No paper validation yet.** This is the next step — paper-run
   the rule for some weeks before live.
5. **Implementation considerations:**
   - Strategy is dead simple: daily check at close, hold or cash
   - One position at a time
   - No regime model dependency (the strategy IS the regime model
     for this purpose)
   - Compatible with $8k account size — buys/sells are at full
     equity, no per-trade cap needed since position is QQQ shares,
     not options

## What this changes upstream

For the multi-strategy portfolio thesis:

- **Lift component:** **CONFIRMED** (BAH-on-trend-ON-days). First
  passing candidate.
- **Diversifier component:** still TBD. IBS-LS, overnight drift,
  VIX spike fade all failed. Afternoon reversion pending data.

The portfolio needs a diversifier that's truly uncorrelated and
profitable in bear regimes. The BAH-on-trend rule sits in cash
during bears (good for itself, but doesn't add return there). A
genuine diversifier would make money during the bears that this
rule sits out.

For the IBS regime-filter work: still parked pending user's model.
The trend filter that was useless for IBS-LS turns out to be highly
useful as a standalone signal for buy/sell decisions on QQQ itself.
Different question, different answer.

## Recommended next steps

1. **Don't deploy yet.** Per locked discipline: this is a one-look
   validation. We learned the rule generalizes. Now scope it as a
   real strategy with full implementation considerations (transaction
   costs, tax efficiency, slippage, exact entry/exit timing).
2. **Run on monthly/weekly rebalance frequencies** to see if the
   daily flag is necessary or if a weekly check is fine. (This IS
   parameter-tuning, but it's an implementation detail rather than
   signal-fitting.)
3. **Test against SPY** as well — does the same rule work on SPY
   shares? Different instrument, same mechanic. If it does on SPY,
   the rule is genuinely general; if it only works on QQQ, the
   tech-heavy bias is part of why.
4. **Park afternoon reversion and regime model work** until those
   land. The lift component is now confirmed; the next priority is
   filling the diversifier slot.

## Files

- `src/data/yahoo.py` — yfinance helper (free, pre-2010 daily bars)
- `src/backtest/benchmark.py` — Sortino formula corrected to standard
- `scripts/run_bah_on_trend.py` — reproducible runner
- `reports/bah_on_trend/raw_output.txt` — full output, all three periods

# Decisions log

A running record of strategy and engineering decisions, especially the ones
where data invalidated a prior intuition. Append-only — when the picture
changes, write a new dated entry rather than rewriting an old one.

---

## 2026-05-01 — v1.1 strategy changes considered, none committed

### Context

After the model-fix sequence (Step 1 intraday stop, Step 2a IV recalibration,
Step 2b spread recalibration), the 2024-01-01 → 2026-04-15 backtest produced:
−$876 PnL, Sharpe −0.33, PF 0.86, 50% win rate. A draft v1.1 spec proposed:
relaxed EWO thresholds (`z<-1.8` instead of `-2.0`), an IV-rank-70 entry gate,
underlying-price stop at 1.0×ATR, disable SHORT_FADE, loosen position cap
2→3.

### Diagnostic process

A 5-part diagnostic was run on Step 2b:

1. Stop decomposition into directional (>1× ATR adverse), IV/theta (<0.5×),
   and mixed (0.5-1.0×) buckets.
2. Max adverse excursion (MAE) on signal-exit winners.
3. Per-strategy P&L (EWO / IBS long / IBS short).
4. Forward returns on suppressed signals.
5. IV-rank-70 gate counterfactual.

## 2026-05-01 — Bug invalidating the v1.1 prescription (entry_underlying scale mismatch)

**This section deliberately stands on its own.** The episode is the kind of
thing that recurs: a diagnostic produces a confident verdict, the verdict
reaches the recommendation stage, and only a verification challenge surfaces
that the underlying measurement was wrong. Future readers should be able to
find this episode quickly, not after combing through a long entry.

### What the bug was

`BacktestEngine._execute_entry` stored the option ETF's open price
(UPRO/TQQQ/SQQQ) in `Position.entry_underlying`. But `Position.entry_atr20`
was computed on the SIGNAL underlying (SPY/QQQ). Any analysis that subtracts
`entry_underlying` from a SPY/QQQ price and divides by `entry_atr20` is
computing units-incoherent arithmetic — the diagnostic's MAE buckets and
"underlying move in ATR units" calculations on stops were both affected.

### Effect on production code

**Zero effect on trade ledger or P&L** for any backtest run to date.
`entry_underlying` is read by exit branches (afternoon hard stop, ATR trail
post +100% scale) that don't fire materially in the current backtests.
The live runner sets `entry_underlying` correctly (signal underlying via
`broker.underlying_price(d.underlying)`); only the backtest engine was
inconsistent.

### What the buggy data said

- Stop decomposition: Bucket A (directional, >1× ATR adverse) = **5%**;
  Bucket B (IV/theta, <0.5× ATR) = **75%**.
- MAE on signal-exit winners: **100% under 0.5× ATR.**
- Verdict drawn: switch the −50% premium stop to an underlying-price stop
  at 1.0× or 0.7× ATR. Aggressive variant supportable by data.

### What the corrected data said

- Stop decomposition: Bucket A = **61%**, Bucket B = **5%** (3 trades).
  Almost the inverse.
- MAE on winners: 88% under 0.5×; 12% in 0.5-1.0×; 1 trade in 1.0-1.5×.
- Verdict reversed: underlying-price stop offers no clear edge.
- IV-rank-70 gate (independent of the bug): still −$250 net if applied.
- Per-strategy: EWO 100% win was a 2-trade artifact.

### What was done

- Bug fixed in commit `94f3ae0`. Engine now uses `_underlying_open(sig.underlying, today)`
  for `entry_underlying`, matching the live runner.
- Diagnostic re-run with corrected data.
- v1.1 prescription that depended on the buggy verdict was withdrawn.
- This section written.

### How the bug was caught

The user asked three specific verification questions about the MAE
measurement before acting on the prescription:

1. Is MAE measured on the signal underlying (SPY/QQQ), not the ETF?
2. Is MAE computed as `(intraday_low − entry_price) / entry_ATR` for longs?
3. What does the MAE distribution look like if you exclude same-day winners?

Question 1 forced a code-read of `BacktestEngine._execute_entry`, which
exposed the scale mismatch. Without those questions, the underlying-price
stop change would likely have been committed and only surfaced as wrong
when the next backtest variant produced inconsistent results.

**Methodology takeaway**: when a diagnostic produces a strong verdict,
ask measurement-detail questions before implementing. The cost of asking
is one round-trip; the cost of acting on a wrong measurement is a commit
that needs reverting plus reputational drag on the next conclusion.

### Expanded backtest (2018-2026)

To validate the strategy across regimes rather than one short window:

```
508 trades over 8.3 years
57% win rate, +$368 total, +4.6% return, Sharpe 0.11, PF 1.03

Per year:
  2018: -$240 (chop -> Q4 correction)
  2019: +$34  (bull)
  2020: +$1,110 (crisis + recovery) <-- 75% of 8-year edge
  2021: +$134 (bull)
  2022: -$249 (bear, only 11 trades)
  2023: +$456 (bull)
  2024: -$594 (bull)
  2025: +$390 (bull_chop)
  2026: -$672 YTD (mixed)
```

Key findings:

1. 75% of the strategy's 8-year edge comes from 2020 alone.
2. EWO does not persist: 6 trades over 8 years, 50% win, −$25 total.
3. SHORT_FADE genuinely doesn't fire — only 2 trades in 8 years, both
   losers. Not small-sample noise; structural rarity.
4. IBS does NOT outperform in bear regimes. The `close > SMA(200)` filter
   prevents firing in actual bears. 2022 was 36% win, PF 0.49.
5. Real edge regime is `crisis_recovery` (2020): 74% win, PF 2.77.
   N=1 instance in 8 years — not a reproducible-at-will edge.

### Decisions (final)

**v1.1 changes considered, ALL rejected by data:**

- IV-rank-70 entry gate — refuted by counterfactual (−$250 net).
- EWO threshold loosening (`z<-1.8`, `RSI<15`) — refuted by 8-year sample
  showing EWO has no edge at v1.0 thresholds either.
- Underlying-price stop at 1.0× ATR — refuted by corrected stop
  decomposition (Bucket A = 61% directional, the −50% premium stop and
  underlying-price stop catch the same trades).
- Underlying-price stop at 0.7× ATR — refuted by MAE analysis on winners.
- Position-limit loosening 2→3 — small N, parked.
- Budget cap loosening — small N, parked. Budget gate is doing real work.
- Premium-stop backstop at −65% — moot; the −50% premium stop already
  fires intraday under Step 1's fill model.

**v1.1 changes that ARE supported by 8-year data:**

- Disable SHORT_FADE in config (default off). 2 trades in 8 years, 0% win
  rate. No statistical basis to leave it active.
- Disable EWO in config (default off). 6 trades, 50% win, no edge over
  8 years. The earlier 2-trade 100% win was small-sample.

**Strategic decisions:**

- Strategy as specified is not viable for live deployment. Sharpe 0.11
  vs spec requirement of 0.8.
- 75% concentration in 2020 makes it not a tradeable edge — it's a
  one-regime artifact.
- The framework (engine, runner, position manager, FMP, install scripts,
  paper bot) is sound. The strategies are not.

### Next step

Hold v1.1 implementation for now. Two paths:

1. **Wait for the regime filter the user is building separately.** If it
   can gate to high-vol-with-recovery regimes (the only place IBS shows
   real edge), re-run the 8-year backtest with the filter applied and
   re-evaluate.
2. **Treat v1.0 as a learning exercise.** Move toward v2 design with
   different signal logic (e.g., IBS combined with realized-vol state,
   different timeframe, different option structure like put credit
   spreads instead of long calls).

The paper bot continues to run. Live execution data is a side benefit
even if the underlying strategy is shelved — it calibrates the
backtest model for any future strategy iterations.

### Methodology notes (for future episodes)

- The bug-catch happened because the user requested specific verification
  questions about MAE measurement details. The questions surfaced the
  scale mismatch that wasn't visible in the headlines. **Always ask
  measurement-detail questions before acting on a diagnostic verdict.**
- The expanded-period backtest invalidated multiple findings drawn from
  the shorter sample. **Never deploy a strategy on edge demonstrated
  only in a 2-3 year window if more data is accessible.**
- The v1.1 prescription that the 5-step diagnostic produced was wrong
  at every stage (initially via the bug, then via small-N sample
  artifacts). **A clean diagnostic process can still produce wrong
  conclusions if the underlying data sample is unrepresentative.**

---

## What would change the recommendation (explicit triggers)

This section locks the criteria for re-opening decisions, so future
review doesn't re-litigate them open-endedly. If one of these triggers
fires, the matching decision gets re-evaluated. Otherwise it stands.

### Trigger to reconsider live deployment of v1.0 strategy

**The strategy is reconsidered for live deployment if and only if**
a regime filter (per the user's separate workstream) is built and,
when applied to the 2018-2026 backtest, satisfies all of the following:

1. **Identifies high-vol-with-recovery environments with ≥60% precision**
   when measured against the labeled regimes in this document
   (`crisis_recovery` is the positive class; precision = correctly-flagged
   regime-on days / total regime-on days).
2. **Gated profit factor in regime-on periods is ≥1.5.**
3. **Gated equity curve in regime-off periods is flat (drawdown ≤−5%).**

If all three hold, paper-trade for 4-6 weeks with the gated strategy,
then evaluate live.

If any of the three fails, **v1.0 strategy is shelved**, and the
workstream pivots to v2 design (different timeframe, different signal,
different option structure — the "Option C" from the v1.1 deliberation).

### Trigger to enable SQQQ short

`SQQQ_SHORT_ENABLED` flips back to true if and only if a future backtest
(with regime filter or other modification) produces **at least 10 SQQQ
short trades with a win rate above 50%** in a single sample. Until
then it stays off. The 2-trade / 0%-win history is structural rarity,
not bad luck — the entry conditions essentially don't fire.

### Trigger to disable EWO

`EWO_ENABLED` flips to false if and only if EWO accumulates **at least
10 trades with PF ≤ 0.8** over a forward sample (paper or future backtest
with regime filter). At <1 trade/year fire rate, this likely takes
multiple years to resolve — the unvalidated label stays in the meantime.

### Trigger to revisit position cap and budget cap loosening

`MAX_CONCURRENT_POSITIONS=2` and `WEEKLY_LOSS_BUDGET_USD=500` get
revisited only after **at least 20 paper-trading weeks** with the
regime filter active. The 4 and 5 cases of suppression we observed
on the 2024-2026 sample were too small for any conclusion. Live data
under regime gating is the only path to evidence here.

### Triggers that explicitly do NOT exist

- **No P&L threshold.** A bad month or quarter on paper does not trigger
  any change. The strategy's decision is regime-gated, not equity-curve-gated.
- **No "look at one more period" trigger.** The 2018-2026 backtest is
  the locked baseline. Adding 2027 data later doesn't reopen v1.1
  unless one of the explicit triggers above fires.

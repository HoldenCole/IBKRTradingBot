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

### Bug found mid-diagnostic

`BacktestEngine._execute_entry` was storing the option ETF's open price in
`Position.entry_underlying`, while `entry_atr20` was computed on the SIGNAL
underlying (SPY/QQQ). This made any post-hoc analysis that computed
"underlying move in ATR units" units-incoherent.

The bug had **zero** effect on the trade ledger and PnL of any backtest run
to date — the affected fields are read by exit branches that don't fire
materially in the current backtests (afternoon hard stop, ATR trail post-
+100% scale). But the diagnostic results based on those fields were wrong.

Fixed in commit 94f3ae0. Live runner was not affected.

### Initial (pre-bug-fix) diagnostic verdict

- Bucket A (directional) was 5%, Bucket B (IV/theta) was 75%.
- MAE on winners: 100% under 0.5× ATR.
- Verdict: switch to underlying-price stop as primary v1.1 change.

### Corrected diagnostic verdict

- Bucket A jumped to 61%, Bucket B collapsed to 5%.
- MAE on winners: 88% under 0.5× ATR; 12% in 0.5-1.0×; 1 in 1.0-1.5×.
- Verdict reversed: underlying-price stop offers no clear edge over the
  existing −50% premium stop.
- IV-rank-70 gate counterfactual independent of the bug, still showed
  −$250 net P&L if applied. Counterproductive.
- Per-strategy: EWO 100% win was a 2-trade artifact; IBS long ~break-even
  per trade.

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

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

---

## 2026-05-02 — Locked candidate evaluation rules (v2)

After two negative findings (IBS-LS Tier D vs benchmark, overnight drift
negative Sortino lift on every slice), the v2 strategy validation
workstream needs explicit rules to prevent re-litigating "is this
deployable" each time. Locking the criteria here.

### The structural finding driving these rules

**Long-biased trade-in-trade-out strategies on SPY/QQQ in 2018-2026 are
strictly dominated by buy-and-hold of the same instrument.** This is a
property of the sample (strong bull punctuated by short crashes that
recovered quickly), not a strategy-design problem. Any candidate in this
family must have a clear mechanistic story for why it would beat
buy-and-hold specifically. If the story can't be articulated upfront,
the candidate is unlikely to clear the lift test and shouldn't consume
backtest cycles.

### Rule 1 — buy-and-hold-lift candidates (long-biased, frequent-trading)

Applies to strategies that take long-biased equity exposure with
multiple entries/exits per month — IBS-style mean reversion, overnight
drift, momentum continuation on SPY/QQQ shares, etc.

**Pass criteria:**
- Strategy Sortino > Benchmark Sortino (same instrument, same period)
- Strategy total return ≥ Benchmark total return (same instrument, same period)
- Both train and test slices, not just full period

**If pass**: candidate proceeds to portfolio-component evaluation (correlation
with other components, role in regime mix).

**If fail (either Sortino or return below bench)**: drop the candidate.
The strategy is strictly dominated by buy-and-hold of the same instrument.
No leverage or sizing trick fixes a strictly-dominated standalone result.

### Rule 2 — diversifier candidates (low-frequency, regime-specific, contrarian)

Applies to strategies designed to be uncorrelated with long equity —
VIX spike fade, vol breakouts, defensive rotation, pairs trading,
short-biased mean reversion in specific regimes.

**Pass criteria (all four):**
- Correlation of strategy daily returns with QQQ buy-and-hold daily
  returns < 0.30 (over same period)
- Strategy P&L during QQQ drawdown periods (>5% from rolling high) > 0
  (i.e., it hedges, not amplifies)
- Strategy Sortino > 1.0 on its own equity curve (it makes money on
  net even though it sits in cash much of the time)
- ≥30 trades over 8 years for statistical meaningfulness

**Diversifiers are NOT held to the buy-and-hold-return-beat rule.** A
diversifier whose absolute return is +20% over 8 years can still earn
its slot if the four criteria above are met — its job is to make the
portfolio's drawdown profile better, not to beat SPY.

**If pass**: candidate proceeds to portfolio-sizing evaluation.

**If fail any criterion**: drop or specifically diagnose which criterion
failed and whether the strategy can be tightened to clear it.

### Rule 3 — special cases

**Intraday-only strategies (afternoon reversion):** the buy-and-hold
comparison may not apply cleanly because the strategy doesn't take
overnight risk. Report BOTH the lift-test and the diversifier-test;
treat as diversifier if its primary value is uncorrelated returns,
treat as lift candidate if it's frequent-trading and competing with
buy-and-hold.

**Regime-gated strategies:** if a regime classifier exists and the
strategy is conditional on it, evaluate against the regime-gated
benchmark — i.e., compare to "what buy-and-hold would have returned
if you only held the underlying during regime-on periods." This
applies to IBS-with-regime-gate when user's regime model is delivered.

**Leveraged strategies (Phase 2 options, margin shares):** apply rule 1
or rule 2 based on the underlying signal's classification, not the
leverage. Leverage on a regime-dependent strategy amplifies dependence;
it doesn't change the category.

### What this rules out (won't backtest)

- Most variants of mean reversion on SPY/QQQ shares — already two
  strikes against this category (IBS-LS, overnight drift).
- Trend continuation on SPY/QQQ shares — would be just expensive
  market exposure given the 2018-2026 sample.
- Most "improve on buy-and-hold" framings without a specific
  mechanistic story.

### What this favors

- Diversifier strategies with clear uncorrelated mechanics (VIX spike
  fade, vol breakout, defensive rotation).
- Strategies on instruments where buy-and-hold isn't the obvious
  benchmark (sector rotation, pairs trading, fixed-income carry).
- Leverage applied selectively in regimes where buy-and-hold isn't
  optimal — but only after a regime classifier exists and the
  underlying signal already passes rule 1.

### Implementation

`src/backtest/diversifier_check.py` (new) implements rule 2 mechanically.
`src/backtest/v2_report.py` extended to emit the lift table (rule 1) and
the diversifier verdict (rule 2) per strategy run. No more manual
verdicts; the report tells you which tier and which rule applied.

### Triggers to revisit these rules

- A future strategy passes the lift test cleanly: confirms the rule is
  achievable, no change.
- The 2018-2026 sample window is extended (e.g., adding 2027+) and the
  lift-test results materially shift: rule may need recalibration.
- A backtest produces a result that "feels right" but fails the rule —
  forces an explicit conversation about whether the rule is too strict.
  Don't lower the bar without that conversation.

---

# Commodity Trend Research — closed (2026-06-21)

Two-pass research round evaluating commodity-futures trend/carry strategies
as a potential diversifier alongside the locked equity strategy. Ran on
Databento data (10 CME commodities, 2010-2026); 3 ICE instruments + the
2000-2009 sub-period deferred (Norgate trial 2-yr cap; paid $270 not worth
it for a nice-to-have). Full trail in `reports/commodity_trend/`.

## Outcome

**First pass (long-flat):** three locked signal variants.
- V1 50/200 SMA: Tier D (doesn't generalize from equities).
- V2 Donchian 100/50: Tier D (the "classic CTA" signal lost money).
- V3 vol-adj momentum: Tier C — only variant beating buy-and-hold, but
  failed the 2013-2017 held-out sub-period.

**Second pass (long-short, reframed mandate):** the commodity sleeve's job
was redefined as *uncorrelated returns during equity stress, not matching
Sortino*.
- Test 1 — long-short V3 trend: **Tier C, but satisfies the actual
  mandate.** Made money in 4 of 5 equity-stress windows (+33% / +11% /
  +22% / +6%), −0.05 full-sample correlation with the equity strategy,
  both sub-periods now positive (long-short shorting the 2014-16 oil crash
  fixed the first-pass robustness failure), 27% max DD. Misses Tier B by
  0.03 Sortino (0.67 vs 0.70).
- Test 2 — carry (term-structure): **Tier D. CLOSED PERMANENTLY.** Loses
  money (−5% CAGR, 110×/yr turnover). Genuinely orthogonal (+0.07 vs
  trend, −0.04 vs equity) but an uncorrelated money-loser is useless — the
  50/50 trend+carry blend was *worse* than trend alone.

## Decisions

1. **Carry is a closed question.** Do not revisit unless something
   fundamental changes about how we model term structure, or a published
   result shows the locked carry definition has improved structurally.

2. **Commodity strategy is NOT deployed now.** Neither test cleared Tier B;
   the pre-committed rule ("if neither clears Tier B, move on") is honored.

3. **Long-short V3 trend is filed as DEFERRED deployment candidate** — see
   `reports/commodity_trend/CANDIDATE_FOR_RESURRECTION.md`. This is not an
   override of the pre-committed rule; it is recognizing the deployment
   decision doesn't need to be made now. Re-evaluate when multi-strategy
   becomes viable ($25k+) against then-current criteria and then-available
   information (live equity results, new equity-stress events, crypto
   results). Preserves both options at zero cost.

4. **Infrastructure preserved.** `src/data/databento_loader.py`,
   `src/commodity/*` (loader, signals, vol, engine, metrics), the runner
   scripts, and the 28-test suite all stay for future use.

## Methodological lesson (load-bearing for future strategy specs)

The Test 1 spec said "judge on crisis diversification, **not** Sortino" but
then set the Tier-B gate **on Sortino** (>0.70). That's an internal
inconsistency: the locked numeric criterion was on the very metric the
mandate de-emphasized, producing a 0.03-Sortino "near-miss" that is neither
a clean pass nor a clean fail.

**Rule for future strategy work:** when the mandate says "judge on metric X,
not metric Y," the locked criteria must be expressed on **X**, not on Y. If
the goal is crisis diversification, gate on crisis-period correlation and
crisis-period return — not on full-sample Sortino. We won't repeat this
framing error.

## Triggers to revisit

- Account reaches $25k+ (multi-strategy viable) → evaluate the deferred
  Test 1 candidate.
- A published structural improvement to commodity carry modeling → carry
  could reopen (only then).
- Full-history data (Norgate $270) acquired for some other reason → the
  2000-2009 robustness test on long-short V3 becomes free to run.

---

# Diversifier Search — CLOSED as a structural empirical finding (2026-06-22)

This entry records the close of a multi-round, multi-asset-class search for
a deployable equity-stress diversifier. It is **not a failure to find
something**; it is an empirical finding about **what is available in the
retail systematic toolkit on tested asset classes**. The rationale for the
long-biased portfolio is now explicit rather than implicit.

## What was tested (~10 candidates, disciplined methodology)

| Round | Candidate | Outcome | Notes |
|---|---|---|---|
| Equity early | IBS long-short on QQQ | Tier D | failed lift criterion |
| Equity early | Overnight drift | Tier D | failed |
| Equity early | VIX spike fade (VXX) | Tier D | VXX bleed dominated |
| Equity v1 | Inverse-ETF OFF treatment | rejected | Sortino degradation |
| Equity v1 | IBS shorts overlay | rejected | Sortino degradation |
| Commodity 1 | V1 50/200 SMA trend (long-flat) | Tier D | didn't generalize |
| Commodity 1 | V2 Donchian 100/50 trend (long-flat) | Tier D | lost money |
| Commodity 1 | V3 vol-adj momentum (long-flat) | Tier C | held-out failure |
| Commodity 2 | V3 long-short trend | **near-miss** | Tier C, deferred to $25k+ |
| Commodity 2 | Carry (term-structure) | Tier D | closed permanently |
| Bond | ZN/ZB/ZF 50/200 trend | Tier D (split) | real diversification properties; failed standalone Sortino |
| FX 2A | G6 trend / carry / combined (naive) | Tier D | textbook carry-fails-in-stress pattern |
| FX 2B | G6 carry — post-2022 high-rate sub-period | Tier D | recency hypothesis rejected by data |

## The pattern across all tests

Candidates failed in one or more of three ways:

1. **Standalone Sortino too low** even when diversification properties were
   right (bond trend: −0.29 corr with equity, won 4/4 stress windows, but
   Sortino 0.47 — whipsaw tax in calm periods).
2. **Equity correlation too positive** for a diversifier role (commodity
   trend post-2010 ran +0.5+ in crises; crypto correlation rose from ~0 to
   ~0.5+).
3. **Both fail simultaneously** in the same crises (FX carry: loses
   standalone, loses *more* during equity stress — textbook risk-off
   unwind).

**Particularly meaningful:** the FX recency argument was tested explicitly.
Hypothesis: ZIRP era suppressed carry; post-2022 high-rate regime should
work. The mechanism was specific (rate differentials returned). The data
rejected it: post-2022 carry was *worse* (Sortino delta −0.14, stress wins
1/3 → 0/3), because rate differentials *rearranged* rather than uniformly
widened, leaving JPY-funded carry concentrated in exactly the configuration
that hit the 2024 yen unwind.

## The structural conclusion

**Clean equity-stress diversifiers with deployable standalone returns are
not available in the retail systematic toolkit on the asset classes we
tested**, with one near-miss documented for re-examination at higher
account size.

The mechanism is plausible in hindsight:
- "Clean" diversification (negative equity correlation in stress) tends to
  belong to assets that pay for it the rest of the time (bonds in inflation
  regimes, FX carry in unwinds).
- "Standalone profitable" strategies tend to be long-biased growth assets
  (equities, crypto), which by construction can't hedge equity stress.
- The intersection — uncorrelated in crisis AND profitable standalone — is
  the rare case. We did not find one in the tested universe.

## The deployable architecture (replaces the diversifier-sleeve concept)

**Long-biased trend-following on growth assets, with the trend rule's exit
logic providing crash avoidance, not a separate diversifier sleeve.**

Specifically:
1. **Equity sleeve:** QQQ 50/200 + T-bill OFF (via SGOV) — locked, paper.
2. **Crypto sleeve:** BTC 50/200 + T-bill OFF — IBIT now, MBT futures at
   $25k+. Tier B under tame-the-drawdown mandate (Calmar 1.38, DD halved).
3. **Implicit diversification mechanism:** the trend rule's exit. During
   equity bears, **both sleeves sit in T-bills earning yield**. This is the
   "diversification" — not from a separate hedge sleeve, but from the
   composite portfolio sitting in cash during stress.

During equity bears, the realized portfolio profile is:
- Equity sleeve: in T-bills
- Crypto sleeve: in T-bills (crypto bears coincide with equity bears post-2020)
- Net: ~100% T-bills earning ~3-5%, no active crisis profit, no equity drawdown
- This is the honest, defensible, evidence-based architecture given what the
  research established is and isn't available.

## Triggers to reopen the diversifier search

- Account reaches $25k+ → evaluate the deferred commodity long-short V3
  candidate (CANDIDATE_FOR_RESURRECTION.md).
- A published or empirically-discovered new diversifier class becomes
  available (e.g., a structural change in commodity carry modeling per the
  earlier note).
- New asset classes become retail-accessible (e.g., decentralized prediction
  markets, perpetual swaps with documented carry/funding profiles).
- Live trading reveals an unexpected gap that a diversifier could fill.

Until any of those triggers fires, the search is closed and the long-biased
two-sleeve architecture is the deployment plan.

---

# Leverage Research — CLOSED (2026-06-22)

Final research-queue items run before deployment focus. All three closed.

## TQQQ trend (3x leveraged ETF) — Tier D

- TQQQ 50/200 CAGR +21% (1.7× QQQ trend) BUT Calmar 0.38, MaxDD 55%.
- Leverage amplifies whipsaw approximately as much as it amplifies returns;
  Calmar doesn't improve. Per-era: 2015-2016 chop, QQQ trend lost −10%,
  TQQQ trend lost −28% (3× whipsaw cost). Even in clean bull 2020-21,
  TQQQ trend captured only ~2× QQQ trend (entries/exits eat the leverage).
- The "leveraged-trend gives you upside without drawdown" thesis fails
  empirically. Don't deploy.

## MES vs QQQ index choice — MNQ wins

- 50/200 on SPX (SPY proxy) produces Calmar 0.27 vs NDX 0.52 — half the
  risk-adjusted return for similar drawdown. SPX trend WORKS, just worse.
- Mechanism: NDX has higher structural drift (+30% BAH vs +19%) and more
  persistent trends; the long-biased trend filter monetizes those better.
- Vehicle recommendation: **stay on QQQ shares until ~$50k; switch to MNQ
  (NDX futures) at $50k+, NOT MES (SPX futures).** MES would be a strategy
  change in disguise.

## MES vehicle one-pager — see report

`reports/leverage/01_mes_vehicle_analysis.md` documents the full
account-size threshold logic. Headline: ~10pp Section 1256 tax saving on
ST gains + no-wash-sale + capital efficiency, but threshold is $50k+ for
MNQ (the NDX-tracking variant) given contract notional ~$50k.

## Updated vehicle decision (final)

| Account size | Equity sleeve | Crypto sleeve |
|---|---|---|
| $8k - $25k | QQQ shares (IBKR Lite) | IBIT |
| $25k - $50k | QQQ shares | MBT futures |
| $50k+ | MNQ futures (NDX) | MBT futures |

Research queue cleared. All items closed. Move to deployment focus.

---

# NQ Vehicle Equivalence Test (2026-06-22) — CONFIRMED with caveat

Final research item. Tests whether NQ continuous futures behave like QQQ
shares under the 50/200 trend rule, validating the MNQ migration plan
at $50k+.

## Headline result

- BAH equivalence: NQ +27% CAGR vs QQQ +29% (gap is dividend yield ~0.7%/yr).
- Trend equivalence: NQ trend Calmar 0.49 vs QQQ trend Calmar 0.55 = gap 0.06,
  PASSES the locked 0.10 tolerance.
- Per-era match: all 8 eras qualitatively match (same sign, similar magnitudes).
- After-tax: MNQ wins by ~0.4 pp/yr at $50k+ (Section 1256 + no wash-sale +
  capital efficiency on free margin).

## Two methodology bugs caught (worth documenting forward)

1. `pct_change(back-adjusted)` deflates early-period returns. Cumulative
   back-adjustment lifts the historical level by $3,482 (NQ 2010), so a
   2.8% daily move on actual price becomes 0.95% in pct_change(adj).
   Fix: use `diff(adj) / front.shift(1)` — dollar change divided by
   actual prior-day contract price.

2. Naive futures backtest treats position as 100% invested. Futures only
   consume ~6% margin; the other 94% should earn T-bill ALL the time
   (ON and OFF), not just on OFF days. With futures-collateral accounting,
   the test result changes materially.

Both bugs apply to ANY back-adjusted futures backtest going forward.

## Outcome

MNQ at $50k+ migration plan VALIDATED. The deployment vehicle ladder is
final:

| Account | Equity sleeve | Crypto sleeve |
|---|---|---|
| $8k - $25k | QQQ shares (IBKR Lite) | IBIT |
| $25k - $50k | QQQ shares | MBT futures |
| $50k+ | **MNQ futures (validated this test)** | MBT futures |

## Research phase final close

This is the final research item. The queue is empty. The diversifier search
is closed, the leverage research is closed, the vehicle decisions are all
locked. Operational deployment work is the only outstanding stream.

Trigger to reopen research: live deployment data reveals an unexpected
gap, OR account reaches $25k+ unlocking the parked commodity long-short V3
candidate evaluation.

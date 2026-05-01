# Strategy Specification

Source-of-truth document for the initial strategy set, risk management, and execution logic. Claude Code should treat this as authoritative when implementing. If a requirement here conflicts with general best practice, this document wins — these rules reflect the user's specific preferences, constraints, and style.

**Scope:** three strategies (EWO mean reversion, afternoon reversion, IBS), all long-biased with reversion shorts, options-only execution, SPY/QQQ signal universe.

---

## Account & Global Constraints

| Parameter | Value |
|---|---|
| Starting capital | ~$8,000 |
| Broker | Interactive Brokers (IBKR Pro) |
| Execution venue | Options only — no share trading |
| Instruments (long) | SPY, QQQ, UPRO (3x SPY), TQQQ (3x QQQ) calls |
| Instruments (short) | SQQQ (3x inverse QQQ) calls — SDS/SPXS deferred to v2 |
| Order types | Calls only. No puts. |
| Signal universe | SPY and QQQ (underlyings) |
| Max concurrent positions | 2 (scales to more after validation) |
| Max contracts per position | 1 (scales to 2 after 20 paper + 10 live wins with positive expectancy) |
| Weekly loss budget | **$500 fixed, Mon 9:30 ET → Fri 16:00 ET** |
| Per-trade risk cap | 40% of weekly budget = $200 max |

---

## Instrument Mapping

Signals are generated on the underlying (SPY or QQQ) and executed via options on the ETF family. Calls only, always.

| Signal direction | Underlying | Primary expression | Rationale |
|---|---|---|---|
| Long SPY | SPY | UPRO ATM calls | 3x leverage, affordable premium at $8k NAV |
| Long QQQ | QQQ | TQQQ ATM calls | Most liquid levered option chain |
| Short SPY (reversion) | SPY | *deferred to v2* | SDS/SPXS option spreads too wide for $8k |
| Short QQQ (reversion) | QQQ | SQQQ ATM calls | Cleanest inverse option chain |

**V1 scope:** SPY longs via UPRO, QQQ longs via TQQQ, QQQ shorts via SQQQ. SPY shorts skipped.

---

## DTE & Strike Rules (all strategies)

- **Target DTE at entry:** 7-14 days
- **Minimum DTE at entry:** 5 days
- **Strike (default):** ATM (delta ~0.50)
- **Strike (higher conviction / shorter DTE):** 1-strike ITM (delta ~0.60)
- **Hard exit at 2 DTE** regardless of P&L (assignment + gamma/theta risk)
- **Never hold through expiry**

---

## Strategy 1: EWO Mean Reversion

### Indicator

```
typical_price = (high + low + close) / 3
EWO_raw = SMA(typical_price, 5) - SMA(typical_price, 35)
EWO_z = zscore(EWO_raw, lookback=252)
```

Z-scoring auto-adapts thresholds across volatility regimes. No per-instrument threshold retuning needed.

### Long Entry (SPY or QQQ signal)

All conditions must be true at daily close; order fires at next day's open.

- `EWO_z < -2.0` on SPY, or `EWO_z < -2.2` on QQQ
- `RSI(2) < 10`
- `Close > SMA(200)`
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** UPRO calls (SPY signal) or TQQQ calls (QQQ signal), ATM, 10-14 DTE.
**Higher conviction (z < -2.5 and RSI(2) < 5):** 1-strike ITM, same DTE.

### Short Entry (mean reversion of overbought QQQ)

- `EWO_z > +2.2` on QQQ
- `RSI(2) > 90`
- `Close < SMA(200)` *(only fade rips inside downtrends)*
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** SQQQ ATM calls, 10-14 DTE.

### Exits

Any of the following closes the position:

1. First daily close above SMA(5) for longs / below SMA(5) for shorts (on the underlying)
2. RSI(2) > 70 for longs / RSI(2) < 30 for shorts
3. **3-day time stop** (close at market open on day T+3)
4. -50% premium stop
5. +50% premium → scale out 50%; +100% → scale out another 25%; remaining 25% trails

### Position Sizing

Start: 1 contract per signal. No scaling up until validated.

---

## Strategy 2: Afternoon Reversion

### Windows

- **Observation window:** 9:30-11:00 ET (measure morning move)
- **Trigger window:** 11:00-11:30 ET (wait for confirmation candle)

### Long Entry (fading a morning sell-off)

All conditions must be true during 11:00-11:30 ET:

- `abs(open_to_1100_return) > 0.6 × ATR(20)` — move must be *extended*
- Price at 11:00 within 15% of morning low
- 5-min confirmation candle between 11:00-11:30 closes ≥ 0.08% above the morning low
- No economic release scheduled or delivered during observation window
- No blackout event active (see event table)
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** UPRO calls (SPY) or TQQQ calls (QQQ), **1-strike ITM** (intraday momentum → prioritize delta), 5-9 DTE.

**Higher conviction (morning move > 1.2 × ATR):** same instrument, but ATM for cheaper premium with more gamma.

### Short Entry (fading a morning rip)

Mirror of the above, on QQQ only (SPY shorts deferred):

- `morning_return > 0.6 × ATR(20)` (up-move)
- Price at 11:00 within 15% of morning high
- Confirmation candle closes ≥ 0.08% below morning high

**Instrument:** SQQQ calls, 1-strike ITM, 5-9 DTE.

### Exits

1. **VWAP reclaim** → scale out 50%
2. **Prior day close OR 11am extreme ± morning range** → scale out 30%
3. **Runner (20%) with trailing stop** through EOD
4. Overnight hold: close on first reclaim of entry price OR end of day T+1, whichever first
5. **2-day hard time stop** — no position held past T+1 close
6. Hard stop: 0.5 × morning range below entry for longs (above for shorts)
7. -50% premium stop overrides all above

### Position Sizing

Start: 1 contract per signal.

---

## Strategy 3: IBS (Internal Bar Strength)

### Indicator

```
IBS = (close - low) / (high - low)
```

Computed at 16:00 ET daily close on the underlying.

### Long Entry

- `IBS < 0.20` on SPY, or `IBS < 0.25` on QQQ
- `Close > SMA(200)`
- Prior day was NOT also IBS < threshold (avoids stacking on falling knives)
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room
- **Execute on next day's open (9:31-9:35 ET)**

**Instrument:** UPRO calls (SPY signal) or TQQQ calls (QQQ signal), ATM, 7-9 DTE.

### Short Entry (rare)

- `IBS > 0.80` on QQQ
- `Close < SMA(200)`
- Prior day was NOT also IBS > threshold

**Instrument:** SQQQ ATM calls, 7-9 DTE. Expect this to trigger seldom.

### Exits

1. First daily close above prior day's high (long) / below prior day's low (short)
2. IBS > 0.70 on an exit day (long) / IBS < 0.30 (short)
3. **2-day hard time stop**
4. -50% premium stop
5. +50% premium → scale out 50%; +100% → scale out another 25%; remaining 25% trails

### Position Sizing

Start: 1-2 contracts (IBS is the highest-frequency, smallest-per-trade edge; volume matters).

---

## Event Blackout Logic

Block new entries during these windows. All times ET. Data source: economic calendar API (e.g., FRED, Trading Economics, investpy) — **never hardcode dates**.

| Event | Blackout window |
|---|---|
| FOMC statement | T-0 11:00 → T+1 open |
| FOMC minutes | T-0 13:00 → T-0 close |
| CPI | T-0 07:00 → T-0 11:00 |
| PCE | T-0 07:00 → T-0 11:00 |
| NFP (Employment Situation) | T-0 07:00 → T-0 11:00 |
| GDP | T-0 07:00 → T-0 11:00 |
| ISM Mfg/Services | T-0 09:30 → T-0 11:00 |
| JOLTS | T-0 09:30 → T-0 11:00 |

### Interaction rules

- **Afternoon reversion is blocked for the entire session on any blackout day** — premise is non-news-driven.
- **EWO and IBS**: block entries only during the window. If a position is already open when a release lands, policy is to **flatten 15 minutes before the release** with a limit order at `mid - 0.05` (longs) to exit cleanly.
- Blackout checker is shared infrastructure (`src/risk/blackout.py`) and imported by all strategies.

---

## Regime Filter

A separate module (user is building this — not in this repo's scope) emits a boolean per underlying: `regime_active(SPY) -> bool`, `regime_active(QQQ) -> bool`.

### Integration rules

- **Gate at signal/order time.** If regime is OFF for the relevant underlying when a signal fires, skip entry and log the suppressed signal.
- **Mid-trade regime flips do NOT force exits.** Existing positions run their normal exit logic. (Policy A.)
- **Regime signal is per-underlying**, not global. SPY can be ON while QQQ is OFF, etc.
- If the regime service is unreachable or returns an error: **fail closed** — treat as OFF and skip entries.

---

## Weekly Loss Budget

### Hard rules

- **Budget:** $500 fixed per week, Monday 9:30 ET → Friday 16:00 ET
- **Fixed, not rolling:** the budget is maximum *net* weekly loss. Wins do not extend the budget.
- **Reset:** every Monday at 9:30 ET, the budget returns to $500 regardless of prior week's outcome.

### Risk accounting

```
trade_risk_at_risk = contracts × entry_premium × 0.50   # stop is 50% premium
weekly_realized_loss = max(0, -sum(closed_trade_pnl_this_week))
weekly_open_risk = sum(trade_risk_at_risk for open positions)
weekly_risk_used = weekly_realized_loss + weekly_open_risk
```

### Gates

| Threshold | Behavior |
|---|---|
| `weekly_risk_used < $350` | Normal operation |
| `$350 ≤ weekly_risk_used < $500` | **Soft gate**: new entries allowed at 50% sizing |
| `weekly_risk_used ≥ $500` | **Hard gate**: no new entries until Monday reset |

### Open-position policy on hard-gate trip

Policy A: existing positions run their normal exits unchanged. (Consistent with regime-filter policy.)

### Overnight gap haircut

Positions held overnight count at **1.5× their trade_risk_at_risk** against the weekly budget. Mechanically reduces sizing on overnight holds and discourages stacking overnight exposure.

### Reporting

Print a weekly budget snapshot every trading day at close:

```
=== Weekly Risk Budget ===
Week of: YYYY-MM-DD (Mon-Fri)
Realized P&L: -$XXX
Open positions max loss: -$XXX
Total risk used: $XXX / $500 (XX%)
Entries remaining: up to ~$XXX risk
Next reset: Monday 9:30 ET
```

Alert (log + optional push notification) on:
- Crossing 70% soft gate
- Hitting 100% hard gate
- Any single trade that would alone consume > 40% of budget (should never happen — if it does, that's a sizing bug)

---

## Order Execution Logic

### Pre-trade spread guardrail

Before sending any order, measure `spread_bps = (ask - bid) / mid × 10000`.

```
if spread_pct_of_mid > 15%:    # spread wider than 15% of mid premium
    SKIP TRADE, log as "spread_skip"
elif spread_pct_of_mid > 8%:
    PROCEED only if strategy == "EWO"   # 3-day hold can absorb it
else:
    PROCEED
```

### Order type

**All options orders are LIMIT.** Never market orders on options — spreads can blow out in milliseconds.

### Entry fill-chase ladder

```
t=0s:    place LIMIT at mid
t=15s:   if unfilled, cancel & replace at mid + 25% × spread
t=30s:   cancel & replace at mid + 50% × spread
t=45s:   cancel & replace at mid + 75% × spread
t=60s:   cancel & replace at ask (full aggression)
t=75s:   if still unfilled, CANCEL and re-evaluate signal
```

Abort fill chase immediately if:
- Underlying has moved past entry invalidation level
- Spread_pct > 500% (liquidity evaporated)
- Weekly budget flipped to hard gate during chase

### Exit fill-chase ladder

Same structure, but direction is reversed (`mid - 25% × spread`, etc.), and:

- **Never abort an exit for time**. If the ladder exhausts, drop to `bid` and take what's there.
- **Stop-loss exits skip the ladder entirely**: send limit at `bid - 0.05` immediately to guarantee fill.

### Scale-out orders

- First profit target (+50%): sell 50% of contracts
- Second profit target (+100%): sell another 25%
- Remaining 25%: trails with underlying-price-based stop

---

## Underlying-Price Trailing Stop (for runner)

Premium-based trailing stops are noisy (IV changes mess with them). Use an ATR-based trail on the **underlying** price:

```
# At entry, record entry_underlying_price and entry_ATR_20
# Trail activates once +1R realized

trail_level = max(trail_level_history, current_underlying - 1.5 × ATR_20)   # for longs
# (inverted for shorts on SQQQ)

if underlying crosses trail_level against position:
    send exit limit order on the option
```

Trailing stop ratchets — it only moves in the favorable direction.

---

## Exit Priority (if multiple conditions fire simultaneously)

In order of precedence (first applicable wins):

1. **-50% premium stop** (risk control)
2. **Event blackout flatten** (flatten 15m pre-release)
3. **Time stop** (strategy's max hold exceeded)
4. **DTE stop** (2 DTE reached)
5. **Strategy-specific signal exit** (EWO: close > SMA5; IBS: close > prior high; Afternoon: VWAP reclaim etc.)
6. **Profit-scale targets** (+50%, +100%)
7. **Trailing stop on runner**

---

## Correlation & Concentration Limits

Since EWO and IBS are both daily mean-reversion signals on the same underlyings, they will often fire together.

| Rule | Value |
|---|---|
| Max concurrent positions (total) | 2 |
| Max positions per underlying (SPY OR QQQ) | 2 — but count each strategy's signal as independent |
| Max positions per *strategy family* (EWO + IBS together = mean-reversion family) | 2 |
| Max gross premium deployed | 60% of NAV (~$4,800 at $8k) |

If both EWO and IBS fire on the same underlying the same day: **take EWO** (higher-conviction signal, deeper stop, fits the 2-3 day window better). Log IBS as a suppressed co-signal.

---

## Backtest Requirements Before Live

Before any strategy goes live, it must pass all of:

1. **Historical backtest**: minimum 3 years of data, including options P&L modeling (not just underlying). Must include bid-ask spreads, IV dynamics, and realistic fills (mid ± 25% of spread).
2. **Paper trading**: minimum 20 live-market paper trades with positive expectancy and Sharpe > 0.8.
3. **Regime filter integration validated**: regime-OFF suppression works end-to-end.
4. **Event blackout validated**: at least one FOMC, CPI, and NFP release observed with correct behavior.
5. **Weekly budget enforcement validated**: one full week in paper with a simulated drawdown that trips soft and hard gates.

After all five: go live at **25% of intended size** for 4 weeks. Scale up only if performance matches backtest within reasonable bounds.

---

## Open Questions / Deferred Items

Not blocking v1, but flagged for future iteration:

- SPY shorts via SDS/SPXS (deferred due to option spread quality at $8k NAV)
- Scaling contracts beyond 1 per position (gated on 20 paper + 10 live wins per strategy)
- Options on non-index single-name stocks (out of scope for v1)
- IV-aware entry filter (skip entries when option IV rank > 80%) — nice to have
- Rolling budget experiment (after 3 months of fixed-budget data)

---

## v1.1 — 2026-05-01

**Scope**: Two configuration defaults flipped. **No parameter changes, no
threshold changes, no exit-logic changes.** All v1.0 indicator definitions,
entry conditions, exit rules, sizing, and risk parameters remain in force.

### Defaults flipped

| Config | v1.0 | v1.1 | Rationale |
|---|---|---|---|
| `SQQQ_SHORT_ENABLED` | implicit on | **off** | 8-year backtest (2018-2026): 2 trades, 0% win rate, −$360 total. The IBS-short trigger (`IBS > 0.80 AND close < SMA(200) AND no stacking`) almost never fires; when it has, it's lost. Structural rarity, not small-sample noise. |
| `EWO_ENABLED` | implicit on | **on (acknowledged unvalidated)** | 8-year backtest: 6 trades, 50% win rate, −$25 total. The earlier 2-trade 100% win rate was a small-sample artifact. EWO does NOT have demonstrated edge over a longer sample. Strategy stays enabled because (a) sample is still small (~1 trade/year), (b) the spec's selectivity is intentional, and (c) we don't have evidence to reject it — only evidence not to deploy it confidently. Every EWO signal logs `UNVALIDATED_LOW_N` so the operator sees the caveat at fire time. |

### What was considered for v1.1 and rejected

- **Relaxed EWO thresholds (`z<-1.8`, `RSI<15`)**: refuted by 8-year sample.
  EWO has no edge at v1.0 thresholds either; loosening risks dilution.
- **IV-rank-70 entry gate**: counterfactual on Step 2b baseline shows
  −$250 net P&L if applied. Most stops happen in low-IV regimes, not
  high. Counterproductive.
- **Underlying-price stop @ 1.0× ATR (replacing −50% premium stop)**:
  61% of stops are >1.0× ATR adverse moves on the signal underlying.
  Both stops catch the same trades. No demonstrable improvement.
- **Underlying-price stop @ 0.7× ATR**: forfeits more winner P&L
  (~$499 from MAE analysis) than it saves from earlier stop catches.
- **Premium stop backstop at −65%**: moot. The −50% premium stop fires
  intraday under the current model.
- **Position-limit loosening 2→3**: 4 cases of position_limit suppression
  with +2.89% forward return suggest a possible miss, but N=4 — parked.
- **Budget cap loosening**: 5 cases, +0.95% avg forward — N too small.

### Where this leaves the strategy

The 8-year backtest produced Sharpe 0.11 vs the spec's 0.8 threshold
for live deployment. The strategy as specified is not viable for live
trading without further work. The next workstream is the **regime
filter** described in the user's separate workstream — see DECISIONS.md
for the criterion that would re-open live deployment.

The paper bot remains running for **infrastructure validation**
(reconnect behavior, order routing, EOD push reliability) — not as
strategy validation.

---

## Change Log

| Date | Change | Rationale |
|---|---|---|
| 2026-04-22 | v1.0: initial spec | Three strategies locked, options-only, $500/wk fixed budget, Policy A |
| 2026-05-01 | v1.1: SQQQ short off by default; EWO acknowledged unvalidated | 2018-2026 backtest: 8-year sample refuted SHORT_FADE entirely (2 trades, 0% win) and showed EWO has no demonstrated edge (6 trades, 50% win). No parameter or logic changes. See DECISIONS.md for the deliberation. |

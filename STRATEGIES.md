# Strategy Specification

**Version:** 1.2 (2026-04-22)

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
| Max concurrent positions | 2 total, **max 1 per underlying** |
| Max contracts per position | 1 (scales to 2 after 20 paper + 10 live wins with positive expectancy per strategy) |
| Weekly loss budget | **$500 fixed, Mon 9:30 ET → Fri 16:00 ET** |
| Per-trade risk cap | 40% of weekly budget = $200 max |
| Max gross premium deployed | **40% of NAV** (~$3,200 at $8k) |
| Mandatory entry gate | **IV rank < 70** on the signal underlying's 30-day CMT IV (see IV Rank Gate section) |

**Contract multiplier.** All dollar calculations involving option premium must use the 100× share equivalent:

```
cash_at_risk = contracts × entry_premium × 100 × stop_loss_pct
```

Example: 1 contract at $2.00 premium with a 50% stop = `1 × 2.00 × 100 × 0.50 = $100` at risk.

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

### Long Entry — Primary Tier

All conditions at daily close; order fires at next day's open.

- `EWO_z < -1.8` (SPY) or `EWO_z < -2.0` (QQQ)
- `RSI(2) < 15`
- `Close > SMA(200)`
- `IV rank < 70` (see IV Rank Gate section)
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** UPRO calls (SPY signal) or TQQQ calls (QQQ signal), ATM, 10-14 DTE.

### Long Entry — High-Conviction Tier

All primary conditions above, plus:

- `EWO_z < -2.2` (SPY) or `EWO_z < -2.5` (QQQ)
- `RSI(2) < 10`

**Instrument:** Same, but 1-strike ITM. Eligible for 2 contracts once scaling is unlocked.

### Short Entry (QQQ only)

- `EWO_z > +2.0` on QQQ
- `RSI(2) > 85`
- `Close < SMA(200)` *(only fade rips inside downtrends)*
- `IV rank < 70`
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** SQQQ ATM calls, 10-14 DTE.

### Exits

Any of the following closes the position (see **Exit Priority** for conflict resolution):

1. First daily close above SMA(5) for longs / below SMA(5) for shorts (on the underlying)
2. RSI(2) > 70 (longs) / RSI(2) < 30 (shorts)
3. **3-day time stop** — close at market open on day T+3
4. -50% premium hard stop
5. +50% premium → scale out 50%; +100% → scale out another 25%; remaining 25% trails

### Spread Rule (UPRO gets the carve-out)

EWO holds for up to 3 days, so it can absorb wider spreads:

```
spread_pct = (ask - bid) / mid

if instrument == UPRO:
    proceed if spread_pct ≤ 20%
else:  # TQQQ, SQQQ
    proceed if spread_pct ≤ 8%
```

### Position Sizing

Start: 1 contract per signal. No scaling until validation thresholds met.

---

## Strategy 2: Afternoon Reversion

### Windows (all times ET)

- **Observation window:** 9:30-11:00 — measure morning move
- **Trigger window:** 11:00-11:30 — wait for confirmation candle
- **Fire on the first qualifying 5-min confirmation candle.** Do not wait for 11:30.

### Reference values (units fixed explicitly)

```
morning_move_pts  = abs(price_at_1100 - open_price)      # dollar points
daily_ATR_pts     = ATR(20) on daily bars of underlying  # dollar points
morning_range_pts = morning_high - morning_low           # dollar points
```

### Long Entry (fading a morning sell-off)

All conditions during 11:00-11:30 ET:

- `morning_move_pts > 0.6 × daily_ATR_pts` — move must be extended
- Open-to-11:00 direction is DOWN (price at 11:00 below open)
- `(price_at_1100 - morning_low) ≤ 0.15 × morning_range_pts` — price within 15% of morning range from the low
- 5-min confirmation candle closes ≥ 0.08% above the morning low
- No economic release scheduled or delivered during observation window
- **If today is any blackout day, the entire session is skipped** (afternoon reversion never trades on news days)
- `IV rank < 70` on target option
- Regime filter = ON
- Weekly loss budget has room

**Instrument:** UPRO calls (SPY) or TQQQ calls (QQQ), **1-strike ITM** (delta priority), 5-9 DTE.

**Higher-conviction tier (`morning_move_pts > 1.2 × daily_ATR_pts`):** ATM instead of 1-strike ITM.

### Short Entry (fading a morning rip, QQQ only)

Mirror the above:

- `morning_move_pts > 0.6 × daily_ATR_pts`
- Open-to-11:00 direction is UP
- `(morning_high - price_at_1100) ≤ 0.15 × morning_range_pts`
- Confirmation candle closes ≥ 0.08% below the morning high

**Instrument:** SQQQ calls, 1-strike ITM, 5-9 DTE.

### Exits

1. **Session VWAP reclaim** (VWAP anchored to 9:30 ET) → scale out 50%
2. **Prior day close OR (11:00 extreme ± morning_range_pts)** → scale out 30%
3. **Runner (20%) with trailing stop** through EOD
4. Overnight: close on first reclaim of entry price OR end of day T+1, whichever first
5. **2-day hard time stop** — no position held past T+1 close
6. Underlying-price stop: `0.5 × morning_range_pts` below entry (longs) or above (shorts)
7. -50% premium hard stop overrides all above

### Spread Rule

```
proceed if spread_pct ≤ 8%       # no UPRO carve-out — too fast to absorb slippage
```

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
- Prior day was NOT also IBS below threshold (avoids falling-knife stacking)
- `IV rank < 70` on target option
- Not inside an event blackout window
- Regime filter = ON
- Weekly loss budget has room
- **Execute on next day's open (9:31-9:35 ET)**

**Instrument:** UPRO calls (SPY signal) or TQQQ calls (QQQ signal), ATM, 7-9 DTE.

### Short Entry (QQQ only)

- `IBS > 0.80` on QQQ
- `Close < SMA(200)`
- Prior day was NOT also IBS > threshold

**Instrument:** SQQQ ATM calls, 7-9 DTE. Expect rare triggers.

### Exits

1. First daily close above prior day's high (long) / below prior day's low (short) on underlying
2. IBS > 0.70 (longs) / IBS < 0.30 (shorts) at day close
3. **2-day hard time stop**
4. -50% premium hard stop
5. +50% premium → scale out 50%; +100% → scale out another 25%; remaining 25% trails

### Spread Rule

```
proceed if spread_pct ≤ 8%       # fast hold, can't absorb slippage
```

### Position Sizing

Start: 1-2 contracts (highest-frequency, smallest-per-trade edge).

---

## Event Blackout Logic

Block new entries during these windows. All times ET.

**Data source priority:**
1. Official primary sources — BLS (CPI, NFP, JOLTS), BEA (GDP, PCE), Fed (FOMC statement/minutes), ISM (manufacturing/services), Census (retail sales). Release schedules publish months in advance and are stable.
2. Paid calendar API (Trading Economics, EconDB) as phase-2 convenience.
3. **Never hardcode dates.** The calendar is loaded from YAML/JSON updated from these sources.

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
| Retail Sales | T-0 07:00 → T-0 11:00 |

### Interaction rules

- **Afternoon reversion is blocked for the entire session on any blackout day.**
- **EWO and IBS** block new entries during the window. If a position is open when a release is approaching, **flatten 15 minutes before the release** using a limit order at `mid - max($0.02, 0.5 × spread)` for longs, `mid + max($0.02, 0.5 × spread)` for shorts.
- Blackout checker is shared infrastructure (`src/risk/blackout.py`).

---

## Regime Filter

A separate user-built module emits a boolean per underlying: `regime_active(SPY) -> bool`, `regime_active(QQQ) -> bool`.

### Integration rules

- **Gate at signal/order time.** If regime is OFF for the relevant underlying when a signal fires, skip entry and log the suppressed signal.
- **Mid-trade regime flips do NOT force exits.** (Policy A.) Existing positions run their normal exit logic.
- **Per-underlying, not global.** SPY can be ON while QQQ is OFF.
- **Fail closed.** If the regime service errors or is unreachable: treat as OFF, skip entries.

---

## Weekly Loss Budget

### Hard rules

- **Budget:** $500 fixed per week, Monday 9:30 ET → Friday 16:00 ET
- **Fixed, not rolling** — wins do not extend the budget
- **Reset:** Monday 9:30 ET, back to $500 regardless of prior week

### Risk accounting (with correct 100× multiplier)

```
trade_risk_at_risk    = contracts × entry_premium × 100 × 0.50     # 50% stop
weekly_realized_loss  = max(0, -sum(closed_trade_pnl_this_week))
weekly_open_risk      = sum(trade_risk_at_risk for all open positions)
weekly_risk_used      = weekly_realized_loss + weekly_open_risk
```

### Gates

| Threshold | Behavior |
|---|---|
| `weekly_risk_used < $350` | Normal operation |
| `$350 ≤ weekly_risk_used < $500` | **Soft gate** — new entries at 50% sizing |
| `weekly_risk_used ≥ $500` | **Hard gate** — no new entries until Monday |

### Open-position policy on hard-gate trip

**Policy A:** existing positions run their normal exits unchanged.

### Overnight gap haircut

Positions held overnight count at **1.5× their `trade_risk_at_risk`** against the weekly budget. Discourages stacking overnight exposure.

### Reporting

Daily close summary:

```
=== Weekly Risk Budget ===
Week of: YYYY-MM-DD
Realized P&L: -$XXX
Open positions max loss (100x applied): -$XXX
Total risk used: $XXX / $500 (XX%)
Entries remaining: up to ~$XXX risk
Next reset: Monday 9:30 ET
```

Alerts on 70% soft gate and 100% hard gate. Flag any single trade sized >40% of budget (= sizing bug).

---

## Order Execution Logic

### Pre-trade spread guardrail

Uses percent throughout — no bps. `spread_pct = (ask - bid) / mid`.

Strategy × instrument thresholds:

| Strategy | TQQQ / SQQQ | UPRO |
|---|---|---|
| EWO | ≤ 8% | ≤ 20% |
| Afternoon Reversion | ≤ 8% | ≤ 8% |
| IBS | ≤ 8% | ≤ 8% |

Skipped trades logged as `spread_skip` with strategy, instrument, spread%, and IV rank for post-hoc analysis.

### Order type

**All options orders are LIMIT.** No market orders, ever.

### Entry fill-chase ladder

Linear ramp from mid to the far side of the spread. No dollar floor — IBKR rounds sub-penny orders correctly, and a floor breaks the ramp on narrow spreads.

```
step = spread / 4      # linear mid → ask (or mid → bid) over four rungs

t=0s:    LIMIT at mid
t=15s:   cancel & replace at mid + 1 × step (buy) or mid - 1 × step (sell)
t=30s:   cancel & replace at mid + 2 × step (buy) or mid - 2 × step (sell)
t=45s:   cancel & replace at mid + 3 × step (buy) or mid - 3 × step (sell)
t=60s:   cancel & replace at ask (buy) / bid (sell) — full aggression
t=75s:   if still unfilled, CANCEL and re-evaluate signal
```

Monotonically increasing aggression regardless of spread width. For a $0.04 spread: step = $0.01. For a $0.40 spread: step = $0.10.

Abort immediately if:
- Underlying has moved past the entry invalidation level
- Spread widens > 3× original
- Weekly budget flipped to hard gate during chase

### Exit fill-chase ladder

Same structure, mirrored direction. **Exits never abort for time** — if ladder exhausts, drop to `bid` (longs) / `ask` (shorts) and take the fill.

### Stop-loss exits

Skip the ladder. Send limit at `bid - max($0.02, 0.25 × spread)` for longs (or `ask + max($0.02, 0.25 × spread)` for shorts) immediately. The floor here is defensive — crossing the market by at least 2¢ guarantees fill.

### Scale-out orders

- +50% premium → sell 50%
- +100% premium → sell 25% more
- Final 25% trails

---

## Underlying-Price Trailing Stop (for runner)

Premium-based trailing stops are noisy because IV shifts. Use ATR on the **underlying**:

```
# At entry, record entry_underlying_price and entry_ATR_20
# Trail activates once +1R realized (R = initial stop distance in underlying terms)

for a long position (UPRO or TQQQ call = long SPY/QQQ direction):
    trail_level = max(trail_level_history, current_underlying_price - 1.5 × ATR_20)
    # ratchets up only

for a short position (SQQQ call = short QQQ direction):
    qqq_trail_level = min(qqq_trail_level_history, current_qqq_price + 1.5 × ATR_20_QQQ)
    # ratchets down only

if underlying crosses the trail level adversely:
    send exit limit order on the option (uses exit fill-chase ladder)
```

---

## Exit Priority (first applicable wins)

1. **-50% premium hard stop**
2. **Ex-dividend protection** — if long call is deep ITM (delta > 0.85) AND the **next session is ex-div on the held option's own underlying** (e.g., UPRO's own ex-div, not SPY's), close by **15:50 ET on T-1** (the day before ex-div). Morning-of (T-0) is too late — early exercise happens overnight between T-1 close and T-0 open, so by the open you've already been assigned if a counterparty exercised.
3. **Event blackout flatten** — 15 min before release
4. **Time stop** (strategy-specific max hold)
5. **DTE stop** (2 DTE reached)
6. **Strategy signal exit** (EWO: close > SMA5 / RSI flip; IBS: close > prior high / IBS reversion; Afternoon: VWAP reclaim etc.)
7. **Profit scale-out targets** (+50%, +100%)
8. **Trailing stop on runner**

---

## Concurrent-Signal Rules

Constraints: max 2 concurrent positions, max 1 per underlying.

**Both SPY and QQQ fire simultaneously, both slots open:** take both, one per underlying.

**Same underlying fires two different-strategy signals in the same session (only one slot allowed on that underlying):** prefer in order **EWO > Afternoon Reversion > IBS** (conviction order). Log the suppressed signal.

**Same underlying, same strategy signals twice (data-timing edge case):** take the first, ignore the second.

**Only one slot left open, signals fire on both SPY and QQQ:** prefer the one with stronger statistical signal strength (more extreme z-score, lower IBS, larger morning-move-to-ATR ratio). Log the suppressed signal.

---

## IV Rank Gate (mandatory for v1)

Applied at order time. IV rank is computed on the **signal underlying's (SPY or QQQ) 30-day constant-maturity ATM IV**, not on the specific option contract being purchased. This keeps the measurement on a stable, deep-history surface and avoids noise from thin leveraged-ETF chains and per-expiry IV volatility.

```
cmt_iv_30d = interpolate ATM IV between nearest expiries bracketing 30 DTE
iv_rank    = (cmt_iv_30d - min_cmt_iv_52w) / (max_cmt_iv_52w - min_cmt_iv_52w) × 100

if iv_rank >= 70:
    SKIP TRADE, log as "iv_skip"
```

Gate applies to any option trade on that underlying family:
- SPY signal → gate UPRO entries on SPY's IV rank
- QQQ signal → gate TQQQ/SQQQ entries on QQQ's IV rank

### Bootstrap / warm-up

Option-chain history accumulates slowly from live scraping, so v1 seeds the 52-week IV range from a historical data source:

- **Primary seed:** CBOE VIX (for SPY) and VXN (for QQQ) — both are 30-day ATM IV measures with decades of public history via CBOE/FRED. VIX/VXN are close proxies for SPY/QQQ's 30-day CMT IV (same methodology base, small skew differences).
- On live start, load the prior 252 trading days of VIX/VXN closes to seed `min_cmt_iv_52w` and `max_cmt_iv_52w`.
- Each session thereafter, compute today's CMT IV from the live IBKR option chain, append to a rolling 252-day deque, and recompute min/max.
- **Phase 2 enhancement:** replace VIX/VXN seed with direct CMT-IV historicals from the local chain archive once ~6 months of data has accumulated.

### Fallback

If IV rank cannot be computed (IBKR chain data missing, bootstrap file absent, no valid bracketing expiries): **fail closed — skip entry, log as `iv_data_missing`**.

Rationale: long call buyers bleed when IV is rich. 70 is the cutoff where theta/vega drag typically overwhelms directional edge on 5-14 DTE long calls.

---

## Backtest Requirements Before Live

Before any strategy goes live:

1. **Historical backtest ≥ 3 years** with options P&L modeling: bid-ask spreads, IV dynamics, fills at mid ± 25% of spread, 100× contract multiplier applied correctly.
2. **Paper trading ≥ 20 live-market trades** per strategy with positive expectancy, Sharpe > 0.8.
3. **Regime filter integration validated** end-to-end.
4. **Event blackout validated** — at least one FOMC, CPI, and NFP observed with correct behavior.
5. **Weekly budget enforcement validated** — one simulated-drawdown week tripping soft and hard gates.
6. **Leveraged-ETF decay measurement** — UPRO/TQQQ beta to SPY/QQQ measured over typical 1-3 day holds. Decay > 5% relative underperformance vs. 3× beta is a red flag that warrants revisiting the instrument choice.
7. **Spread realism** — backtest fills must incorporate historical bid-ask, not mid-only.
8. **IV rank filter validated** — skipped trades logged and analyzed to confirm the filter catches unfavorable regimes.

After all pass: go live at **25% of intended size for 4 weeks**. Scale to full size only if live results track backtest within tolerance.

---

## Open Questions / Deferred Items

- SPY shorts via SDS/SPXS (deferred due to option spread quality at $8k NAV)
- Scaling contracts beyond 1-2 per position (gated on per-strategy validation thresholds)
- Options on single-name stocks (out of scope for v1)
- Rolling budget experiment (after 3 months of fixed-budget data)
- Calendar API integration (phase 2 — official sources suffice for v1)
- Replacing VIX/VXN IV seed with locally-stored CMT-IV historicals (phase 2, ~6 months after go-live)

---

## Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-04-22 | Initial spec — three strategies, options-only, $500/wk fixed budget, Policy A. |
| 1.1 | 2026-04-22 | **Bug fixes:** 100× contract multiplier on risk math; unified spread units to percent (removed bps); variable fill/exit offsets tied to spread via `max($0.02, 0.5 × spread)`. **Ambiguities resolved:** ATR reference in dollar points with matching units on morning move; "15%" means 15% of morning range (not price); session VWAP anchored 9:30 ET; position caps = max 2 total and max 1 per underlying; afternoon reversion fires on first qualifying candle. **Concerns addressed:** UPRO spread carve-out to ≤20% for EWO only; EWO primary trigger loosened to `z<-1.8 AND RSI(2)<15` with high-conviction tier preserved at `z<-2.2, RSI(2)<10`; gross premium cap tightened 60% → 40% of NAV; IV rank <70 promoted to mandatory v1 entry gate; ex-div exit rule added to priority list; official release schedules designated as v1 calendar source. |
| 1.2 | 2026-04-22 | **Fix: ex-div timing** — rule now triggers at **15:50 ET on T-1** (day before ex-div), not T-0 open. Early exercise happens overnight, so morning-of was already too late. **Fix: IV rank surface** — moved from per-expiry option IV (noisy, no deep history) to **signal underlying's 30-day constant-maturity ATM IV** (stable, decades of data). Gate applies family-wide (SPY IV rank gates UPRO; QQQ IV rank gates TQQQ/SQQQ). **Fix: IV rank bootstrap** — seed 52-week min/max from CBOE VIX (SPY) / VXN (QQQ) historicals on live start, then roll the window forward with live CMT-IV appended each session. Fail closed if data missing. **Fix: fill-chase ladder** — replaced `max($0.02, 0.5 × spread)/4` formula (which broke monotonicity on narrow spreads) with linear `step = spread / 4`, ramping mid → ask over t=15/30/45s. |

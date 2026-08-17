# CL1–USO Time-Difference Strategy

Source-of-truth spec for the CL1/USO bot. Same authority rules as `STRATEGIES.md`: if this document conflicts with general best practice, this document wins.

---

## The Edge

USO is an ETF that holds front-month-ish WTI crude futures (CL). Two clocks are out of sync:

| Instrument | Trading hours (ET) |
|---|---|
| CL futures (NYMEX/Globex) | Sun 18:00 → Fri 17:00, ~23h/day (daily break 17:00–18:00) |
| USO (NYSE Arca) | 09:30 → 16:00 RTH |

Because USO's fair value is a direct function of the CL contracts it holds, every CL move *must* eventually show up in USO. But USO can only react while the equity market is open, and even intraday the futures lead the ETF. That produces two tradeable expressions of the same mispricing:

1. **Opening dislocation.** Overnight CL moves get priced into USO's opening print. When the open under- or over-reacts to the CL-implied fair value, USO converges toward fair value during the first part of the session.
2. **Intraday lag.** During RTH, sharp CL moves propagate to USO with a lag. When USO deviates from its CL-implied fair value beyond noise, it reverts.

Both are captured by one signal: the **z-scored residual spread** between log(USO) and beta × log(CL1).

**V1 trades USO shares only.** CL is a signal input — we never trade the future. This keeps margin, roll mechanics, and overnight risk out of the execution path. A futures-leg hedge (true market-neutral spread) is a v2 item.

---

## Signal Construction

All computed on synchronized 1-minute closes (RTH only — bars where both instruments printed):

```
beta      = cov(r_USO, r_CL) / var(r_CL)        over beta_lookback returns (~5 RTH days)
spread_i  = log(USO_i) - beta × log(CL_i)        for the last z_lookback bars (~1 RTH day)
z         = (spread_now - mean(spread)) / std(spread)
```

- Rolling **beta** absorbs USO's expense drag, contango/backwardation roll drift, and the fact that USO holds a mix of contract months. No hardcoded hedge ratio.
- Working in **returns/log space** makes the signal immune to CL contract-roll price gaps and USO share splits.
- **z-scoring** auto-adapts thresholds across vol regimes (same philosophy as the EWO spec).
- The overnight gap needs no special-casing: the first synchronized bar of a session naturally embeds the full overnight CL move, so an under-reacting USO open shows up as a large |z| at 09:31.

### CL1 definition

Front month CL by nearest expiry, **rolling to the next month when the front contract is within 5 calendar days of expiry** (mirrors USO's own roll schedule and avoids expiry-week noise). Historical/backtest data uses back-adjusted continuous CL; live uses the qualified specific contract month.

---

## Rules

### Entry (evaluated each synchronized minute bar)

| Condition | Action |
|---|---|
| `z < -entry_z` (USO cheap vs CL-implied fair value) | BUY USO |
| `z > +entry_z` (USO rich) | SELL SHORT USO (config flag, default ON) |

Gates, all required:
- At least `min_history` synchronized bars accumulated (no signal on a cold start)
- Time < 15:30 ET (no new entries in the last half hour)
- Daily loss kill switch not tripped, position cap has room
- Flat (one position at a time, v1)

### Exit (first applicable wins)

1. **Stop:** z extends beyond `±stop_z` against the position (the "mispricing" was information, not lag)
2. **Convergence:** |z| ≤ `exit_z` — the trade thesis completed
3. **Time stop:** held longer than `max_hold_minutes`
4. **EOD flatten:** 15:55 ET, always. **No overnight USO positions, ever** — holding USO overnight *is* the exposure this strategy exists to fade.

### Default parameters (locked for v1 — no tuning until a full backtest round is reviewed)

| Param | Default | Notes |
|---|---|---|
| `beta_lookback` | 1950 bars | ~5 RTH days of 1-min returns |
| `z_lookback` | 390 bars | ~1 RTH day |
| `entry_z` | 2.0 | |
| `exit_z` | 0.25 | |
| `stop_z` | 4.0 | |
| `max_hold_minutes` | 120 | |
| `min_history` | 450 bars | |
| `allow_short` | true | |
| entry cutoff / flatten | 15:30 / 15:55 ET | |

---

## Execution

- **USO shares, LIMIT orders only**, priced at the NBBO mid, capped by `MAX_POSITION_USD`.
- Position size: `floor(MAX_POSITION_USD / price)` shares, minimum 1.
- Spread guardrail: skip entries when USO's bid-ask spread > 10 bps of mid (it's normally ~1-2 bps; wider means something is wrong).
- Exits reuse the limit-at-mid logic; the EOD flatten and stop exits price through the spread (marketable limit) to guarantee the fill.

## Risk

- `MAX_POSITION_USD` per-position cap (default $500)
- `MAX_DAILY_LOSS_USD` daily kill switch (default $200): trips on realized PnL, blocks all new entries for the rest of the day, existing position still runs its normal exits
- One concurrent position, no overnight holds, paper mode by default per the repo safety rules

## Validation gate before live

1. Backtest on ≥ 1 year of synchronized 1-min data with slippage + commission modeled — positive expectancy after costs
2. ≥ 20 paper trades with positive expectancy
3. Kill switch and EOD flatten each observed working in paper at least once

---

## Explicitly out of scope for v1

- Trading the CL leg (market-neutral futures hedge) — v2
- Overnight positioning ahead of the USO open
- Sub-minute / HFT-style latency competition (we trade minutes-scale convergence, not microstructure)
- BNO/UCO/SCO or other oil ETFs

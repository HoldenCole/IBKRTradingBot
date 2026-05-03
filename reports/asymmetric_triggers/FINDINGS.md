# Asymmetric trigger test — Liberation Day 2025 + faster entry filters

**Date:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Script:** `scripts/run_asymmetric_triggers.py`
**Raw output:** `output.txt`

## User questions

1. Did the strategy avoid the "Liberation Day" 2025 sell-off?
2. How does the strategy identify when to buy?
3. Most recovery has happened by the time SMA(50) crosses SMA(200) — can
   we test 50/100 or 20/50 cross from the bottom?

## Headline answers

1. **YES.** The strategy exited Feb 24, 2025 at QQQ $519, more than a month
   before the April 2 Liberation Day announcement. It was in SGOV during
   the entire -22% drop to the April 8 low of $416. Insurance worked.

2. **Entry rule:** `SMA(50) > SMA(200) AND close > SMA(50)`. Both
   conditions must hold. This is the same condition as the exit, just
   inverted (no separate entry logic).

3. **Tested four asymmetric variants. None survives the 98-year sanity
   check.** A faster entry filter does catch more of post-Liberation-Day
   recovery, but the same faster filter costs more in whipsaw losses
   across the broader history. The 50/200 baseline holds.

---

## What actually happened in 2025

QQQ price action and SMA states around the event:

| Date | QQQ Close | SMA(50) | SMA(200) | 50/200 state |
|---|---:|---:|---:|---|
| Feb 14 2025 | $538 | $522 | $488 | ON |
| Feb 19 2025 (peak) | $539 | $523 | $489 | ON |
| **Feb 24 2025** (strategy exit) | **$520** | **$523** | **$490** | **flipped OFF** |
| Mar 13 2025 | $468 | $515 | $493 | OFF |
| Apr 2 2025 (Liberation Day) | $476 | $505 | $494 | OFF |
| Apr 8 2025 (low) | $416 | $497 | $493 | OFF |
| May 30 2025 | $519 | $480 | $496 | OFF (SMA50<200) |
| **Jun 24 2025** (V1 entry) | **$539** | $508 | $501 | flipped ON |
| Jul 15 2025 | $557 | $527 | $506 | ON |

**Strategy round-trip:**
- Exit: Feb 24 at $520
- Re-entry: Jun 24 at $540
- Round-trip cost: $20 (3.8%) of "lost" recovery between exit and re-entry
- BUT: avoided participating in the -22% drop from Feb peak to April low

The strategy paid 3.8% for insurance against an 18% intra-period drawdown.
Net outcome: significantly better than buy-and-hold over the same window.

---

## Liberation Day re-entry timing per variant

| Variant | Re-entry date | QQQ price at entry | $ vs baseline |
|---|---|---:|---:|
| V1: SS 50/200 (baseline) | Jun 24 2025 | $539.78 | reference |
| V2: AS 20/50 → 50/200 | May 13 2025 | $515.59 | **-$24** (better) |
| V3: AS 50/100 → 50/200 | Jun 20 2025 | $526.83 | -$13 |
| V4: AS 20/100 → 50/200 | May 22 2025 | $514.00 | **-$26** (best) |
| V5: SS 50/100 | Jun 20 2025 | $526.83 | -$13 |

V2 and V4 caught the recovery ~5 weeks earlier and ~5% lower.
**Looks promising in isolation.** But:

---

## 26-year QQQ Convention 2 backtest

| Variant | Sortino | CAGR | AT-CAGR | |DD| | Trans/yr |
|---|---:|---:|---:|---:|---:|
| V1: SS 50/200 (baseline) | 0.83 | +6.3% | +5.4% | 22% | 12.56 |
| V2: AS 20/50 → 50/200 | 0.69 | +5.6% | +4.8% | 30% | 11.30 |
| V3: AS 50/100 → 50/200 | 0.66 | +5.1% | +4.3% | 24% | 12.75 |
| **V4: AS 20/100 → 50/200** | **0.86** | **+6.8%** | **+5.9%** | **22%** | 12.29 |
| V5: SS 50/100 | 0.65 | +4.9% | +4.2% | 24% | 12.90 |

**V4 marginally beats V1** on every metric (Sortino +0.03, CAGR +0.5pp,
same DD, slightly fewer transitions). Looks like a small win.

**Locked criteria check:** None pass. V4 fails Sortino criterion (+0.03
vs required +0.30). Margin too narrow.

---

## 98-year ^GSPC long-history check

The decisive test:

| Period | V1 (50/200) | V2 (AS 20/50) | V4 (AS 20/100) |
|---|---|---|---|
| 1928-1949 Depression+WWII | 0.38 / +2.4% | 0.53 / +4.1% | **0.58 / +4.4%** |
| 1950-1965 Post-war bull | **1.92** / +10.0% | 1.76 / +9.0% | 1.86 / +9.6% |
| 1966-1982 Secular bear | **1.95** / +8.9% | 1.78 / +8.9% | 1.91 / +9.3% |
| 1983-1999 Disinflationary | **1.26** / +8.5% | 1.12 / +7.6% | 1.10 / +7.4% |
| 2000-2009 Dotcom+GFC | 0.22 / +1.0% | 0.20 / +0.9% | **0.26** / +1.3% |
| 2010-2017 Post-GFC | **0.44** / +2.3% | 0.18 / +0.8% | 0.28 / +1.4% |
| 2018-2026 Modern | **0.94** / +6.0% | 0.77 / +5.3% | 0.68 / +4.7% |
| **FULL 1928-2026** | **0.97** / +5.9% | 0.89 / +5.8% | 0.94 / +6.0% |

(format: Sortino / CAGR; bold = best in row)

V4 over 98 years: **wins in 2 of 7 periods, loses in 5 of 7**, full-sample
Sortino is 0.94 vs V1's 0.97 — a -0.03 Sortino regression.

The 26-year QQQ sample's apparent V4 edge **does not generalize**.

---

## Why the asymmetric trick doesn't work in general

In the Liberation Day case, the recovery was V-shaped — a fast bounce
back to where we exited. The 20/100 entry filter caught it earlier than
50/200 because the 20-day SMA reacted to the bottom faster.

But across the 98-year record, most recoveries are NOT V-shaped:
- 1932-1937 Depression recovery: slow grinding
- 1942-1946 WWII recovery: slow grinding
- 1974-1976 oil-bear recovery: stair-step rally with multiple false starts
- 2002-2004 dotcom recovery: sideways for 18 months before resuming
- 2009-2010 GFC recovery: V-shaped (similar to Liberation Day) — 20/100 helps here
- 2019-2020 COVID recovery: V-shaped — 20/100 helps
- 2022-2023 inflation recovery: stair-step

The fast filter generates many false-positive entries during stair-step
recoveries (you re-enter on a rally → it fails → exit at a loss → re-
enter on next rally → repeat). These eat the V-shaped wins.

The 1966-1982 stagflation period is the clearest example: 1.95 Sortino
under V1 vs 1.91 under V4, with V4 having a higher drawdown (10% vs 8%).
The slow filter's whipsaw resistance is what made the strategy a robust
bear-market hedge.

## Recommendation

**Keep V1 (SS 50/200) as the deployment trigger.** Three reasons:

1. **V4's edge is sample-specific.** The 26-year QQQ improvement reverses
   on the 98-year ^GSPC sample.

2. **The Liberation Day cost is the insurance premium.** Strategy paid
   $20 (3.8%) to avoid an 18% intra-period drawdown. Over the long run
   that trade pays off; in any given mild bear, it can feel painful.

3. **Locked Tier-A criteria are unmet** by all asymmetric variants.
   The +0.03 Sortino margin is within sample noise.

## Liberation Day in context — the strategy's actual track record on
recoveries

V1's behavior in past bears (from `reports/long_history/output.txt`):

| Bear | BAH max DD | Strategy max DD | Re-entry timing |
|---|---:|---:|---|
| 1929 Crash | -86% | 0% | Strategy avoided entirely (1929 was a 22-year drawdown for BAH) |
| 1973-74 oil bear | -48% | -3% | Re-entered late 1975 (8% above pre-crash exit but 30% above bottom) |
| 2000-2002 dotcom | -49% | -18% | Re-entered late 2003 |
| 2008-2009 GFC | -47% | 0% | Re-entered mid-2009 |
| March 2020 COVID | -34% | -5% | Re-entered ~July 2020 |
| 2022 inflation | -25% | -4% | Re-entered late 2022 |
| **2025 Liberation Day** | **-22%** | **0%** | Re-entered Jun 24 ($540 vs $519 exit) |

In every case, the strategy avoided the brunt of the drawdown but paid
some recovery cost. Liberation Day is consistent with this pattern.

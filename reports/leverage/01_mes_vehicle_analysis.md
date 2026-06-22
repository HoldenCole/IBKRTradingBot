# MES Vehicle Analysis — Account-Size-Conditional Thresholds

**Date:** 2026-06-22
**Scope:** NOT a strategy test. Vehicle-decision one-pager — when does it
make sense to switch the equity sleeve from QQQ shares to 1 MES (Micro
E-mini S&P 500) futures? Mirrors the crypto MBT analysis structure.
**Effort:** ~1 hour, no backtest.

## The three vehicles

| | QQQ shares (deployed now) | 1 MES future | 1 ES future |
|---|---|---|---|
| Underlying | Nasdaq-100 | S&P 500 | S&P 500 |
| Notional per unit | fully fractional (~$540 share) | **$5 × SPX ≈ $37,500** @ SPX 7500 | $50 × SPX ≈ $375,000 |
| Margin | full cash | **~$2,455 overnight** | ~$24,550 |
| Tax treatment | ordinary ST / 20% LTCG; wash-sale applies | **Section 1256: 60/40, mark-to-market, NO wash-sale** | same |
| Trading hours | market hours | 24/5 | 24/5 |
| Roll/expiry | none | quarterly (Mar/Jun/Sep/Dec) | quarterly |
| Operational load | lowest | medium (futures acct + roll + Form 6781) | high (~10x position size) |

## The tax math (the main reason to consider MES)

For QQQ 50/200 trend, the average position is held ~25 days (well under 1
year → short-term). Compare marginal rates on a short-term gain (Texas, no
state income tax):

| Vehicle | Short-term gain rate | Notes |
|---|---|---|
| QQQ shares | **37%** (federal ordinary) | unless held >1yr → 20% LTCG (rare under trend) |
| MES (§1256) | **~26.8%** | 0.6×20% + 0.4×37%, *regardless* of holding period |

**MES saves ~10 percentage points of tax on every short-term gain** —
recurring on every flip. Same calculation we did for crypto MBT; the
arithmetic is identical for any §1256 instrument.

§1256's mark-to-market means you pay tax on unrealized year-end gains, so it
is a cash-flow shift (you owe in year N on a position you might exit at a
different price in year N+1) but not a rate disadvantage. **§1256 also
EXEMPTS from wash-sale**, which is genuinely material for a 50/200 strategy
that whipsaws ~6× per year (some of those round-trips include losses that
would be wash-saled on shares but are immediately deductible on futures).

## Sizing — why account size is the deciding factor

1 MES = ~$37,500 notional at SPX 7,500 (scales with SPX). Can't hold a
fractional contract, so MES is only "naturally sized" when the intended
equity allocation is ≈ one (or a few) contract notionals.

| Account | Sensible equity sleeve (~70-100% of account) | 1 MES notional | Fit |
|---|---|---|---|
| **$8k (current)** | $5,600 - $8,000 | $37,500 | **MES = 4.7× the sleeve — far too big.** QQQ shares only. |
| $15k | $10,500 - $15,000 | $37,500 | MES still 2.5-3.5× oversized. QQQ shares. |
| $25k | $17,500 - $25,000 | $37,500 | MES 1.5× oversized; doesn't fit cleanly. QQQ shares. |
| **$40k** | $28,000 - $40,000 | $37,500 | **MES ≈ 1 contract becomes natural** at the sleeve top. **Threshold.** |
| $60k+ | $42,000 - $60,000 | $37,500 | 1 MES = ~70-90% of sleeve, clean fit |
| $100k+ | $70,000+ | $37,500 (or use 2 MES) | 1-2 contracts; consider stepping up to ES at $375k+ |

(If SPX rises to 8,500 or 9,000 these thresholds shift up ~15-20%.)

**Key change from the crypto MBT analysis:** MES threshold is **$40k+**, not
$25k+, because SPX trades at much higher levels than BTC. The $25k+ crypto
threshold doesn't translate.

## Capital efficiency (secondary MES advantage)

MES needs ~$2,455 margin for ~$37,500 notional → **~93% of capital stays
in T-bills earning yield while you hold full SPX exposure.** At $40k account
with a $37,500 MES sleeve, the other ~$37,500 of unencumbered cash earns
~3-5%/yr T-bill. Net of the futures basis financing cost (≈ T-bill, so
~wash), this means full equity exposure AND most of the capital still
yields.

At $40k+ this is meaningful. At $8k it doesn't matter — you're not
capital-constrained on a $6k sleeve to start with.

## The catch — MES is SPX, not NDX

QQQ tracks the Nasdaq-100 (NDX), MES tracks SPX. **Different indices.**
- QQQ historically delivers higher CAGR with higher vol (tech-heavy)
- SPX is broader, less concentrated, more stable

Switching to MES is not just a vehicle change — it's an **index change**.
Does the 50/200 trend rule work equally well on SPX? That's the empirical
question in `02_mes_vs_qqq_index_test.md`. **You should not switch to MES
until that test confirms the strategy works on the SPX series.**

The alternative is **MNQ** (Micro E-mini Nasdaq-100): same Section 1256
treatment, but tracks NDX so it's a true vehicle-swap of QQQ shares. MNQ
specs:
- $2 × NDX ≈ $50,000 notional at NDX 25,000
- Margin ~$3,000 overnight
- Threshold even higher than MES (~$50k+) because NDX trades at a higher
  level than SPX

So the realistic path:
- **<$40k: QQQ shares** (deployed today)
- **$40k+ AND SPX trend test passes: 1 MES** (cheaper threshold, tax-efficient)
- **$50k+ AND prefer NDX exposure: 1 MNQ** (same strategy, futures vehicle)

## Recommendation by account-size threshold

- **$8k (now) → QQQ shares.** MES at 1 contract is 4.7× too big to size a
  reasonable sleeve. Deploy as planned. Pay ordinary ST tax on flips, accept
  the wash-sale complexity. Use IBKR Lite for $0 commission.

- **$40k → vehicle-switch threshold.** Once a sensible equity sleeve
  approaches one MES notional (~$37,500), **switch to MES** — IF the SPX
  trend test passes (see companion doc). The ~10pp §1256 tax saving on
  short-term gains + §1256 wash-sale exemption + capital efficiency now
  outweigh the operational complexity (futures-enabled account, quarterly
  roll, Form 6781 at year-end).

- **$50k+ AND want to keep NDX exposure → MNQ.** Same logic but on
  Nasdaq-100. Threshold is higher because NDX trades higher; MNQ notional
  per contract is ~$50k. Same tax treatment as MES.

- **$375k+ → consider full ES.** Notional 10× MES; clean fit only for
  meaningful position sizes.

## One-line answer

**Deploy QQQ shares now at $8k.** Switch to **1 MES at ~$40k+** (or **MNQ at
~$50k+** to keep NDX exposure), but only AFTER confirming the strategy works
on the chosen index (`02_mes_vs_qqq_index_test.md`). The ~10pp §1256 tax
edge + wash-sale exemption + capital efficiency are real, recurring wins
on a strategy that flips 6×/yr — but the account has to be big enough to
size a single contract sensibly. Confirm Section 1256 treatment of equity
index futures with a tax advisor (well-established, but worth confirming).

Sources: [CME MES contract specs](https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.contractSpecs.html), [Section 1256 tax treatment](https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.margins.html)

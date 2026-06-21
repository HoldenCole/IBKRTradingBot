# Crypto Vehicle Decision — Spot/IBIT vs MBT Futures (by account size)

**Date:** 2026-06-21
**Scope:** NOT a strategy test. BTC 50/200 trend is locked (Test 1, Tier B).
This is the deployment-vehicle question: how to *hold* the BTC exposure.
**Effort:** one-pager / ~1 hour, no backtest.

## The three vehicles

| | Spot crypto (Coinbase etc.) | IBIT (spot BTC ETF) | MBT (Micro BTC future) |
|---|---|---|---|
| Instrument type | property | security (ETF) | regulated futures contract |
| Contract/granularity | fully fractional | fully fractional (shares) | 0.10 BTC = **~$6,400 notional** @ BTC $64k |
| Margin | full cash | full cash | **~$2,000/contract** (rest stays in T-bills) |
| Expense/carry | ~0.1-0.4% trade fees | **0.25%/yr** expense | no expense; financing ≈ embedded in basis ≈ T-bill (≈ wash) |
| Tax treatment | cap gains; **no wash-sale rule** | cap gains; wash-sale applies; 1099-B | **Section 1256: 60/40 blended, mark-to-market** |
| Roll / expiry | none | none | monthly contract, must roll |
| Trading hours | 24/7 | market hours only | ~24/5 (CME) |
| Operational load | medium (custody/security) | **lowest** (normal ETF) | highest (futures acct, margin, roll, MTM) |

## The tax math (the main reason to consider MBT)

For the BTC trend strategy, holds in choppy/bear periods are often <1 year →
**short-term**. Comparing the marginal rate on a short-term gain at the top
federal bracket (Texas, no state tax):

| Vehicle | Short-term gain rate | Note |
|---|---|---|
| Spot / IBIT | **37%** (ordinary) | unless held >1yr → 20% LTCG |
| MBT future (§1256) | **~26.8%** | 0.6×20% + 0.4×37%, *regardless of holding period* |

**MBT saves ~10 percentage points of tax on short-term gains** — a real,
recurring edge for a strategy that turns over a few times a year. Caveat:
CME Bitcoin futures are regulated futures contracts and are generally treated
as §1256 by practitioners, but the IRS has not issued crypto-futures-specific
guidance — **confirm with a tax advisor**. §1256 also forces **mark-to-market
at year-end** (you pay tax on unrealized gains annually), which is a cash-flow
consideration, not a rate disadvantage.

Offsetting nuance: **spot crypto has NO wash-sale rule** (it's property), so
you can harvest losses freely and immediately re-enter — a genuine edge during
choppy/bear periods that IBIT (security, wash-sale applies) and even §1256
(MTM makes it moot) don't share. For a trend strategy that takes many small
losses in chop, spot's free loss-harvesting partially offsets MBT's lower rate.

## Sizing — why account size is the deciding factor

1 MBT = ~$6,400 notional (at BTC $64k; scales with BTC price — at $100k BTC
it's $10k). You can't hold a *fraction* of a futures contract, so MBT is only
"natural-sized" when your intended BTC allocation is ≈ one (or a few) contract
notionals.

| Account | Sensible BTC sleeve (15-25%) | 1 MBT notional | Fit |
|---|---|---|---|
| **$8k (current)** | $1,200 - $2,000 | $6,400 | **MBT = 80% of account — far too big.** Spot/IBIT only. |
| $15k | $2,250 - $3,750 | $6,400 | MBT still oversized (>40%). Spot/IBIT. |
| **$25k** | $3,750 - $6,250 | $6,400 | **MBT ≈ 1 contract becomes natural** at the top of a sensible sleeve. Threshold. |
| $40k+ | $6,000 - $10,000 | $6,400 | MBT clean (1 contract ≈ 16-25%). §1256 + capital efficiency win. |

(If BTC rises to ~$100k, 1 MBT = $10k and these thresholds shift up ~1.5×.)

## Capital efficiency (secondary MBT advantage)

MBT needs only ~$2k margin per ~$6.4k notional. The other ~$4.4k stays in
T-bills earning yield while you hold full BTC exposure. The futures basis
charges ~risk-free for that leverage, which roughly nets against the T-bill
earned — so it's ~expense-neutral *and* frees capital. At larger account
sizes this lets the BTC sleeve coexist with the equity/other sleeves without
tying up cash. At $8k it's irrelevant (you're not capital-constrained on a
$1-2k sleeve).

## Recommendation by account-size threshold

- **$8k (now) → Spot/IBIT.** MBT's ~$6.4k notional cannot size a small crypto
  sleeve in an $8k account. Use **IBIT** in the taxable brokerage (simplest,
  fractional, normal ETF) — accept the 0.25%/yr expense and ordinary-income
  ST tax, and hold past 1yr for LTCG where the trend allows. (Spot on an
  exchange is an alternative for the no-wash-sale loss-harvesting edge, but
  adds custody/security overhead — not worth it at this size.)

- **$25k → transition point.** Once a sensible BTC sleeve (~20-25%) approaches
  one MBT notional (~$6.4k), **switch to MBT futures.** The ~10pp §1256 tax
  saving on short-term gains + capital efficiency now outweigh the operational
  complexity (futures-enabled account, monthly roll, year-end MTM / Form 6781).

- **$40k+ → MBT clearly.** 1-2 MBT contracts size cleanly to a 15-25% sleeve;
  §1256 + capital efficiency are unambiguous wins.

## One-line answer

**Deploy BTC trend via IBIT now (at $8k); switch to MBT futures at ~$25k+**
when the sleeve grows into one contract's notional and the Section 1256
tax edge (~10pp on short-term gains) starts paying for the added operational
complexity. Confirm §1256 treatment with a tax advisor before relying on it.

Sources: [CME MBT contract specs](https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/micro-bitcoin.contractSpecs.html),
[IBKR CME Micro Bitcoin](https://www.interactivebrokers.com/en/trading/cme-micro-bitcoin.php)

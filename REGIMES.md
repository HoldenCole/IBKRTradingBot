# Four-Quadrant Regime Framework

The user's organizing model for the whole strategy portfolio: two macro axes — growth (up/down) and inflation (up/down) — give four regimes, and each strategy family trades only in the quadrant(s) where it has demonstrated edge. No strategy is expected to work everywhere; the portfolio is the thing that works.

Implementation: `src/regime/quadrant.py`. Evidence below, 2026-08-17.

---

## Classifier (locked)

Market-based proxies, ex-ante, no publication lag, no tuning (Faber-standard 10-month SMA):

- **Growth ON:** SPY month-end close > its 10-month SMA
- **Inflation ON:** DBC (broad commodities) month-end close > its 10-month SMA
- Month T uses the classification computed at the end of month T-1. Fail closed when history is insufficient.

## What each quadrant paid (next-month annualized, 2007–2026)

| Quadrant | Months | SPY | QQQ | USO | DBC | GLD | TLT |
|---|---|---|---|---|---|---|---|
| G+I− GROWTH | 75 | +14.9% | **+22.3%** | −1.8% | −1.4% | +6.6% | +6.4% |
| G+I+ REFLATION | 108 | +7.4% | +9.5% | **+15.6%** | +11.7% | +13.6% | +0.5% |
| G−I+ STAGFLATION | 19 | −10.7% | −6.0% | −8.4% | −7.9% | −7.5% | **+4.2%** |
| G−I− DEFLATION | 30 | **+31.4%** | +44.3% | −28.4% | −3.3% | +24.6% | +8.5% |

Two textbook confirmations (equities own G+I−, commodities own G+I+) and two corrections to the textbook: in ex-ante-classified stagflation **everything** loses except bonds/cash (not gold, not commodities), and DEFLATION months hide violent post-crash equity rebounds the lagging classifier hasn't caught up to — the known whipsaw cost of trend-based regime signals.

A naive monthly playbook rotation returned +11.2% CAGR vs SPY's +10.8% with max drawdown −35% vs −51%.

---

## Strategy-family mapping (with evidence)

### equity_reversion → GROWTH (G+I−)

The user's existing `STRATEGIES.md` suite, tested per spec on 24y of SPY/QQQ daily data (signals and exits exactly as written, next-open entries, long side):

- **IBS** (the workhorse — 557 SPY / 686 QQQ trades): ungated +8.1 / +10.4 bps per trade, 65-66% win. **Gated to G+I−: +12.9 / +18.6 bps per trade, 70% win both, t = 1.64 / 2.37** — roughly double the per-trade edge on ~40% of the trades, and **positive in every era** (SPY: +35/+14/+4 bps across 07-12/13-19/20-26; QQQ: +27/+3/+41).
  - Within labeled history, the G+I− quadrant produced ~2/3 of total IBS P&L from ~40% of trades. The spec's own `Close > SMA200` filter already handles the growth axis; the inflation axis (skip G+I+) is where the quadrant gate adds new information.
- **EWO**: fires ~0.4x/year per symbol at spec thresholds (11 SPY / 8 QQQ trades in 24 years) — positive but far too few events to judge or gate. Note: at these frequencies EWO is a garnish, not a strategy leg.
- **Afternoon reversion**: needs long intraday history — deferred to the IBKR data pull.

### commodity_trend → REFLATION (G+I+)

CL surge + trend-filter calls (`CL_SURGE_CALLS.md`): its SMA50/200 oil-trend gate is effectively a REFLATION detector for the energy complex. Era-stable in the 10y test (+65 bps/event, all eras positive).

### defense → STAGFLATION + DEFLATION

T-bills / stand down. Refusing to trade is the demonstrated best play in G−I+. The DEFLATION rebound problem (missing +31%/+44% annualized recovery months) is an open research question — candidates: faster reclassification, or the IBS suite un-gated during G−I− (its 12-33 G−I− trades were strongly positive but n is too small to lock).

---

## Rules

- Gates apply at **entry time only**; open positions run their normal exits (Policy A, consistent with STRATEGIES.md).
- Classifier definition is **locked** — no per-strategy tuning of the SMA length or proxies. If a change is proposed, it must be justified on data not used to propose it.
- Fail closed: unclassifiable ⇒ no new entries for gated families.

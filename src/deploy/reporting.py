"""Per-strategy + per-basket P&L and drawdown reporting (item #13).

Consumes the persisted ledger + an equity-curve history (computed daily by
the orchestrator) and produces:
  - per-strategy P&L (realized + unrealized + cash drag)
  - per-basket aggregation
  - per-basket drawdown (peak-to-trough on the basket equity curve)
  - operator-readable daily report (plain text — single file artifact)

The daily orchestrator appends to a daily-snapshot CSV after each
successful daily-check. This module produces reports off that history.

Why a separate module: keeping reporting decoupled from the ledger lets
us produce reports against historical snapshots without re-running the
strategy. Same module serves the year-end reconciliation against IBKR
1099-B.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from src.deploy.baskets import BasketConfig
from src.deploy.portfolio import Ledger


@dataclass
class BasketReport:
    basket_id: str
    name: str
    target_weight: float
    enabled: bool
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    market_value: float
    drift_pct: float | None = None     # |realized_weight - target_weight| / target_weight; None if not enabled or NAV is 0


@dataclass
class PortfolioReport:
    as_of: date
    nav: float
    cash: float
    baskets: list[BasketReport]
    strategy_pnl: dict[str, float]      # realized P&L per strategy_id
    notes: list[str] = field(default_factory=list)


def _strategy_to_basket(cfg: BasketConfig) -> dict[str, str]:
    out: dict[str, str] = {}
    for bid, b in cfg.baskets.items():
        for s in b.strategies:
            out[s.id] = bid
    return out


def _strategy_to_lot_cost_basis(ledger: Ledger) -> dict[str, float]:
    """Cumulative cost-basis of OPEN lots per strategy (denominator for
    unrealized P&L calc)."""
    out: dict[str, float] = {}
    for lot in ledger.open_lots():
        cost = lot.quantity * (lot.cost_basis_per_share
                               + lot.disallowed_wash_basis_addon)
        out[lot.strategy_id] = out.get(lot.strategy_id, 0.0) + cost
    return out


def build_portfolio_report(
    cfg: BasketConfig, ledger: Ledger, prices: dict[str, float],
    nav: float, as_of: date,
) -> PortfolioReport:
    """Produce a point-in-time portfolio report.

    `nav` is the broker's authoritative net-liquidation value; `prices`
    are current quotes for all held symbols. `as_of` is the trading date
    the report represents.
    """
    strat_to_basket = _strategy_to_basket(cfg)
    realized_by_strat = ledger.realized_pnl_by_strategy()
    mv_by_strat = ledger.market_value_by_strategy(prices)
    cost_by_strat = _strategy_to_lot_cost_basis(ledger)

    notes: list[str] = []
    by_basket: dict[str, BasketReport] = {}
    cash_used = 0.0

    for bid, b in cfg.baskets.items():
        # Realized + unrealized aggregated across this basket's strategies
        realized = sum(
            realized_by_strat.get(s.id, 0.0) for s in b.strategies
        )
        mv = sum(mv_by_strat.get(s.id, 0.0) for s in b.strategies)
        cost = sum(cost_by_strat.get(s.id, 0.0) for s in b.strategies)
        unrealized = mv - cost
        cash_used += mv

        drift = None
        if b.enabled and nav > 0:
            realized_weight = mv / nav
            if b.weight > 0:
                drift = abs(realized_weight - b.weight) / b.weight

        by_basket[bid] = BasketReport(
            basket_id=bid, name=b.name, target_weight=b.weight,
            enabled=b.enabled, realized_pnl=realized,
            unrealized_pnl=unrealized, total_pnl=realized + unrealized,
            market_value=mv, drift_pct=drift,
        )

    cash = nav - cash_used
    # Cash sliver flagging (matches the "Stage-1 cash sliver stays in sweep" decision)
    if cash < 0:
        notes.append(f"Negative cash sliver {cash:.2f}; "
                     f"possible MV/quote mismatch — investigate")
    return PortfolioReport(
        as_of=as_of, nav=nav, cash=cash,
        baskets=sorted(by_basket.values(), key=lambda r: r.basket_id),
        strategy_pnl=realized_by_strat, notes=notes,
    )


# ===== Equity-curve history + drawdown =====

@dataclass
class EquityHistoryRow:
    trading_date: date
    nav: float
    basket_mv: dict[str, float]   # basket_id -> MV; basket "cash" for cash


def append_daily_history(
    path: Path, row: EquityHistoryRow, basket_ids: Iterable[str],
) -> None:
    """Append a daily history row to a CSV. Creates the file with a
    header if it doesn't exist. Idempotent on the same trading_date —
    overwrites the existing row for that date (so re-runs of the same
    day don't produce duplicate rows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bids = list(basket_ids)
    headers = ["trading_date", "nav"] + [f"basket_{b}_mv" for b in bids] + ["cash"]

    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open() as f:
            existing = list(csv.DictReader(f))
        existing = [r for r in existing if r.get("trading_date") != row.trading_date.isoformat()]

    new_row = {"trading_date": row.trading_date.isoformat(),
               "nav": f"{row.nav:.4f}"}
    for b in bids:
        new_row[f"basket_{b}_mv"] = f"{row.basket_mv.get(b, 0.0):.4f}"
    new_row["cash"] = f"{row.basket_mv.get('cash', 0.0):.4f}"
    existing.append(new_row)
    existing.sort(key=lambda r: r["trading_date"])

    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in existing:
            w.writerow({h: r.get(h, "") for h in headers})


def compute_drawdown(equity_series: list[tuple[date, float]]) -> dict:
    """Peak-to-trough drawdown over the series. Returns
    {max_dd, max_dd_start, max_dd_trough, current_dd, peak}."""
    if not equity_series:
        return {"max_dd": 0.0, "max_dd_start": None, "max_dd_trough": None,
                "current_dd": 0.0, "peak": 0.0}
    peak = equity_series[0][1]
    peak_date = equity_series[0][0]
    max_dd = 0.0
    max_dd_start = peak_date
    max_dd_trough = peak_date
    cur_peak = peak
    cur_peak_date = peak_date
    for d, eq in equity_series:
        if eq > cur_peak:
            cur_peak = eq
            cur_peak_date = d
        dd = (cur_peak - eq) / cur_peak if cur_peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_start = cur_peak_date
            max_dd_trough = d
        if eq > peak:
            peak = eq
            peak_date = d
    last_d, last_eq = equity_series[-1]
    current_dd = (peak - last_eq) / peak if peak > 0 else 0.0
    return {
        "max_dd": max_dd, "max_dd_start": max_dd_start,
        "max_dd_trough": max_dd_trough,
        "current_dd": current_dd, "peak": peak,
    }


def format_report(report: PortfolioReport) -> str:
    """Operator-readable plain text. One file per daily run."""
    lines: list[str] = []
    lines.append(f"=== PORTFOLIO REPORT — {report.as_of} ===")
    lines.append(f"NAV: ${report.nav:,.2f}")
    lines.append(f"Cash: ${report.cash:,.2f}")
    lines.append("")
    lines.append(f"{'Basket':<6}{'Name':<42}{'Tgt %':>7}{'MV':>12}"
                 f"{'Real P&L':>11}{'Unrl P&L':>11}{'Drift':>8}")
    for b in report.baskets:
        enabled_mark = "ON " if b.enabled else "off"
        drift_s = f"{b.drift_pct*100:.1f}%" if b.drift_pct is not None else "-"
        lines.append(
            f"{enabled_mark} {b.basket_id:<3}{b.name:<42}"
            f"{b.target_weight*100:>6.0f}%"
            f"{b.market_value:>12,.2f}"
            f"{b.realized_pnl:>+11,.2f}"
            f"{b.unrealized_pnl:>+11,.2f}"
            f"{drift_s:>8}")
    lines.append("")
    if report.strategy_pnl:
        lines.append("Realized P&L by strategy:")
        for sid, pnl in sorted(report.strategy_pnl.items()):
            lines.append(f"  {sid:<28} {pnl:>+10,.2f}")
    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for n in report.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)

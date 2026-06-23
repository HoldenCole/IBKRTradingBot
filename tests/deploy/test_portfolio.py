"""Tests for the portfolio ledger: lot tracking, HIFO matching, realized
P&L, ST/LT classification, wash-sale flagging (QQQ only), per-strategy +
per-basket aggregation."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.deploy.portfolio import (
    Ledger, LotStatus, RealizedSale, TaxLot,
)


# ===== Basic lot lifecycle =====

def test_buy_creates_open_lot():
    L = Ledger()
    lot = L.record_buy(strategy_id="qqq", symbol="QQQ",
                       quantity=10, price=500.0, trade_date=date(2024, 6, 20))
    assert lot.status == LotStatus.OPEN
    assert lot.quantity == 10
    open_lots = L.open_lots("QQQ")
    assert len(open_lots) == 1
    assert open_lots[0].cost_basis_per_share == 500.0


def test_sell_matches_against_open_lot_full_close():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10,
                 price=500.0, trade_date=date(2024, 6, 20))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10,
                          price=550.0, trade_date=date(2024, 7, 20))
    assert len(sales) == 1
    assert sales[0].realized_pnl == pytest.approx(500.0)  # (550-500) * 10
    assert sales[0].is_long_term is False                  # held 30 days
    assert L.open_lots("QQQ") == []


def test_sell_partial_leaves_remainder():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10,
                 price=500.0, trade_date=date(2024, 6, 20))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=4,
                          price=520.0, trade_date=date(2024, 7, 1))
    assert sales[0].quantity == 4
    assert sales[0].realized_pnl == pytest.approx(80.0)
    remaining = L.open_lots("QQQ")
    assert len(remaining) == 1
    assert remaining[0].quantity == 6


def test_oversell_raises():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=5,
                 price=500.0, trade_date=date(2024, 6, 20))
    with pytest.raises(ValueError, match="insufficient"):
        L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10,
                      price=520.0, trade_date=date(2024, 7, 1))


def test_sell_with_no_open_position_raises():
    L = Ledger()
    with pytest.raises(ValueError, match="no open lots"):
        L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=1,
                      price=520.0, trade_date=date(2024, 7, 1))


# ===== HIFO matching =====

def test_hifo_sells_highest_basis_first():
    """3 buys at $400, $500, $450; sell 1 share should consume the $500 lot."""
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=400.0,
                 trade_date=date(2024, 1, 10))
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=500.0,
                 trade_date=date(2024, 1, 11))
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=450.0,
                 trade_date=date(2024, 1, 12))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=1,
                          price=480.0, trade_date=date(2024, 6, 1))
    assert len(sales) == 1
    assert sales[0].cost_basis_per_share == 500.0          # the HIGHEST
    assert sales[0].realized_pnl == pytest.approx(-20.0)   # 480 - 500 = -20
    remaining_bases = sorted(L.open_lots("QQQ"), key=lambda L: L.cost_basis_per_share)
    assert [r.cost_basis_per_share for r in remaining_bases] == [400.0, 450.0]


def test_hifo_spans_multiple_lots_when_qty_exceeds_one():
    """Sell 3 shares from lots [400, 500, 450, 450]: consumes 500, 450, 450
    (HIFO). The 400-lot remains."""
    L = Ledger()
    for px, d in [(400, 10), (500, 11), (450, 12), (450, 13)]:
        L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=px,
                     trade_date=date(2024, 1, d))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=3,
                          price=480.0, trade_date=date(2024, 6, 1))
    bases = sorted(s.cost_basis_per_share for s in sales)
    assert bases == [450.0, 450.0, 500.0]
    remaining = L.open_lots("QQQ")
    assert len(remaining) == 1 and remaining[0].cost_basis_per_share == 400.0


# ===== ST vs LT classification =====

def test_short_term_under_one_year():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=500.0,
                 trade_date=date(2024, 1, 1))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=1,
                          price=520.0, trade_date=date(2024, 12, 31))
    assert sales[0].is_long_term is False


def test_long_term_over_one_year():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=1, price=500.0,
                 trade_date=date(2023, 1, 1))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=1,
                          price=600.0, trade_date=date(2024, 1, 2))
    # 366 days = long-term (>1yr)
    assert sales[0].is_long_term is True


# ===== Wash-sale rule (QQQ shares only) =====

def test_qqq_loss_followed_by_buy_within_30_days_is_wash_sale():
    """Classic wash sale: sell QQQ at loss, buy back within 30 days.
    The loss must be DISALLOWED and added to the new lot's basis."""
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 6, 1))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10,
                          price=450.0, trade_date=date(2024, 7, 1))   # -$500 loss
    # No replacement yet -> wash sale not flagged on the sale itself
    assert sales[0].wash_sale_disallowed_loss == 0.0
    # Buy back 5 days later -> retroactively disallow the loss
    new_lot = L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10,
                           price=460.0, trade_date=date(2024, 7, 6))
    # The realized sale should now be flagged
    updated_sales = L.realized_sales()
    assert updated_sales[0].wash_sale_disallowed_loss == pytest.approx(500.0)
    assert updated_sales[0].wash_sale_replacement_lot_id == new_lot.lot_id
    # The new lot's basis addon is PER SHARE: $500 disallowed / 10 shares = $50/sh
    assert new_lot.disallowed_wash_basis_addon == pytest.approx(50.0)


def test_qqq_loss_after_more_than_30_days_is_not_wash_sale():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 6, 1))
    sales = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10,
                          price=450.0, trade_date=date(2024, 7, 1))
    # Buy back 35 days later -> wash sale window has passed
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=460.0,
                 trade_date=date(2024, 8, 5))
    assert L.realized_sales()[0].wash_sale_disallowed_loss == 0.0


def test_qqq_gain_is_not_wash_sale_even_with_quick_rebuy():
    """Wash-sale applies ONLY to losses. Gains followed by quick rebuy
    are unaffected."""
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 6, 1))
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10, price=550.0,
                  trade_date=date(2024, 7, 1))
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=560.0,
                 trade_date=date(2024, 7, 5))
    assert L.realized_sales()[0].wash_sale_disallowed_loss == 0.0


def test_sgov_loss_with_quick_rebuy_NOT_flagged_wash_sale():
    """Locked: wash-sale tracking is ONLY for QQQ shares (§1256 / non-stock
    instruments are out of scope). SGOV losses are not flagged."""
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="SGOV", quantity=10, price=100.0,
                 trade_date=date(2024, 6, 1))
    L.record_sell(strategy_id="qqq", symbol="SGOV", quantity=10, price=99.0,
                  trade_date=date(2024, 7, 1))   # tiny loss
    L.record_buy(strategy_id="qqq", symbol="SGOV", quantity=10, price=99.5,
                 trade_date=date(2024, 7, 5))
    assert L.realized_sales()[0].wash_sale_disallowed_loss == 0.0


def test_wash_sale_applies_within_strategy_only():
    """A QQQ loss in strategy A and a QQQ rebuy in strategy B is NOT a
    wash sale per our model (each sleeve is its own account-equivalent).
    Real IRS rules don't distinguish, but for OUR strategy attribution
    we keep sleeves independent to avoid cross-sleeve bookkeeping
    confusion. (User can elect to consolidate at year-end if desired.)"""
    L = Ledger()
    L.record_buy(strategy_id="qqq_A", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 6, 1))
    L.record_sell(strategy_id="qqq_A", symbol="QQQ", quantity=10, price=450.0,
                  trade_date=date(2024, 7, 1))
    # Rebuy in DIFFERENT strategy
    L.record_buy(strategy_id="qqq_B", symbol="QQQ", quantity=10, price=460.0,
                 trade_date=date(2024, 7, 5))
    assert L.realized_sales()[0].wash_sale_disallowed_loss == 0.0


def test_wash_sale_chain_with_subsequent_sell_recognizes_disallowed_loss():
    """Lot A bought $500, sold $450 (loss -$500 disallowed).
    Lot B bought $460 (basis bumped to $510 effective).
    Lot B sold $480: 'realized loss' is (480-510)*10 = -$300 — i.e. the
    original disallowed $500 loss now partially flows through, plus the
    additional drop from $460 to $480 = +$200, netting -$300.
    """
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 6, 1))
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10, price=450.0,
                  trade_date=date(2024, 7, 1))
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=460.0,
                 trade_date=date(2024, 7, 6))
    sales_second = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10,
                                 price=480.0, trade_date=date(2024, 10, 1))
    # adjusted basis was 510; sold at 480 -> realized -30 per share = -300
    assert sales_second[0].realized_pnl == pytest.approx(-300.0)


# ===== Per-strategy + per-basket attribution =====

def test_realized_pnl_by_strategy_separates_sleeves():
    L = Ledger()
    # QQQ sleeve gain
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 1, 1))
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10, price=550.0,
                  trade_date=date(2024, 3, 1))   # +$500
    # BTC sleeve loss
    L.record_buy(strategy_id="btc", symbol="IBIT", quantity=100, price=60.0,
                 trade_date=date(2024, 1, 1))
    L.record_sell(strategy_id="btc", symbol="IBIT", quantity=100, price=55.0,
                  trade_date=date(2024, 3, 1))   # -$500
    by_strat = L.realized_pnl_by_strategy()
    assert by_strat["qqq"] == pytest.approx(500.0)
    assert by_strat["btc"] == pytest.approx(-500.0)


def test_realized_pnl_by_basket_aggregates_strategies():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 1, 1))
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=10, price=550.0,
                  trade_date=date(2024, 3, 1))
    L.record_buy(strategy_id="btc", symbol="IBIT", quantity=100, price=60.0,
                 trade_date=date(2024, 1, 1))
    L.record_sell(strategy_id="btc", symbol="IBIT", quantity=100, price=55.0,
                  trade_date=date(2024, 3, 1))
    strategy_to_basket = {"qqq": "3", "btc": "2"}
    by_basket = L.realized_pnl_by_basket(strategy_to_basket)
    assert by_basket["3"] == pytest.approx(500.0)
    assert by_basket["2"] == pytest.approx(-500.0)


def test_mark_to_market_by_strategy_attributes_open_lots():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 1, 1))
    L.record_buy(strategy_id="btc", symbol="IBIT", quantity=100, price=60.0,
                 trade_date=date(2024, 1, 1))
    L.record_buy(strategy_id="qqq", symbol="SGOV", quantity=40, price=100.0,
                 trade_date=date(2024, 1, 1))    # sleeve's parked-cash position
    mv = L.market_value_by_strategy({"QQQ": 540.0, "IBIT": 70.0, "SGOV": 100.5})
    # qqq strategy: 10 QQQ * 540 + 40 SGOV * 100.5 = 5400 + 4020 = 9420
    # btc strategy: 100 IBIT * 70 = 7000
    assert mv["qqq"] == pytest.approx(5400 + 4020)
    assert mv["btc"] == pytest.approx(7000)


# ===== End-to-end whipsaw scenario (exercises wash-sale + HIFO together) =====

def test_whipsaw_realistic_qqq_sequence():
    """Realistic QQQ whipsaw: enter, exit at loss, re-enter in window
    (loss disallowed), exit again at small gain. Final realized P&L
    should reflect the wash-sale basis bumping.
    """
    L = Ledger()
    d = date(2024, 6, 1)
    # 1. Enter: buy 7 QQQ @ 540
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=7, price=540.0,
                 trade_date=d)
    # 2. Exit at loss: sell 7 @ 500, 10 days later
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=7, price=500.0,
                  trade_date=d + timedelta(days=10))    # -280 loss
    # 3. Re-enter within wash window: buy 7 @ 510, 5 days later
    new_lot = L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=7,
                            price=510.0, trade_date=d + timedelta(days=15))
    # First sale should now be flagged as wash; new_lot basis bumped by
    # $280 / 7 sh = $40 per share
    sales_after_rebuy = L.realized_sales()
    assert sales_after_rebuy[0].wash_sale_disallowed_loss == pytest.approx(280.0)
    assert new_lot.disallowed_wash_basis_addon == pytest.approx(40.0)
    # 4. Exit second position at small gain: sell 7 @ 555
    sales2 = L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=7,
                           price=555.0, trade_date=d + timedelta(days=60))
    # Adjusted basis = 510 + 40 = 550; gain = (555-550)*7 = 35
    assert sales2[0].realized_pnl == pytest.approx(35.0)
    # Combined "actual" P&L across both round-trips:
    # Raw: (-280) + (45*7=+315) = +35
    # That matches the second sale's P&L since the first was wash-disallowed.
    # If we naively summed raw realized P&L: -280 + 35 = -245
    # The disallowed_loss field tells us: -245 + 280 (disallowed) = +35 actual.
    total_raw = sum(s.realized_pnl for s in L.realized_sales())
    total_disallowed = sum(s.wash_sale_disallowed_loss for s in L.realized_sales())
    assert total_raw + total_disallowed == pytest.approx(35.0)


def test_snapshot_returns_full_state():
    L = Ledger()
    L.record_buy(strategy_id="qqq", symbol="QQQ", quantity=10, price=500.0,
                 trade_date=date(2024, 1, 1))
    L.record_sell(strategy_id="qqq", symbol="QQQ", quantity=5, price=550.0,
                  trade_date=date(2024, 3, 1))
    snap = L.snapshot()
    assert "QQQ" in snap.open_lots_by_symbol
    assert snap.open_lots_by_symbol["QQQ"][0].quantity == 5
    assert len(snap.realized_sales) == 1
    assert snap.realized_sales[0].realized_pnl == pytest.approx(250.0)

from src.portfolio.order_calc import build_orders


WEIGHTS = {"TQQQ": 0.30, "ERX": 0.315, "GDX": 0.1575, "DBC": 0.2275}


def test_fresh_account_all_buys_sum_to_equity():
    orders = build_orders(WEIGHTS, 11000.0)
    assert all(o["action"] == "BUY" for o in orders)
    assert abs(sum(o["target"] for o in orders) - 11000.0) < 0.01


def test_scales_linearly_with_equity():
    small = {o["ticker"]: o["target"] for o in build_orders(WEIGHTS, 10000.0)}
    big = {o["ticker"]: o["target"] for o in build_orders(WEIGHTS, 100000.0)}
    for t in WEIGHTS:
        assert abs(big[t] - 10 * small[t]) < 0.01


def test_contribution_deploy_is_buys_only():
    held = {"TQQQ": 3300.0, "ERX": 3465.0, "GDX": 1733.0, "DBC": 2503.0}
    orders = build_orders(WEIGHTS, 12500.0, held)
    assert all(o["action"] == "BUY" for o in orders)


def test_drift_inside_band_holds_not_sells():
    # TQQQ 3pp overweight — inside the 5pp band, must not sell
    held = {"TQQQ": 3630.0, "ERX": 3465.0, "GDX": 1733.0, "DBC": 2503.0}
    orders = build_orders(WEIGHTS, 11000.0, held)
    tqqq = next(o for o in orders if o["ticker"] == "TQQQ")
    assert tqqq["action"] == "HOLD" and tqqq["delta"] == 0.0


def test_drift_beyond_band_sells():
    held = {"TQQQ": 4500.0, "ERX": 3000.0, "GDX": 1600.0, "DBC": 2400.0}
    orders = build_orders(WEIGHTS, 12000.0, held)
    tqqq = next(o for o in orders if o["ticker"] == "TQQQ")
    assert tqqq["action"] == "SELL" and tqqq["delta"] == -900.0


def test_rotation_sells_departed_ticker_fully():
    # ticker no longer in the matrix must be sold regardless of band
    held = {"SCO": 550.0, "TQQQ": 3300.0}
    orders = build_orders(WEIGHTS, 11000.0, held)
    sco = next(o for o in orders if o["ticker"] == "SCO")
    assert sco["action"] == "SELL" and sco["delta"] == -550.0

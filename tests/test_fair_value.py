"""FairValueModel: beta recovery and lag detection on synthetic data."""

import numpy as np

from src.strategies.cl1_uso_spread import FairValueModel, SpreadParams


def make_pair(n: int, beta: float = 1.0, noise: float = 1e-4, seed: int = 7):
    """Synthetic CL path with USO tracking it at the given beta."""
    rng = np.random.default_rng(seed)
    r_cl = rng.normal(0, 0.0008, n)
    r_uso = beta * r_cl + rng.normal(0, noise, n)
    cl = 70.0 * np.exp(np.cumsum(r_cl))
    uso = 75.0 * np.exp(np.cumsum(r_uso))
    return cl, uso


def test_no_signal_before_min_history():
    params = SpreadParams(min_history=100)
    model = FairValueModel(params)
    cl, uso = make_pair(99)
    states = [model.update(c, u) for c, u in zip(cl, uso)]
    assert all(s is None for s in states)


def test_beta_recovered():
    params = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)
    model = FairValueModel(params)
    cl, uso = make_pair(1000, beta=0.9)
    state = None
    for c, u in zip(cl, uso):
        state = model.update(c, u) or state
    assert state is not None
    assert abs(state.beta - 0.9) < 0.05


def test_lag_produces_negative_z():
    """CL jumps 2% while USO stands still -> USO is cheap -> z strongly negative."""
    params = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)
    model = FairValueModel(params)
    cl, uso = make_pair(600, beta=1.0)
    for c, u in zip(cl, uso):
        model.update(c, u)
    state = model.update(cl[-1] * 1.02, uso[-1])
    assert state is not None
    assert state.z < -3.0


def test_rich_uso_produces_positive_z():
    params = SpreadParams(min_history=200, beta_lookback=800, z_lookback=200)
    model = FairValueModel(params)
    cl, uso = make_pair(600, beta=1.0)
    for c, u in zip(cl, uso):
        model.update(c, u)
    state = model.update(cl[-1], uso[-1] * 1.02)
    assert state is not None
    assert state.z > 3.0


def test_rejects_bad_prices():
    model = FairValueModel(SpreadParams())
    try:
        model.update(0.0, 75.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive price")

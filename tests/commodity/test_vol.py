"""Math tests for vol module — verify the full-covariance targeting actually
hits the target vol on synthetic data, and edge cases behave."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.commodity.vol import (
    realized_vol, rolling_cov, vol_target_weights,
)


def _synthetic_returns(n_days: int = 500, n_assets: int = 4,
                       sigmas=(0.20, 0.30, 0.40, 0.15),
                       corr: float = 0.0, seed: int = 7) -> pd.DataFrame:
    """Generate daily returns with known annual vols and a constant pairwise
    correlation. sigma values are ANNUAL vols (sqrt(252) scaling)."""
    rng = np.random.default_rng(seed)
    k = len(sigmas)
    daily = np.array(sigmas) / np.sqrt(252)
    cov = np.outer(daily, daily) * (corr * np.ones((k, k)) + (1 - corr) * np.eye(k))
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal((n_days, k))
    r = z @ L.T
    cols = [f"A{i}" for i in range(k)]
    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.DataFrame(r, index=idx, columns=cols)


def test_realized_vol_recovers_input_sigma():
    sigmas = (0.20, 0.40)
    rets = _synthetic_returns(n_days=1000, sigmas=sigmas, corr=0.0)
    rv = realized_vol(rets, lookback=252)
    final = rv.iloc[-1]
    # Within 15% of true (small-sample noise)
    assert abs(final["A0"] - sigmas[0]) / sigmas[0] < 0.15, final.to_dict()
    assert abs(final["A1"] - sigmas[1]) / sigmas[1] < 0.15, final.to_dict()


def test_vol_target_zero_correlation_hits_target():
    """With independent assets and equal weights, scaled sigma should hit target."""
    sigmas = (0.20, 0.30, 0.40, 0.15)
    rets = _synthetic_returns(n_days=500, sigmas=sigmas, corr=0.0)
    covs = rolling_cov(rets, lookback=60)
    last_date = max(covs.keys())
    cov = covs[last_date]
    on = pd.Series(True, index=cov.columns)
    w = vol_target_weights(cov, on, target_vol=0.15, max_weight=0.99)
    realized = float(np.sqrt(w.values @ cov.values @ w.values))
    assert abs(realized - 0.15) < 0.002, f"realized {realized:.4f} vs target 0.15"


def test_vol_target_correlated_assets_still_hits_target():
    """With correlated assets, independent-vol formula would overshoot — full
    covariance must compensate. This is the whole point of Q1."""
    rets = _synthetic_returns(n_days=500, sigmas=(0.30, 0.30, 0.30, 0.30),
                              corr=0.8, seed=11)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series(True, index=cov.columns)
    w = vol_target_weights(cov, on, target_vol=0.15, max_weight=0.99)
    realized = float(np.sqrt(w.values @ cov.values @ w.values))
    assert abs(realized - 0.15) < 0.003, f"realized {realized:.4f} vs target 0.15"


def test_vol_target_cap_applied():
    """Per-instrument 25% cap actually caps."""
    rets = _synthetic_returns(n_days=500, sigmas=(0.10, 0.10, 0.10, 0.10), corr=0.0)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series(True, index=cov.columns)
    # Target very high vol so equal-weights blow past the cap
    w = vol_target_weights(cov, on, target_vol=1.0, max_weight=0.25)
    assert (w <= 0.25 + 1e-9).all(), w.to_dict()
    assert (w > 0).sum() == 4, "all four assets ON"


def test_no_on_returns_zero_weights():
    rets = _synthetic_returns(n_days=200)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series(False, index=cov.columns)
    w = vol_target_weights(cov, on, target_vol=0.15)
    assert (w == 0).all()


def test_inverse_vol_vs_equal_weight_distinguishes():
    """Inverse-vol gives more weight to low-vol assets; equal-weight doesn't.
    Both schemes target the same portfolio vol when no cap binds."""
    # Moderate heterogeneity + low target so cap doesn't bind for either scheme.
    rets = _synthetic_returns(n_days=500, sigmas=(0.15, 0.35), corr=0.0)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series(True, index=cov.columns)
    # max_weight high enough not to bind for the modest scaling needed
    w_inv = vol_target_weights(cov, on, target_vol=0.10, max_weight=0.99,
                               scheme="inverse_vol")
    w_eq = vol_target_weights(cov, on, target_vol=0.10, max_weight=0.99,
                              scheme="equal_weight")
    # Inverse-vol: low-vol asset (A0) gets MORE weight than high-vol (A1)
    assert w_inv["A0"] > w_inv["A1"], (
        f"inverse_vol should favor low-vol asset: {w_inv.to_dict()}")
    # Equal-weight: both get the same weight
    assert abs(w_eq["A0"] - w_eq["A1"]) < 1e-9, (
        f"equal_weight should give equal weights: {w_eq.to_dict()}")
    # No cap should bind in either scheme at these parameters
    assert (w_inv < 0.99).all() and (w_eq < 0.99).all()
    # Both schemes hit target vol when no cap binds
    for label, w in (("inv", w_inv), ("eq", w_eq)):
        realized = float(np.sqrt(w.values @ cov.values @ w.values))
        assert abs(realized - 0.10) < 0.003, f"{label} realized {realized:.4f}"


def test_cap_reduces_risk_below_target():
    """When the cap binds, realized vol should drop BELOW target (cap reduces
    risk; we do NOT redistribute capped weight to uncapped names)."""
    rets = _synthetic_returns(n_days=500, sigmas=(0.05, 0.05, 0.05, 0.05), corr=0.0)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series(True, index=cov.columns)
    # Target vol way above what 4 capped 25% positions can achieve
    w = vol_target_weights(cov, on, target_vol=1.0, max_weight=0.25,
                           scheme="inverse_vol")
    realized = float(np.sqrt(w.values @ cov.values @ w.values))
    assert realized < 1.0, "cap should hold realized vol below target"
    assert (w <= 0.25 + 1e-9).all()


def test_single_on_position_scales_correctly():
    """One ON asset with vol 0.30: weight should be 0.50 to target 0.15."""
    rets = _synthetic_returns(n_days=500, sigmas=(0.30, 0.30), corr=0.0)
    covs = rolling_cov(rets, lookback=60)
    cov = covs[max(covs.keys())]
    on = pd.Series([True, False], index=cov.columns)
    w = vol_target_weights(cov, on, target_vol=0.15, max_weight=0.99)
    # Realized sample vol of A0 may differ slightly from 0.30; check
    # via the actual cov, not the input sigma.
    realized_a0 = float(np.sqrt(cov.iloc[0, 0]))
    expected_w = 0.15 / realized_a0
    assert abs(w.iloc[0] - expected_w) < 1e-6, f"got {w.iloc[0]:.4f} expected {expected_w:.4f}"
    assert w.iloc[1] == 0.0

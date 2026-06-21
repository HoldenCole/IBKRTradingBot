"""Realized volatility + rolling covariance + full-covariance vol-targeting.

Per locked methodology Q1: full-covariance, NOT independent-vol. The independent
formula assumes commodities are uncorrelated, which is wrong in exactly the
regimes that matter (energy complex selling off together; crisis "everything
correlates to 1"). In those regimes realized portfolio vol substantially
exceeds the target under independent-vol sizing — defeating the point of
vol-targeting. We pay 1-2 extra days of dev work to do it right.

Module contents:
  realized_vol(returns, lookback)
      Per-instrument rolling annualized realized vol.
  rolling_cov(returns, lookback)
      Rolling sample covariance MATRIX of daily returns, annualized.
  vol_target_weights(cov, on_mask, target_vol, max_weight)
      Given a covariance matrix and an ON/OFF mask, returns position weights
      such that portfolio vol = target_vol, subject to per-instrument cap.

Conventions:
  - Annualization factor: sqrt(252) for vol, 252 for variance.
  - Returns are SIMPLE (price.pct_change()). Trend signals key on simple
    returns, so the vol estimate must too.
  - Lookback is 60 trading days (the spec). Initial NaN window passes
    through; vol_target_weights returns zero weights until the window fills.
  - Sample (Bessel-corrected) covariance via pandas default ddof=1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_DAYS_PER_YEAR = 252


def realized_vol(returns: pd.DataFrame, lookback: int = 60,
                 min_obs_frac: float = 0.8) -> pd.DataFrame:
    """Per-instrument rolling realized vol, annualized.

    Computed PER INSTRUMENT on its own non-NaN return series, so calendar
    mismatches (grains don't trade some sessions energy does) don't blank
    out cross-instrument vol. A column is NaN at date t only if it has
    fewer than `min_obs_frac * lookback` valid observations in the trailing
    window through t.
    """
    min_obs = max(2, int(lookback * min_obs_frac))
    return (returns
            .rolling(lookback, min_periods=min_obs)
            .std() * np.sqrt(_DAYS_PER_YEAR))


def rolling_cov(returns: pd.DataFrame, lookback: int = 60,
                min_obs_frac: float = 0.8) -> dict[pd.Timestamp, pd.DataFrame]:
    """Rolling annualized covariance matrix, pairwise NaN-tolerant.

    For each date t we compute the sample covariance over the trailing
    `lookback` calendar bars, using pandas' pairwise-complete handling.
    A column is included in that date's cov matrix if it has at least
    `min_obs_frac * lookback` valid observations in the window (default
    80% — accommodates grain/energy calendar mismatches without dropping
    grains entirely).

    Returns a dict keyed by date, each value a (k x k) cov DataFrame.
    """
    out: dict[pd.Timestamp, pd.DataFrame] = {}
    R = returns.dropna(how="all")
    if len(R) < lookback:
        return out
    min_obs = max(2, int(lookback * min_obs_frac))
    for i in range(lookback - 1, len(R)):
        date = R.index[i]
        window = R.iloc[i - lookback + 1 : i + 1]
        valid_cols = [c for c in window.columns if window[c].count() >= min_obs]
        if not valid_cols:
            continue
        cov = window[valid_cols].cov() * _DAYS_PER_YEAR
        # Guard against PSD violation from pairwise-NaN handling on the
        # off-diagonal: NaN entries drop to 0 (asset pair just doesn't
        # contribute), keeping the matrix usable.
        cov = cov.fillna(0.0)
        out[date] = cov
    return out


def vol_target_weights(
    cov: pd.DataFrame,
    on_mask: pd.Series,
    target_vol: float = 0.15,
    max_weight: float = 0.25,
    scheme: str = "inverse_vol",
) -> pd.Series:
    """Vol-targeted position weights with per-instrument cap.

    Two weighting schemes (the inner-scheme; full covariance is then used to
    scale the overall book to target_vol either way):

      scheme="inverse_vol" (DEFAULT, matches spec wording)
        Per-instrument weight ∝ 1/σ_i for ON instruments. Each position
        contributes EQUAL VOLATILITY before correlation adjustment. This is
        the standard CTA "risk parity" base; matches the spec's
        "contribution to portfolio vol is target_vol / (N_on × σ_i)" wording.

      scheme="equal_weight"
        All ON positions get equal CAPITAL allocation. High-vol instruments
        dominate portfolio risk. Simpler baseline; useful for ablation.

    Both schemes then SCALE the entire weight vector by target_vol /
    sqrt(w' Σ w) so the portfolio's realized vol (under the current
    covariance) equals target_vol. The full Σ is used here, so realized
    portfolio vol hits target even when assets are correlated (the whole
    point of Q1).

    Per-instrument 25% cap is applied AFTER scaling. Capped weight is not
    redistributed (caps reduce risk; redistribution would concentrate into
    uncapped names and defeat the cap's purpose).

    Returns: pd.Series indexed by `on_mask.index`. Zero for non-ON or when
    cov is degenerate.
    """
    if cov is None or cov.empty:
        return pd.Series(0.0, index=on_mask.index)
    if scheme not in {"inverse_vol", "equal_weight"}:
        raise ValueError(f"unknown scheme: {scheme!r}")

    syms = list(cov.columns)
    on_aligned = on_mask.reindex(syms).fillna(False).astype(bool)
    on_syms = [s for s in syms if on_aligned[s]]
    if not on_syms:
        return pd.Series(0.0, index=on_mask.index)
    on_idx = np.array([syms.index(s) for s in on_syms])

    cov_arr = cov.values

    w = np.zeros(len(syms))
    if scheme == "inverse_vol":
        sig = np.sqrt(np.maximum(np.diag(cov_arr)[on_idx], 0.0))
        # Guard against zero-vol instruments (would explode 1/σ).
        with np.errstate(divide="ignore"):
            inv = np.where(sig > 0, 1.0 / sig, 0.0)
        if inv.sum() <= 0 or not np.isfinite(inv.sum()):
            return pd.Series(0.0, index=on_mask.index)
        w[on_idx] = inv / inv.sum()    # initial normalized inverse-vol weights
    else:   # equal_weight
        w[on_idx] = 1.0 / len(on_syms)

    try:
        sigma_un = float(np.sqrt(max(0.0, w @ cov_arr @ w)))
    except Exception:
        return pd.Series(0.0, index=on_mask.index)
    if sigma_un <= 0 or not np.isfinite(sigma_un):
        return pd.Series(0.0, index=on_mask.index)

    scale = target_vol / sigma_un
    w = w * scale
    w = np.minimum(w, max_weight)
    w = np.maximum(w, 0.0)

    out = pd.Series(0.0, index=on_mask.index)
    for s, idx in zip(syms, range(len(syms))):
        if s in out.index:
            out[s] = w[idx]
    return out


def vol_target_weights_signed(
    cov: pd.DataFrame,
    direction: pd.Series,
    target_vol: float = 0.15,
    max_weight: float = 0.25,
) -> pd.Series:
    """Long-SHORT vol-targeted weights from a direction vector (-1/0/+1).

    Magnitude is inverse-vol per active instrument (equal risk before
    correlation), signed by `direction`. The signed weight vector is then
    scaled by target_vol / sqrt(w' Cov w) so the portfolio's realized vol
    (full covariance, accounting for long-short offsets) equals target_vol.
    Per-instrument |weight| cap applied after scaling.

    Used by the long-short engine path (Test 1). A short position contributes
    -|w_i| * r_i to the book return, exactly mirroring a long.
    """
    if cov is None or cov.empty:
        return pd.Series(0.0, index=direction.index)

    syms = list(cov.columns)
    d = direction.reindex(syms).fillna(0.0)
    active = [s for s in syms if d[s] != 0]
    if not active:
        return pd.Series(0.0, index=direction.index)
    act_idx = np.array([syms.index(s) for s in active])

    cov_arr = cov.values
    sig = np.sqrt(np.maximum(np.diag(cov_arr)[act_idx], 0.0))
    with np.errstate(divide="ignore"):
        inv = np.where(sig > 0, 1.0 / sig, 0.0)
    if inv.sum() <= 0 or not np.isfinite(inv.sum()):
        return pd.Series(0.0, index=direction.index)

    w = np.zeros(len(syms))
    w[act_idx] = inv / inv.sum()          # normalized inverse-vol magnitude
    w[act_idx] *= d.values[act_idx]       # apply +1/-1 sign

    try:
        sigma_un = float(np.sqrt(max(0.0, w @ cov_arr @ w)))
    except Exception:
        return pd.Series(0.0, index=direction.index)
    if sigma_un <= 0 or not np.isfinite(sigma_un):
        return pd.Series(0.0, index=direction.index)

    w = w * (target_vol / sigma_un)
    w = np.clip(w, -max_weight, max_weight)   # cap |w|, preserve sign

    out = pd.Series(0.0, index=direction.index)
    for idx, s in enumerate(syms):
        if s in out.index:
            out[s] = w[idx]
    return out


@dataclass
class VolTargetingReport:
    """Diagnostic snapshot of a vol-targeting run."""
    weights_history: pd.DataFrame      # date x symbol
    realized_port_vol: pd.Series       # date -> realized 60d portfolio vol
    n_on_history: pd.Series            # date -> count of ON instruments
    n_capped_history: pd.Series        # date -> count of capped positions

    def headline(self) -> dict:
        return {
            "median_realized_port_vol": float(self.realized_port_vol.median()),
            "p95_realized_port_vol": float(self.realized_port_vol.quantile(0.95)),
            "median_n_on": float(self.n_on_history.median()),
            "median_n_capped": float(self.n_capped_history.median()),
            "n_days": int(len(self.weights_history)),
        }

"""Statistics for the harness: summaries, daily P&L, SPA / StepM, random-entry null, power."""
from __future__ import annotations

import numpy as np
import pandas as pd
from arch.bootstrap import SPA, StepM
from scipy import stats as sps

WINDOWS = {"2012-2017": ("2012-01-01", "2017-12-31"), "2018-2024": ("2018-01-01", "2024-11-30")}


def summarize(t: pd.DataFrame) -> dict:
    if t is None or t.empty:
        return {"n": 0}
    x = t["net_bp"].to_numpy()
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    out = {"n": len(x), "mean_net_bp": x.mean(), "t": x.mean() / sd * np.sqrt(len(x)) if sd > 0 else np.nan,
           "mean_gross_bp": t["gross_bp"].mean(), "mean_cost_bp": t["cost_bp"].mean(),
           "cost_ratio": t["gross_bp"].mean() / t["cost_bp"].mean(),
           "win": (x > 0).mean(), "mean_R": t["R"].mean(), "sum_net_bp": x.sum(),
           "stop_share": (t["kind"] == 0).mean(), "target_share": (t["kind"] == 1).mean()}
    et = t["entry_time"].dt.tz_convert(None)
    for w, (a, b) in WINDOWS.items():
        m = (et >= a) & (et <= pd.Timestamp(b) + pd.Timedelta(days=1))
        out[f"mean_net_{w}"] = t.loc[m, "net_bp"].mean() if m.any() else np.nan
        out[f"n_{w}"] = int(m.sum())
    return out


def by_year(t: pd.DataFrame) -> pd.DataFrame:
    y = t["entry_time"].dt.year
    return t.groupby(y).agg(n=("net_bp", "size"), mean_net_bp=("net_bp", "mean"), mean_gross_bp=("gross_bp", "mean"),
                            sum_net_bp=("net_bp", "sum"))


def daily(t: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.Series:
    d = t["exit_time"].dt.tz_convert(None).dt.normalize()
    return t.groupby(d)["net_bp"].sum().reindex(calendar, fill_value=0.0)


def spa_tests(daily_pnl: pd.DataFrame, reps: int = 2000, seed: int = 7) -> dict:
    """Hansen SPA and Romano-Wolf StepM against a zero benchmark. Losses = -P&L."""
    losses = -daily_pnl.to_numpy()
    bench = np.zeros(len(daily_pnl))
    spa = SPA(bench, losses, reps=reps, block_size=10, bootstrap="stationary", seed=seed)
    spa.compute()
    sm = StepM(bench, losses, size=0.05, reps=reps, block_size=10, bootstrap="stationary", seed=seed)
    sm.compute()
    sup = list(sm.superior_models) if sm.superior_models is not None else []
    names = [daily_pnl.columns[i] if isinstance(i, (int, np.integer)) else i for i in sup]
    return {"spa_p_consistent": float(spa.pvalues["consistent"]), "spa_p_lower": float(spa.pvalues["lower"]),
            "spa_p_upper": float(spa.pvalues["upper"]), "stepm_superior": names}


def null_p(actual_mean: float, sims: np.ndarray) -> float:
    return float((1 + np.sum(sims >= actual_mean)) / (1 + len(sims)))


def trades_needed(win: float, payoff: float, t_req: float, alpha_one_sided: float = 0.05, power: float = 0.8) -> int:
    """Trades needed to detect the edge of a win-rate / payoff-ratio rule (R units, loss = 1R)."""
    mu = win * payoff - (1 - win)
    var = win * payoff ** 2 + (1 - win) - mu ** 2
    if mu <= 0:
        return -1
    z_a = t_req if t_req else sps.norm.ppf(1 - alpha_one_sided)
    z_b = sps.norm.ppf(power)
    return int(np.ceil(((z_a + z_b) ** 2) * var / mu ** 2))

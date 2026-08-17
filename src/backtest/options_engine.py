"""Options-execution backtest for the CL1/USO spread strategy.

Same signal engine as the share backtest, but positions are expressed as
long ATM USO options: signal long -> buy ATM call, signal short -> buy
ATM put. Long-premium-only keeps risk strictly bounded (max loss = premium
paid), which is why a defined-risk options expression is attractive here.

Modeling (no historical option chains available, so priced analytically):
- Black-Scholes with trailing realized vol of USO (annualized), flat rate
- 7 calendar DTE at entry; positions never held past the session (the
  strategy flattens at 15:55 ET), so theta decay within a hold is small
- Quoted spread: max($0.02, 3% of premium) — typical for near-ATM USO
  weeklies; entries fill at mid + 25% of spread (limit chase), normal
  exits at mid - 25% of spread, stop exits at bid (limit priced through)
- Commission: $0.65/contract, $1 minimum per order
- Exits: all strategy exits (convergence, z-stop, time stop, EOD flatten)
  PLUS a -50% premium stop checked every bar

This is an approximation good enough for go/no-go sizing decisions; a
real validation still needs live option quotes in paper trading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.backtest.engine import align_pair
from src.strategies.base import Action
from src.strategies.cl1_uso_spread import Cl1UsoSpreadStrategy, PairBar, SpreadParams

TRADING_MINUTES_PER_YEAR = 252 * 390


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(spot: float, strike: float, t_years: float, vol: float, rate: float, is_call: bool) -> float:
    """Black-Scholes European option price."""
    if t_years <= 0:
        intrinsic = (spot - strike) if is_call else (strike - spot)
        return max(0.0, intrinsic)
    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    if is_call:
        return spot * _norm_cdf(d1) - strike * math.exp(-rate * t_years) * _norm_cdf(d2)
    return strike * math.exp(-rate * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


@dataclass
class OptionsBacktestConfig:
    position_usd: float = 1000.0       # premium budget per trade
    dte_days: float = 7.0
    rate: float = 0.04
    vol_lookback_bars: int = 390 * 20  # ~20 RTH days of 1-min returns
    premium_stop_pct: float = 0.50     # exit when option loses 50% of entry premium
    min_spread: float = 0.02
    spread_pct_of_premium: float = 0.03
    entry_fill_frac: float = 0.25      # entries: mid + 25% of spread
    exit_fill_frac: float = 0.25       # normal exits: mid - 25% of spread
    commission_per_contract: float = 0.65
    min_commission: float = 1.0
    params: SpreadParams = field(default_factory=SpreadParams)


@dataclass
class OptionsBacktestResult:
    trades: pd.DataFrame
    metrics: dict

    def summary(self) -> str:
        lines = ["=== CL1/USO Spread Backtest (OPTIONS execution) ==="]
        for key, value in self.metrics.items():
            lines.append(f"{key:>22}: {value}")
        return "\n".join(lines)


class _RealizedVol:
    """Trailing annualized realized vol from 1-min closes."""

    def __init__(self, lookback: int):
        self.lookback = lookback
        self._log_prices: list[float] = []

    def update(self, price: float) -> float | None:
        self._log_prices.append(math.log(price))
        if len(self._log_prices) > self.lookback + 1:
            self._log_prices = self._log_prices[-(self.lookback + 1):]
        if len(self._log_prices) < 60:
            return None
        rets = np.diff(self._log_prices)
        return float(np.std(rets) * math.sqrt(TRADING_MINUTES_PER_YEAR))


def _spread_of(premium: float, config: OptionsBacktestConfig) -> float:
    return max(config.min_spread, premium * config.spread_pct_of_premium)


def run_options_backtest(
    cl: pd.DataFrame, uso: pd.DataFrame, config: OptionsBacktestConfig | None = None
) -> OptionsBacktestResult:
    config = config or OptionsBacktestConfig()
    df = align_pair(cl, uso)
    strategy = Cl1UsoSpreadStrategy(params=config.params)
    vol_model = _RealizedVol(config.vol_lookback_bars)
    timestamps = df.index.to_pydatetime()
    n = len(df)

    trades: list[dict] = []
    open_trade: dict | None = None

    def commission(contracts: int) -> float:
        return max(config.min_commission, contracts * config.commission_per_contract)

    def option_mid(trade: dict, spot: float, ts) -> float:
        elapsed_years = (ts - trade["entry_ts"]).total_seconds() / (365.0 * 86400)
        t = max(1e-6, config.dte_days / 365.0 - elapsed_years)
        return bs_price(spot, trade["strike"], t, trade["vol"], config.rate, trade["is_call"])

    def close_position(ts, spot: float, reason: str, is_stop: bool) -> None:
        nonlocal open_trade
        assert open_trade is not None
        mid = option_mid(open_trade, spot, ts)
        spread = _spread_of(mid, config)
        if is_stop:
            fill = max(0.01, mid - 0.5 * spread)  # priced through to the bid
        else:
            fill = max(0.01, mid - config.exit_fill_frac * spread)
        contracts = open_trade["contracts"]
        pnl = (fill - open_trade["entry_premium"]) * 100 * contracts - commission(contracts)
        trades.append(
            {
                "entry_ts": open_trade["entry_ts"],
                "exit_ts": ts,
                "type": "call" if open_trade["is_call"] else "put",
                "contracts": contracts,
                "entry_premium": open_trade["entry_premium"],
                "exit_premium": fill,
                "entry_reason": open_trade["entry_reason"],
                "exit_reason": reason,
                "pnl": pnl,
            }
        )
        open_trade = None

    for i in range(n):
        ts = timestamps[i]
        spot = float(df["uso_close"].iloc[i])
        vol = vol_model.update(spot)
        bar = PairBar(ts=ts, cl_close=float(df["cl_close"].iloc[i]), uso_close=spot)

        # Premium stop is checked BEFORE the strategy's own logic each bar.
        if open_trade is not None:
            mid = option_mid(open_trade, spot, ts)
            if mid <= open_trade["entry_premium"] * (1 - config.premium_stop_pct):
                close_position(ts, spot, "premium_stop", is_stop=True)
                strategy.position = None  # keep signal engine in sync

        signal = strategy.on_bar(bar)
        if signal is None:
            continue

        if signal.action is Action.CLOSE:
            if open_trade is not None:
                is_stop = "stop" in signal.reason or "eod" in signal.reason
                close_position(ts, spot, signal.reason, is_stop=is_stop)
            continue

        # Entry. Need a vol estimate to price the option.
        if vol is None or vol <= 0:
            strategy.position = None
            continue
        is_call = signal.action is Action.BUY
        strike = round(spot)  # nearest whole-dollar strike ~ ATM
        premium_mid = bs_price(spot, strike, config.dte_days / 365.0, vol, config.rate, is_call)
        if premium_mid < 0.05:
            strategy.position = None
            continue
        spread = _spread_of(premium_mid, config)
        entry_fill = premium_mid + config.entry_fill_frac * spread
        contracts = int(config.position_usd // (entry_fill * 100))
        if contracts < 1:
            strategy.position = None
            continue
        open_trade = {
            "entry_ts": ts,
            "strike": strike,
            "is_call": is_call,
            "vol": vol,
            "contracts": contracts,
            "entry_premium": entry_fill,
            "entry_reason": signal.reason,
        }

    if open_trade is not None:  # safety net; EOD flatten should prevent this
        close_position(timestamps[-1], float(df["uso_close"].iloc[-1]), "backtest_end", is_stop=True)

    trades_df = pd.DataFrame(trades)
    return OptionsBacktestResult(trades=trades_df, metrics=_metrics(trades_df, config))


def _metrics(trades: pd.DataFrame, config: OptionsBacktestConfig) -> dict:
    if trades.empty:
        return {"n_trades": 0, "note": "no trades generated"}
    pnl = trades["pnl"]
    hold = (trades["exit_ts"] - trades["entry_ts"]).dt.total_seconds() / 60
    premium_deployed = trades["entry_premium"] * 100 * trades["contracts"]
    return {
        "n_trades": len(trades),
        "total_pnl": f"${pnl.sum():.2f}",
        "win_rate": f"{(pnl > 0).mean():.1%}",
        "avg_pnl_per_trade": f"${pnl.mean():.2f}",
        "median_hold_minutes": f"{hold.median():.0f}",
        "worst_trade": f"${pnl.min():.2f}",
        "best_trade": f"${pnl.max():.2f}",
        "premium_stops": int((trades["exit_reason"] == "premium_stop").sum()),
        "avg_premium_deployed": f"${premium_deployed.mean():.0f}",
        "calls/puts": f"{int((trades['type'] == 'call').sum())}/{int((trades['type'] == 'put').sum())}",
        "position_usd": f"${config.position_usd:.0f}",
    }

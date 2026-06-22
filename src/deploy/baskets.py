"""Five-basket portfolio architecture — config-driven weights + position sizing.

Loads config/baskets.json and exposes:
  - the basket structure (weights, enabled flags, strategy specs)
  - validation (enabled weights sum to 1.0)
  - per-strategy target dollar allocation given account equity
  - account-size-conditional vehicle resolution (e.g. QQQ_SHARES -> MNQ at $60k)

Changing the deployed allocation is a config edit; this module never
hardcodes weights. Stage transitions, basket activation, and rebalancing
are all driven from config/baskets.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _REPO / "config" / "baskets.json"

# Tolerance for the "enabled weights sum to 1.0" check.
_WEIGHT_EPS = 1e-6


@dataclass(frozen=True)
class StrategySpec:
    id: str
    asset: str
    signal: str
    params: dict
    off_vehicle: str
    vehicle_by_account_usd: dict        # {"0": "IBIT", "25000": "MBT"} (str keys)
    convention: str = "close_t_minus_1_to_t"
    validated: str = ""

    def vehicle_for_account(self, equity_usd: float) -> str:
        """Resolve the deployment vehicle for the given account size by
        selecting the highest threshold <= equity."""
        tiers = sorted(((int(k), v) for k, v in self.vehicle_by_account_usd.items()),
                       key=lambda kv: kv[0])
        chosen = tiers[0][1] if tiers else ""
        for threshold, vehicle in tiers:
            if equity_usd >= threshold:
                chosen = vehicle
        return chosen


@dataclass(frozen=True)
class Basket:
    id: str
    name: str
    role: str
    weight: float
    enabled: bool
    strategies: tuple[StrategySpec, ...] = ()
    filed_candidates: tuple[str, ...] = ()
    activation_criteria: str = ""


@dataclass(frozen=True)
class Allocation:
    """A resolved target allocation for one strategy."""
    basket_id: str
    strategy_id: str
    asset: str
    vehicle: str
    off_vehicle: str
    target_weight: float        # fraction of total account (basket_weight, single strat per basket in Stage 1)
    target_dollars: float


@dataclass
class BasketConfig:
    schema_version: int
    stage: int
    rebalance: dict
    baskets: dict[str, Basket]

    # ----- loading -----
    @classmethod
    def load(cls, path: Path | None = None) -> "BasketConfig":
        p = path or _DEFAULT_CONFIG
        raw = json.loads(p.read_text())
        baskets: dict[str, Basket] = {}
        for bid, b in raw["baskets"].items():
            strategies = tuple(
                StrategySpec(
                    id=s["id"], asset=s["asset"], signal=s["signal"],
                    params=s.get("params", {}), off_vehicle=s.get("off_vehicle", "tbill"),
                    vehicle_by_account_usd=s.get("vehicle_by_account_usd", {}),
                    convention=s.get("convention", "close_t_minus_1_to_t"),
                    validated=s.get("validated", ""),
                )
                for s in b.get("strategies", [])
            )
            baskets[bid] = Basket(
                id=bid, name=b["name"], role=b.get("role", ""),
                weight=float(b["weight"]), enabled=bool(b["enabled"]),
                strategies=strategies,
                filed_candidates=tuple(b.get("filed_candidates", [])),
                activation_criteria=b.get("activation_criteria", ""),
            )
        cfg = cls(schema_version=int(raw["schema_version"]), stage=int(raw["stage"]),
                  rebalance=raw.get("rebalance", {}), baskets=baskets)
        cfg.validate()
        return cfg

    # ----- validation -----
    def validate(self) -> None:
        total = sum(b.weight for b in self.baskets.values() if b.enabled)
        if abs(total - 1.0) > _WEIGHT_EPS:
            raise ValueError(
                f"Enabled basket weights must sum to 1.0; got {total:.6f}. "
                f"Enabled: {[(b.id, b.weight) for b in self.baskets.values() if b.enabled]}")
        for b in self.baskets.values():
            if b.enabled and not b.strategies:
                raise ValueError(f"Basket {b.id} ({b.name}) is enabled but has no strategies")
            if b.weight < 0:
                raise ValueError(f"Basket {b.id} has negative weight {b.weight}")
            if not b.enabled and b.weight != 0.0:
                raise ValueError(f"Basket {b.id} is disabled but has nonzero weight {b.weight}")

    # ----- sizing -----
    def allocations(self, account_equity_usd: float) -> list[Allocation]:
        """Resolve target allocations for every enabled strategy.

        Stage 1 has one strategy per enabled basket, so the strategy's
        target weight equals its basket weight. The design supports multiple
        strategies per basket (they'd split the basket weight equally unless
        per-strategy weights are added to the schema later).
        """
        out: list[Allocation] = []
        for b in self.baskets.values():
            if not b.enabled or not b.strategies:
                continue
            per_strat_weight = b.weight / len(b.strategies)
            for s in b.strategies:
                out.append(Allocation(
                    basket_id=b.id, strategy_id=s.id, asset=s.asset,
                    vehicle=s.vehicle_for_account(account_equity_usd),
                    off_vehicle=s.off_vehicle,
                    target_weight=per_strat_weight,
                    target_dollars=per_strat_weight * account_equity_usd,
                ))
        return out

    def enabled_weight_total(self) -> float:
        return sum(b.weight for b in self.baskets.values() if b.enabled)

    def summary(self) -> str:
        lines = [f"Basket config (schema v{self.schema_version}, Stage {self.stage}, "
                 f"rebalance={self.rebalance.get('policy', '?')}):"]
        for bid in sorted(self.baskets):
            b = self.baskets[bid]
            status = "ON " if b.enabled else "off"
            strat = ", ".join(s.id for s in b.strategies) or "—"
            lines.append(f"  [{status}] B{bid} {b.name:<40} w={b.weight:>4.0%}  {strat}")
        return "\n".join(lines)

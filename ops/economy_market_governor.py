#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
STATUS_DIR = RUNTIME / "status"
SUMMARY_PATH = AUTONOMY / "economy_market_summary.yml"
OUTPUT_DIR = RUNTIME / "economy_operations"
ECONOMY_SUMMARY_PATH = AUTONOMY / "economy_governor_summary.yml"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> int:
    created_at = now_iso()
    economy = load_yaml(ECONOMY_SUMMARY_PATH)
    totals = {
        "status_files": 0.0,
        "economy_earn": 0.0,
        "economy_spend": 0.0,
        "gear_upgrade": 0.0,
        "reward_distributed": 0.0,
        "gear_drop": 0.0,
        "return_player_reward": 0.0,
    }
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1
        for key in totals:
            if key == "status_files":
                continue
            totals[key] += float(payload.get(key, 0) or 0)

    divisor = max(1.0, totals["status_files"])
    earn_avg = round(totals["economy_earn"] / divisor, 2)
    spend_avg = round(totals["economy_spend"] / divisor, 2)
    reward_avg = round(totals["reward_distributed"] / divisor, 2)
    sink_pressure = round(clamp((totals["gear_upgrade"] / divisor) / 260.0 + spend_avg / max(1.0, earn_avg + spend_avg), 0.0, 1.0), 2)
    faucet_balance_score = round(clamp(1.0 - abs(float(economy.get("inflation_ratio", 1.0)) - 1.0) / 0.4, 0.0, 1.0), 2)
    reward_sustainability_score = round(clamp(1.0 - max(0.0, reward_avg - 4500.0) / 6000.0 + min(0.3, sink_pressure * 0.3), 0.0, 1.0), 2)
    supply_discipline_score = round(clamp(1.0 - max(0.0, (totals["gear_drop"] - totals["gear_upgrade"]) / max(1.0, totals["gear_drop"] + totals["gear_upgrade"])), 0.0, 1.0), 2)
    returner_cost_fairness = round(clamp(1.0 - max(0.0, totals["return_player_reward"] / max(1.0, totals["economy_earn"]) - 0.18) / 0.25, 0.0, 1.0), 2)
    market_maturity_score = round(
        clamp(
            faucet_balance_score * 0.34
            + sink_pressure * 0.18
            + reward_sustainability_score * 0.18
            + supply_discipline_score * 0.16
            + returner_cost_fairness * 0.14,
            0.0,
            1.0,
        ),
        2,
    )
    if market_maturity_score >= 0.85:
        market_state = "mature"
    elif market_maturity_score >= 0.65:
        market_state = "stable"
    else:
        market_state = "fragile"

    payload = {
        "created_at": created_at,
        "earn_avg": earn_avg,
        "spend_avg": spend_avg,
        "reward_avg": reward_avg,
        "inflation_ratio": float(economy.get("inflation_ratio", 0.0)),
        "sink_pressure": sink_pressure,
        "faucet_balance_score": faucet_balance_score,
        "reward_sustainability_score": reward_sustainability_score,
        "supply_discipline_score": supply_discipline_score,
        "returner_cost_fairness": returner_cost_fairness,
        "market_maturity_score": market_maturity_score,
        "market_state": market_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_economy_market.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("ECONOMY_MARKET_GOVERNOR")
    print(f"MARKET_MATURITY_SCORE={market_maturity_score}")
    print(f"MARKET_STATE={market_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

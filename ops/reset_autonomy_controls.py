#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from io import StringIO

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"

DEFAULTS = {
    "adaptive_rules.yml": {
        "matchmaking.high_queue_seconds": 45,
        "events.low_join_rate": 0.30,
        "rewards.low_completion_rate": 0.45,
    },
    "runtime_monitor.yml": {
        "scaling.density_scale_trigger": 65,
        "exploit_detection.duplicate_reward_spike": 3,
        "exploit_detection.abnormal_currency_gain": 2500,
    },
    "pressure.yml": {
        "controls.noncritical_spawn_suppression_threshold": 0.75,
        "controls.queue_admission_threshold": 0.85,
    },
    "economy.yml": {
        "market_tax": 0.08,
    },
}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def nested_set(payload: dict, dotted: str, value) -> None:
    current = payload
    parts = dotted.split(".")
    for key in parts[:-1]:
        current = current.setdefault(key, {})
    current[parts[-1]] = value


def write_yaml(path: Path, payload: dict) -> None:
    stream = StringIO()
    yaml.safe_dump(payload, stream, sort_keys=False, allow_unicode=True)
    path.write_text(stream.getvalue(), encoding="utf-8")


def main() -> int:
    for filename, mappings in DEFAULTS.items():
        path = CONFIG / filename
        payload = load_yaml(path)
        for dotted, value in mappings.items():
            nested_set(payload, dotted, value)
        write_yaml(path, payload)
    print("AUTONOMY_CONTROLS_RESET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

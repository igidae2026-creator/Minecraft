#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "runtime_data" / "autonomy" / "control" / "state.yml"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def control_snapshot() -> dict:
    control = load_yaml(CONTROL)
    return {
        "last_mode": control.get("last_mode", "unknown"),
        "last_regime": control.get("last_regime", "unknown"),
        "active_soak": (control.get("active_soak", {}) or {}).get("decision_id", ""),
        "steady_noop_streak": int(control.get("steady_noop_streak", 0)),
    }


if __name__ == "__main__":
    print(control_snapshot())

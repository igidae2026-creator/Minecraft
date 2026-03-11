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


def consumer_status() -> dict:
    control = load_yaml(CONTROL)
    return {
        "execution_threshold_ready": bool(control.get("execution_threshold_ready", False)),
        "operational_threshold_ready": bool(control.get("operational_threshold_ready", False)),
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
        "final_threshold_ready": bool(control.get("final_threshold_ready", False)),
        "steady_noop_streak": int(control.get("steady_noop_streak", 0)),
    }


if __name__ == "__main__":
    print(consumer_status())

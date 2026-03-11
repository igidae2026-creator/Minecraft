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


def soak_status() -> dict:
    control = load_yaml(CONTROL)
    return {
        "active_soak": (control.get("active_soak", {}) or {}).get("decision_id", ""),
        "last_soak_resolution": (control.get("last_soak_resolution", {}) or {}).get("resolution", ""),
    }


if __name__ == "__main__":
    print(soak_status())

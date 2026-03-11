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


def intervention_ledger() -> dict:
    control = load_yaml(CONTROL)
    soak = control.get("last_soak_resolution", {}) or {}
    return {
        "last_resolution": soak.get("resolution", ""),
        "last_resolution_at": soak.get("closed_at", ""),
        "last_resolution_decision": soak.get("decision_id", ""),
    }


if __name__ == "__main__":
    print(intervention_ledger())

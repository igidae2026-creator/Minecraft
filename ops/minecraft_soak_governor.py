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
SUMMARY_PATH = AUTONOMY / "minecraft_soak_summary.yml"
SOAK_DIR = RUNTIME / "minecraft_soak"


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


def main() -> int:
    created_at = now_iso()
    control = load_yaml(AUTONOMY / "control" / "state.yml")
    minecraft_bundle = load_yaml(AUTONOMY / "minecraft_bundle_summary.yml")
    minecraft_strategy = load_yaml(AUTONOMY / "minecraft_strategy_summary.yml")
    economy = load_yaml(AUTONOMY / "economy_governor_summary.yml")
    anti_cheat = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")

    steady_noop_streak = int(control.get("steady_noop_streak", 0))
    final_ready = bool(control.get("final_threshold_ready", False))
    bundle_completion = float(minecraft_bundle.get("bundle_completion_percent", 0.0))
    repairs = int(minecraft_strategy.get("recommended_repairs_count", 0))
    sandbox_cases = int(anti_cheat.get("sandbox_cases", 0))
    inflation_ratio = float(economy.get("inflation_ratio", 0.0))
    held_actions = int(liveops.get("held_actions", 0))

    if final_ready and steady_noop_streak >= 24 and repairs == 0 and held_actions == 0:
        soak_state = "stable"
    elif final_ready and bundle_completion >= 100.0 and steady_noop_streak >= 12:
        soak_state = "observe"
    else:
        soak_state = "tune"

    payload = {
        "created_at": created_at,
        "steady_noop_streak": steady_noop_streak,
        "final_threshold_ready": final_ready,
        "minecraft_bundle_completion_percent": bundle_completion,
        "minecraft_next_focus_csv": str(minecraft_strategy.get("next_focus_csv", "")),
        "recommended_repairs_count": repairs,
        "anti_cheat_sandbox_cases": sandbox_cases,
        "economy_inflation_ratio": inflation_ratio,
        "liveops_held_actions": held_actions,
        "minecraft_soak_state": soak_state,
    }
    SOAK_DIR.mkdir(parents=True, exist_ok=True)
    (SOAK_DIR / f"{created_at.replace(':', '').replace('-', '')}_minecraft_soak.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("MINECRAFT_SOAK_GOVERNOR")
    print(f"MINECRAFT_SOAK_STATE={soak_state}")
    print(f"RECOMMENDED_REPAIRS={repairs}")
    print(f"STEADY_NOOP_STREAK={steady_noop_streak}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

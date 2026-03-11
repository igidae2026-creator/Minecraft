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
SUMMARY_PATH = AUTONOMY / "player_experience_soak_summary.yml"
SOAK_DIR = RUNTIME / "player_experience_soak"


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
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    content_strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    minecraft_strategy = load_yaml(AUTONOMY / "minecraft_strategy_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")

    steady_noop_streak = int(control.get("steady_noop_streak", 0))
    final_ready = bool(control.get("final_threshold_ready", False))
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_state = str(player_experience.get("experience_state", ""))
    friction_penalty = float(player_experience.get("friction_penalty", 0.0))
    first_session_strength = float(player_experience.get("first_session_strength", 0.0))
    trust_pull = float(player_experience.get("trust_pull", 0.0))
    content_repairs = int(content_strategy.get("recommended_repairs_count", 0))
    minecraft_repairs = int(minecraft_strategy.get("recommended_repairs_count", 0))
    boost_reentry = bool(liveops.get("boost_reentry", False))
    combined_repairs = content_repairs + minecraft_repairs

    if final_ready and steady_noop_streak >= 24 and experience_percent >= 46.0 and first_session_strength >= 0.95 and trust_pull >= 0.7 and friction_penalty <= 0.2 and combined_repairs <= 4 and not boost_reentry:
        soak_state = "stable"
    elif final_ready and steady_noop_streak >= 12 and experience_percent >= 25.0:
        soak_state = "observe"
    else:
        soak_state = "tune"

    payload = {
        "created_at": created_at,
        "steady_noop_streak": steady_noop_streak,
        "final_threshold_ready": final_ready,
        "estimated_completeness_percent": round(experience_percent, 1),
        "experience_state": experience_state,
        "friction_penalty": friction_penalty,
        "first_session_strength": first_session_strength,
        "trust_pull": trust_pull,
        "content_recommended_repairs_count": content_repairs,
        "minecraft_recommended_repairs_count": minecraft_repairs,
        "combined_recommended_repairs_count": combined_repairs,
        "boost_reentry": boost_reentry,
        "player_experience_soak_state": soak_state,
    }
    SOAK_DIR.mkdir(parents=True, exist_ok=True)
    (SOAK_DIR / f"{created_at.replace(':', '').replace('-', '')}_player_experience_soak.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("PLAYER_EXPERIENCE_SOAK_GOVERNOR")
    print(f"PLAYER_EXPERIENCE_SOAK_STATE={soak_state}")
    print(f"ESTIMATED_COMPLETENESS_PERCENT={payload['estimated_completeness_percent']}")
    print(f"COMBINED_RECOMMENDED_REPAIRS={combined_repairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

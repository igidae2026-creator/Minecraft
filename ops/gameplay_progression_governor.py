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
SUMMARY_PATH = AUTONOMY / "gameplay_progression_summary.yml"
OUTPUT_DIR = RUNTIME / "gameplay_progression"


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
    content = load_yaml(AUTONOMY / "content_governor_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")

    quest_chain_count = int((content.get("by_type", {}) or {}).get("quest_chain", 0))
    dungeon_variation_count = int((content.get("by_type", {}) or {}).get("dungeon_variation", 0))
    season_count = int((content.get("by_type", {}) or {}).get("season", 0))
    onboarding_count = int((content.get("by_type", {}) or {}).get("onboarding", 0))
    avg_depth = float(content.get("average_depth_score", 0.0))
    replayable_loop_score = float(content.get("replayable_loop_score", 0.0))
    first_loop_coverage = float(content.get("first_loop_coverage_score", 0.0))
    mastery_arc_strength = float(content.get("mastery_arc_strength", 0.0))
    prestige_clarity_strength = float(content.get("prestige_clarity_strength", 0.0))
    trust_pull = float(player_experience.get("trust_pull", 0.0))

    totals = {
        "dungeons_completed": 0.0,
        "bosses_killed": 0.0,
        "progression_level_up": 0.0,
        "streak_progress": 0.0,
        "prestige_gain": 0.0,
        "status_files": 0.0,
    }
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1
        totals["dungeons_completed"] += float(payload.get("dungeon_completed", 0) or 0)
        totals["bosses_killed"] += float(payload.get("boss_killed", 0) or 0)
        totals["progression_level_up"] += float(payload.get("progression_level_up", 0) or 0)
        totals["streak_progress"] += float(payload.get("streak_progress", 0) or 0)
        totals["prestige_gain"] += float(payload.get("prestige_gain", 0) or 0)

    divisor = max(1.0, totals["status_files"])
    dungeon_completion_avg = round(totals["dungeons_completed"] / divisor, 2)
    boss_kill_avg = round(totals["bosses_killed"] / divisor, 2)
    level_up_avg = round(totals["progression_level_up"] / divisor, 2)
    streak_progress_avg = round(totals["streak_progress"] / divisor, 2)
    prestige_gain_avg = round(totals["prestige_gain"] / divisor, 2)

    progression_spine_score = round(
        clamp(
            (quest_chain_count / 3.0)
            + (dungeon_variation_count / 4.0)
            + (season_count / 3.0)
            + (onboarding_count / 3.0)
            + (avg_depth / 3.0)
            + (replayable_loop_score / 3.0)
            + (first_loop_coverage / 3.0),
            0.0,
            7.0,
        ),
        2,
    )
    progression_spine_score = round(clamp(progression_spine_score + mastery_arc_strength / 3.0 + prestige_clarity_strength / 3.0, 0.0, 9.0), 2)
    progression_runtime_score = round(
        clamp(
            (dungeon_completion_avg / 220.0)
            + (boss_kill_avg / 60.0)
            + (level_up_avg / 45.0)
            + (streak_progress_avg / 120.0)
            + (prestige_gain_avg / 35.0)
            + trust_pull,
            0.0,
            7.0,
        ),
        2,
    )
    progression_total_score = round(progression_spine_score + progression_runtime_score, 2)
    progression_state = "advanced" if progression_total_score >= 9.0 else "mid" if progression_total_score >= 6.0 else "early"

    payload = {
        "created_at": created_at,
        "quest_chain_count": quest_chain_count,
        "dungeon_variation_count": dungeon_variation_count,
        "season_count": season_count,
        "onboarding_count": onboarding_count,
        "average_depth_score": avg_depth,
        "replayable_loop_score": replayable_loop_score,
        "first_loop_coverage_score": first_loop_coverage,
        "mastery_arc_strength": mastery_arc_strength,
        "prestige_clarity_strength": prestige_clarity_strength,
        "dungeon_completion_avg": dungeon_completion_avg,
        "boss_kill_avg": boss_kill_avg,
        "progression_level_up_avg": level_up_avg,
        "streak_progress_avg": streak_progress_avg,
        "prestige_gain_avg": prestige_gain_avg,
        "trust_pull": trust_pull,
        "progression_spine_score": progression_spine_score,
        "progression_runtime_score": progression_runtime_score,
        "progression_total_score": progression_total_score,
        "progression_state": progression_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_gameplay_progression.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("GAMEPLAY_PROGRESSION_GOVERNOR")
    print(f"PROGRESSION_TOTAL_SCORE={progression_total_score}")
    print(f"PROGRESSION_STATE={progression_state}")
    print(f"QUEST_CHAIN_COUNT={quest_chain_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

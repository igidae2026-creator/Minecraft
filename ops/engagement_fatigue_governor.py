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
OUTPUT_DIR = RUNTIME / "engagement_fatigue"
SUMMARY_PATH = AUTONOMY / "engagement_fatigue_summary.yml"
STATUS_DIR = RUNTIME / "status"


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
    strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    gameplay_progression = load_yaml(AUTONOMY / "gameplay_progression_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    content_volume = load_yaml(AUTONOMY / "content_volume_summary.yml")

    status_count = 0
    queue_total = 0.0
    event_join_total = 0.0
    return_reward_total = 0.0
    rivalry_total = 0.0
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        status_count += 1
        queue_total += float(payload.get("queue_size", 0) or 0)
        event_join_total += float(payload.get("event_join_count", 0) or 0)
        return_reward_total += float(payload.get("return_player_reward", 0) or 0)
        rivalry_total += float(payload.get("rivalry_match", 0) or 0)

    divisor = max(1.0, float(status_count))
    queue_avg = round(queue_total / divisor, 2)
    event_join_avg = round(event_join_total / divisor, 2)
    return_reward_avg = round(return_reward_total / divisor, 2)
    rivalry_avg = round(rivalry_total / divisor, 2)

    generated = int(content.get("generated", 0))
    promoted = int(content.get("promoted", 0))
    held = int(content.get("held", 0))
    promoted_ratio = promoted / max(1, generated)
    first_loop_coverage = float(content.get("first_loop_coverage_score", 0.0))
    social_loop_density = float(content.get("social_loop_density", 0.0))
    replayable_loop_score = float(content.get("replayable_loop_score", 0.0))
    starter_reward_strength = float(content.get("starter_reward_strength", 0.0))
    rivalry_reward_pull = float(content.get("rivalry_reward_pull", 0.0))
    retention_proxy = float(content.get("average_retention_proxy", 0.0))
    completeness_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    progression_total_score = float(gameplay_progression.get("progression_total_score", 0.0))
    boost_reentry = bool(liveops.get("boost_reentry", False))
    boost_novelty = bool(liveops.get("boost_novelty", False))
    cadence_diversity_score = float(liveops.get("cadence_diversity_score", 0.0))
    promoted_actions = int(liveops.get("promoted_actions", 0))
    content_volume_score = float(content_volume.get("content_volume_score", 0.0))
    content_volume_state = str(content_volume.get("content_volume_state", ""))
    recommended_repairs = int(strategy.get("recommended_repairs_count", 0))

    thinness_score = round(
        clamp(
            1.0
            - (
                first_loop_coverage / 4.0
                + social_loop_density / 4.5
                + replayable_loop_score / 4.5
                + starter_reward_strength / 4.5
                + rivalry_reward_pull / 4.5
                + progression_total_score / 18.0
            )
            / 6.0,
            0.0,
            1.0,
        ),
        2,
    )
    repetition_score = round(
        clamp(
            0.25
            + queue_avg / 18.0
            + recommended_repairs / 10.0
            + held / max(1, generated) * 0.6
            - (0.15 if boost_reentry else 0.0),
            0.0,
            1.0,
        ),
        2,
    )
    repetition_score = round(
        clamp(
            repetition_score
            - cadence_diversity_score * 0.18
            - (0.1 if boost_novelty else 0.0)
            - (0.08 if content_volume_state == "mature" else 0.0)
            - min(0.08, content_volume_score / 100.0)
            - min(0.08, promoted_actions / 40.0)
            - (0.06 if event_join_avg >= 2200 else 0.0)
            - min(0.12, rivalry_reward_pull / 20.0),
            0.0,
            1.0,
        ),
        2,
    )
    novelty_gap_score = round(
        clamp(
            0.9
            - (
                promoted_ratio * 0.25
                + retention_proxy / 4.0
                + event_join_avg / 1800.0
                + rivalry_avg / 18.0
                + return_reward_avg / 180.0
                + completeness_percent / 120.0
                + cadence_diversity_score * 0.18
                + starter_reward_strength / 12.0
                + rivalry_reward_pull / 12.0
            ),
            0.0,
            1.0,
        ),
        2,
    )
    fatigue_gap_score = round(
        clamp(
            thinness_score * 0.4 + repetition_score * 0.35 + novelty_gap_score * 0.25,
            0.0,
            1.0,
        ),
        2,
    )
    if fatigue_gap_score >= 0.65:
        fatigue_state = "high"
    elif fatigue_gap_score >= 0.35:
        fatigue_state = "watch"
    else:
        fatigue_state = "low"

    payload = {
        "created_at": created_at,
        "status_files": int(status_count),
        "queue_avg": queue_avg,
        "event_join_avg": event_join_avg,
        "return_player_reward_avg": return_reward_avg,
        "rivalry_avg": rivalry_avg,
        "generated": generated,
        "promoted": promoted,
        "held": held,
        "recommended_repairs_count": recommended_repairs,
        "progression_total_score": progression_total_score,
        "estimated_completeness_percent": completeness_percent,
        "starter_reward_strength": starter_reward_strength,
        "rivalry_reward_pull": rivalry_reward_pull,
        "cadence_diversity_score": cadence_diversity_score,
        "promoted_actions": promoted_actions,
        "content_volume_score": content_volume_score,
        "content_volume_state": content_volume_state,
        "thinness_score": thinness_score,
        "repetition_score": repetition_score,
        "novelty_gap_score": novelty_gap_score,
        "fatigue_gap_score": fatigue_gap_score,
        "fatigue_state": fatigue_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_engagement_fatigue.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("ENGAGEMENT_FATIGUE_GOVERNOR")
    print(f"FATIGUE_STATE={fatigue_state}")
    print(f"FATIGUE_GAP_SCORE={fatigue_gap_score}")
    print(f"THINNESS_SCORE={thinness_score}")
    print(f"NOVELTY_GAP_SCORE={novelty_gap_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

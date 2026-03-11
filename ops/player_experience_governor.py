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
SUMMARY_PATH = AUTONOMY / "player_experience_summary.yml"
OUTPUT_DIR = RUNTIME / "player_experience"
ANTI_CHEAT_SUMMARY_PATH = AUTONOMY / "anti_cheat_governor_summary.yml"
FATIGUE_SUMMARY_PATH = AUTONOMY / "engagement_fatigue_summary.yml"
CONTENT_VOLUME_SUMMARY_PATH = AUTONOMY / "content_volume_summary.yml"
PLAYER_EXPERIENCE_SOAK_SUMMARY_PATH = AUTONOMY / "player_experience_soak_summary.yml"


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
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    anti_cheat = load_yaml(ANTI_CHEAT_SUMMARY_PATH)
    fatigue = load_yaml(FATIGUE_SUMMARY_PATH)
    content_volume = load_yaml(CONTENT_VOLUME_SUMMARY_PATH)
    player_experience_soak = load_yaml(PLAYER_EXPERIENCE_SOAK_SUMMARY_PATH)

    totals = {
        "queue_size": 0.0,
        "player_density": 0.0,
        "event_join_count": 0.0,
        "return_player_reward": 0.0,
        "guild_joined": 0.0,
        "rivalry_match": 0.0,
        "status_files": 0.0,
    }
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1
        for key in totals:
            if key == "status_files":
                continue
            totals[key] += float(payload.get(key, 0) or 0)

    divisor = max(1.0, totals["status_files"])
    queue_avg = round(totals["queue_size"] / divisor, 2)
    density_avg = round(totals["player_density"] / divisor, 2)
    event_join_avg = round(totals["event_join_count"] / divisor, 2)
    return_reward_avg = round(totals["return_player_reward"] / divisor, 2)
    social_pressure = round((totals["guild_joined"] + totals["rivalry_match"]) / divisor, 2)

    quality_score = float(content.get("average_quality_score", 0.0))
    retention_proxy = float(content.get("average_retention_proxy", 0.0))
    first_loop_coverage = float(content.get("first_loop_coverage_score", 0.0))
    social_loop_density = float(content.get("social_loop_density", 0.0))
    replayable_loop_score = float(content.get("replayable_loop_score", 0.0))
    advanced_loop_strength = float(content.get("advanced_loop_strength", 0.0))
    prestige_loop_strength = float(content.get("prestige_loop_strength", 0.0))
    social_persistence_strength = float(content.get("social_persistence_strength", 0.0))
    spectacle_variety_strength = float(content.get("spectacle_variety_strength", 0.0))
    mastery_arc_strength = float(content.get("mastery_arc_strength", 0.0))
    prestige_clarity_strength = float(content.get("prestige_clarity_strength", 0.0))
    endgame_breadth_strength = float(content.get("endgame_breadth_strength", 0.0))
    returner_retention_strength = float(content.get("returner_retention_strength", 0.0))
    starter_reward_strength = float(content.get("starter_reward_strength", 0.0))
    rivalry_reward_pull = float(content.get("rivalry_reward_pull", 0.0))
    held_actions = int(liveops.get("held_actions", 0))
    progression_protection_score = float(anti_cheat.get("progression_protection_score", 0.0))
    trusted_progression_window = bool(anti_cheat.get("trusted_progression_window", False))
    cadence_diversity_score = float(liveops.get("cadence_diversity_score", 0.0))
    sustain_social = bool(liveops.get("sustain_social", False))
    returner_reactivation_depth = float(liveops.get("returner_reactivation_depth", 0.0))
    long_soak_confidence = float(player_experience_soak.get("long_soak_confidence", 0.0))
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 0.0))
    thinness_score = float(fatigue.get("thinness_score", 0.0))
    repetition_score = float(fatigue.get("repetition_score", 0.0))
    novelty_gap_score = float(fatigue.get("novelty_gap_score", 0.0))
    fatigue_state = str(fatigue.get("fatigue_state", ""))
    content_volume_score = float(content_volume.get("content_volume_score", 0.0))
    volume_pull = round(clamp(content_volume_score / 10.0, 0.0, 1.0), 2)

    onboarding_tempo = round(clamp((return_reward_avg / 120.0) + ((12.0 - queue_avg) / 18.0), 0.0, 1.0), 2)
    reward_tempo = round(clamp((return_reward_avg / 110.0) + (quality_score / 20.0) + (starter_reward_strength / 4.0), 0.0, 1.0), 2)
    social_stickiness = round(clamp((social_pressure / 24.0) + (event_join_avg / 2200.0) + (social_loop_density / 5.0) + (rivalry_reward_pull / 4.0) + cadence_diversity_score * 0.25, 0.0, 1.0), 2)
    if sustain_social:
        social_stickiness = round(clamp(social_stickiness + 0.08, 0.0, 1.0), 2)
    replay_pull = round(clamp((event_join_avg / 1800.0) + (retention_proxy / 3.5) + (replayable_loop_score / 5.0) + cadence_diversity_score * 0.3, 0.0, 1.0), 2)
    friction_penalty = round(clamp(max(0.0, (queue_avg - 4.0) / 12.0) + (held_actions / 4.0) + fatigue_gap_score * 0.45, 0.0, 1.0), 2)
    first_session_strength = round(clamp((first_loop_coverage / 3.0) + onboarding_tempo * 0.35, 0.0, 1.0), 2)
    trust_pull = round(clamp(progression_protection_score + (0.1 if trusted_progression_window else 0.0), 0.0, 1.0), 2)

    weighted_score = (
        first_session_strength * 0.24
        + reward_tempo * 0.19
        + social_stickiness * 0.2
        + replay_pull * 0.19
        + onboarding_tempo * 0.08
        + trust_pull * 0.1
        + volume_pull * 0.1
        + min(1.0, advanced_loop_strength / 3.0) * 0.08
        + min(1.0, prestige_loop_strength / 3.0) * 0.08
        + min(1.0, social_persistence_strength / 3.0) * 0.07
        + min(1.0, spectacle_variety_strength / 3.0) * 0.07
        + min(1.0, mastery_arc_strength / 3.0) * 0.07
        + min(1.0, prestige_clarity_strength / 3.0) * 0.06
        + min(1.0, endgame_breadth_strength / 3.0) * 0.06
        + min(1.0, returner_retention_strength / 3.0) * 0.07
        + min(1.0, returner_reactivation_depth / 2.0) * 0.05
        + long_soak_confidence * 0.06
    )
    completeness_percent = round(
        clamp(
            12.0
            + weighted_score * 38.0
            - friction_penalty * 8.0
            + (2.0 if fatigue_gap_score <= 0.32 else 0.0),
            0.0,
            100.0,
        ),
        1,
    )
    if completeness_percent < 25.0:
        state = "early"
    elif completeness_percent < 45.0:
        state = "mid"
    else:
        state = "advanced"

    payload = {
        "created_at": created_at,
        "queue_avg": queue_avg,
        "player_density_avg": density_avg,
        "event_join_avg": event_join_avg,
        "return_player_reward_avg": return_reward_avg,
        "social_pressure": social_pressure,
        "onboarding_tempo": onboarding_tempo,
        "reward_tempo": reward_tempo,
        "social_stickiness": social_stickiness,
        "replay_pull": replay_pull,
        "first_session_strength": first_session_strength,
        "first_loop_coverage_score": first_loop_coverage,
        "social_loop_density": social_loop_density,
        "replayable_loop_score": replayable_loop_score,
        "advanced_loop_strength": advanced_loop_strength,
        "prestige_loop_strength": prestige_loop_strength,
        "social_persistence_strength": social_persistence_strength,
        "spectacle_variety_strength": spectacle_variety_strength,
        "mastery_arc_strength": mastery_arc_strength,
        "prestige_clarity_strength": prestige_clarity_strength,
        "endgame_breadth_strength": endgame_breadth_strength,
        "returner_retention_strength": returner_retention_strength,
        "starter_reward_strength": starter_reward_strength,
        "rivalry_reward_pull": rivalry_reward_pull,
        "progression_protection_score": progression_protection_score,
        "trusted_progression_window": trusted_progression_window,
        "trust_pull": trust_pull,
        "volume_pull": volume_pull,
        "content_volume_score": content_volume_score,
        "cadence_diversity_score": cadence_diversity_score,
        "sustain_social": sustain_social,
        "returner_reactivation_depth": returner_reactivation_depth,
        "long_soak_confidence": long_soak_confidence,
        "thinness_score": thinness_score,
        "repetition_score": repetition_score,
        "novelty_gap_score": novelty_gap_score,
        "fatigue_gap_score": fatigue_gap_score,
        "fatigue_state": fatigue_state,
        "friction_penalty": friction_penalty,
        "weighted_score": round(weighted_score, 3),
        "estimated_completeness_percent": completeness_percent,
        "experience_state": state,
        "next_focus_hint": str(strategy.get("next_focus_csv", "")),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_player_experience.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("PLAYER_EXPERIENCE_GOVERNOR")
    print(f"ESTIMATED_COMPLETENESS_PERCENT={completeness_percent}")
    print(f"EXPERIENCE_STATE={state}")
    print(f"EVENT_JOIN_AVG={event_join_avg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

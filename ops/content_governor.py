#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
CONFIG = ROOT / "configs"
CONTROL_STATE = RUNTIME / "autonomy" / "control" / "state.yml"
CONTENT_DIR = RUNTIME / "content_pipeline"
SUMMARY_PATH = RUNTIME / "autonomy" / "content_governor_summary.yml"
LEDGER_PATH = CONTENT_DIR / "ledger.jsonl"
PLAYER_EXPERIENCE_SUMMARY_PATH = RUNTIME / "autonomy" / "player_experience_summary.yml"
FATIGUE_SUMMARY_PATH = RUNTIME / "autonomy" / "engagement_fatigue_summary.yml"
CONTENT_VOLUME_SUMMARY_PATH = RUNTIME / "autonomy" / "content_volume_summary.yml"
MIN_DEPTH_SCORE = 2.0


def score_candidate(*, artifact_type: str, validation: dict[str, bool], generated_payload: dict[str, Any]) -> dict[str, float]:
    validation_score = sum(1 for passed in validation.values() if passed)
    depth_score = 1.0
    retention_proxy = 1.0
    economy_safety = 1.0
    if artifact_type == "quest":
        reward = generated_payload.get("reward", {}) or {}
        depth_score += 0.4 if generated_payload.get("repeatable", False) else 0.1
        depth_score += min(1.0, int(generated_payload.get("amount", 0)) / 10.0)
        retention_proxy += 0.5 if reward.get("xp", 0) else 0.0
        economy_safety += 0.5 if int(reward.get("gold", 0)) <= 120 else 0.1
    elif artifact_type == "quest_chain":
        steps = generated_payload.get("steps", []) or []
        depth_score += min(2.2, len(steps) * 0.5)
        depth_score += 0.35 if generated_payload.get("finale_gate") else 0.0
        retention_proxy += 0.8 if generated_payload.get("branching_rewards", False) else 0.2
        retention_proxy += 0.4 if generated_payload.get("returner_bonus", False) else 0.0
        economy_safety += 0.4 if int(generated_payload.get("total_gold", 0)) <= 280 else 0.1
    elif artifact_type == "dungeon":
        enemy_groups = generated_payload.get("enemy_groups", []) or []
        depth_score += min(1.5, len(enemy_groups) * 0.25)
        retention_proxy += 0.6 if generated_payload.get("reward_tier") == "elite" else 0.3
        economy_safety += 0.4 if float(generated_payload.get("difficulty_scaling", 0.0)) <= 1.35 else 0.1
    elif artifact_type == "dungeon_variation":
        modifiers = generated_payload.get("modifiers", []) or []
        depth_score += min(2.2, len(modifiers) * 0.6)
        depth_score += 0.3 if generated_payload.get("boss_rotation") else 0.0
        retention_proxy += 0.7 if generated_payload.get("weekly_rotation", False) else 0.2
        retention_proxy += 0.3 if generated_payload.get("returner_bonus") else 0.0
        economy_safety += 0.4 if generated_payload.get("reward_tier") in {"starter", "elite"} else 0.1
    elif artifact_type == "season":
        axes = generated_payload.get("seasonal_axes", []) or []
        depth_score += min(2.2, len(axes) * 0.38)
        depth_score += 0.3 if generated_payload.get("seasonal_progression_arc") else 0.0
        retention_proxy += 0.8 if generated_payload.get("seasonal_progression", False) else 0.3
        retention_proxy += 0.4 if generated_payload.get("returner_catchup") else 0.0
        economy_safety += 0.3
    elif artifact_type == "onboarding":
        phases = generated_payload.get("phases", []) or []
        depth_score += min(1.8, len(phases) * 0.32)
        retention_proxy += 0.7 if generated_payload.get("idempotent_reward", False) else 0.2
        retention_proxy += 0.4 if generated_payload.get("party_prompt", False) or "first_party_prompt" in phases else 0.0
        economy_safety += 0.4
    elif artifact_type == "social":
        objectives = generated_payload.get("shared_objectives", []) or []
        depth_score += min(1.8, len(objectives) * 0.38)
        retention_proxy += 0.8 if generated_payload.get("returner_bonus", False) else 0.3
        retention_proxy += 0.3 if generated_payload.get("async_competition", False) else 0.0
        economy_safety += 0.4
    elif artifact_type == "event":
        challenges = generated_payload.get("challenge_steps", []) or []
        depth_score += min(1.6, len(challenges) * 0.34)
        retention_proxy += 0.7 if generated_payload.get("returner_bonus", False) else 0.3
        retention_proxy += 0.2 if generated_payload.get("broadcast_emphasis") == "high" else 0.0
        economy_safety += 0.4
    total_score = round(validation_score + depth_score + retention_proxy + economy_safety, 2)
    return {
        "validation_score": float(validation_score),
        "depth_score": round(depth_score, 2),
        "retention_proxy": round(retention_proxy, 2),
        "economy_safety": round(economy_safety, 2),
        "total_score": total_score,
    }


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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def content_candidates() -> list[dict[str, Any]]:
    templates = load_yaml(CONFIG / "dungeon_templates.yml").get("templates", {})
    scheduler = load_yaml(CONFIG / "event_scheduler.yml").get("events", {})
    events = load_yaml(CONFIG / "events.yml").get("events", {})
    quests = load_yaml(CONFIG / "quests.yml")
    guilds = (load_yaml(CONFIG / "guilds.yml").get("guilds", {}) or {})
    reward_pools = load_yaml(CONFIG / "reward_pools.yml").get("pools", {})
    player_experience = load_yaml(PLAYER_EXPERIENCE_SUMMARY_PATH)
    fatigue = load_yaml(FATIGUE_SUMMARY_PATH)
    content_volume = load_yaml(CONTENT_VOLUME_SUMMARY_PATH)
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_state = str(player_experience.get("experience_state", ""))
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 0.0))
    fatigue_high = fatigue_gap_score >= 0.45
    content_volume_score = float(content_volume.get("content_volume_score", 0.0))
    volume_low = content_volume_score < 7.5

    candidates: list[dict[str, Any]] = []
    for template_id, template in sorted(templates.items()):
        hold = float(template.get("difficulty_scaling", 1.0)) > 1.5
        candidates.append(
            {
                "artifact_type": "dungeon",
                "artifact_id": template_id,
                "scaffold": {
                    "layout_type": template.get("layout_type", "unknown"),
                    "boss_type": template.get("boss_type", "unknown"),
                },
                "generated_payload": template,
                "validation": {
                    "scope_fit": bool(template.get("enemy_groups")),
                    "reward_tier_known": template.get("reward_tier") in reward_pools,
                    "party_bounds_valid": int(template.get("recommended_party_size", 0)) <= int(template.get("player_cap", 0)),
                },
                "verdict": "hold" if hold else "promote",
                "reason": "difficulty exceeds governed starter bounds" if hold else "template fits governed dungeon pipeline",
            }
        )
    for event_id, event in sorted(scheduler.items()):
        hold = int(event.get("cooldown_minutes", 0)) < 20
        candidates.append(
            {
                "artifact_type": "event",
                "artifact_id": event_id,
                "scaffold": {
                    "event_type": event.get("type", "unknown"),
                    "reward_pool": event.get("reward_pool", "unknown"),
                },
                "generated_payload": event,
                "validation": {
                    "scope_fit": bool(event.get("type")),
                    "reward_pool_known": event.get("reward_pool") in reward_pools,
                    "cooldown_governed": int(event.get("cooldown_minutes", 0)) >= 20,
                },
                "verdict": "hold" if hold else "promote",
                "reason": "event cadence is too aggressive for fail-closed rollout" if hold else "event fits governed live content rotation",
            }
        )
    for quest_id, quest in sorted(quests.items()):
        reward = quest.get("reward", {}) or {}
        hold = int(reward.get("gold", 0)) <= 0 or int(quest.get("amount", 0)) <= 0
        candidates.append(
            {
                "artifact_type": "quest",
                "artifact_id": quest_id,
                "scaffold": {
                    "objective": quest.get("objective", "unknown"),
                    "repeatable": bool(quest.get("repeatable", False)),
                },
                "generated_payload": quest,
                "validation": {
                    "scope_fit": bool(quest.get("objective")),
                    "positive_reward": int(reward.get("gold", 0)) > 0 or int(reward.get("xp", 0)) > 0,
                    "amount_valid": int(quest.get("amount", 0)) > 0,
                },
                "verdict": "hold" if hold else "promote",
                "reason": "quest payload lacks governed reward or amount" if hold else "quest fits governed progression loop",
            }
        )
    quest_items = sorted(quests.items())
    if len(quest_items) >= 3:
        chain_steps = []
        total_gold = 0
        total_xp = 0
        for quest_id, quest in quest_items[:3]:
            reward = quest.get("reward", {}) or {}
            chain_steps.append(
                {
                    "quest_id": quest_id,
                    "objective": quest.get("objective", "unknown"),
                    "amount": int(quest.get("amount", 0)),
                    "repeatable": bool(quest.get("repeatable", False)),
                }
            )
            total_gold += int(reward.get("gold", 0))
            total_xp += int(reward.get("xp", 0))
        chain_payload = {
            "steps": chain_steps,
            "branching_rewards": True,
            "total_gold": total_gold,
            "total_xp": total_xp,
            "finale_gate": "boss_unlock",
        }
        chain_validation = {
            "scope_fit": len(chain_steps) >= 3,
            "progression_curve_present": total_xp > 0,
            "economy_budget_governed": total_gold <= 280,
        }
        candidates.append(
            {
                "artifact_type": "quest_chain",
                "artifact_id": "starter_to_guardian_chain",
                "scaffold": {
                    "step_count": len(chain_steps),
                    "finale_gate": "boss_unlock",
                },
                "generated_payload": chain_payload,
                "validation": chain_validation,
                "verdict": "promote" if all(chain_validation.values()) else "hold",
                "reason": "quest chain creates multi-session progression spine" if all(chain_validation.values()) else "quest chain exceeds governed economy or progression bounds",
            }
        )
    for template_id, template in sorted(templates.items()):
        modifiers = ["timer_pressure", "elite_pack_rotation", "reward_bonus_window"]
        variation_payload = {
            "base_template": template_id,
            "modifiers": modifiers[: 2 if template.get("reward_tier") == "starter" else 3],
            "weekly_rotation": True,
            "reward_tier": template.get("reward_tier", "starter"),
            "boss_rotation": template.get("boss_type", "") not in {"", "none"},
        }
        variation_validation = {
            "scope_fit": bool(template.get("enemy_groups")),
            "modifier_count_valid": len(variation_payload["modifiers"]) >= 2,
            "difficulty_governed": float(template.get("difficulty_scaling", 0.0)) <= 1.4,
        }
        candidates.append(
            {
                "artifact_type": "dungeon_variation",
                "artifact_id": f"{template_id}_weekly_variation",
                "scaffold": {
                    "base_template": template_id,
                    "layout_type": template.get("layout_type", "unknown"),
                },
                "generated_payload": variation_payload,
                "validation": variation_validation,
                "verdict": "promote" if all(variation_validation.values()) else "hold",
                "reason": "variation engine increases replay depth without new manual maps" if all(variation_validation.values()) else "variation exceeds governed dungeon bounds",
            }
        )

    candidates.append(
        {
            "artifact_type": "onboarding",
            "artifact_id": "starter_route_onboarding",
            "scaffold": {
                "route_family": "first_join_router",
                "target_servers": ["rpg_world", "boss_world", "events"],
            },
            "generated_payload": {
                "phases": ["lobby_router", "first_reward", "branch_selection", "first_transfer"],
                "reward_pool": "starter",
                "idempotent_reward": True,
            },
            "validation": {
                "scope_fit": True,
                "reward_pool_known": "starter" in reward_pools,
                "exploration_os_compatible": True,
            },
            "verdict": "promote",
            "reason": "onboarding artifact standardizes first-session conversion as governed content",
        }
    )
    candidates.append(
        {
            "artifact_type": "social",
            "artifact_id": "guild_rivalry_ladder",
            "scaffold": {
                "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
            },
                "generated_payload": {
                    "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                    "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                    "points": (guilds.get("progression", {}) or {}).get("points", {}),
                    "shared_objectives": ["guild_rank_push", "rivalry_chain", "weekly_boss_clear"],
                    "async_competition": True,
                },
            "validation": {
                "scope_fit": bool(guilds),
                "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
            },
            "verdict": "promote",
            "reason": "social artifact standardizes guild/rivalry progression as replayable operating content",
        }
    )
    candidates.append(
        {
            "artifact_type": "season",
            "artifact_id": "frontier_rotation_season",
            "scaffold": {
                "scheduled_events": sorted(scheduler.keys()),
                "content_sources": sorted(events.keys()),
            },
            "generated_payload": {
                "season_objective": "rotate repeatable events, quests, and rivalry pressure under governed cadence",
                "cadence_minutes": int(load_yaml(CONFIG / "event_scheduler.yml").get("rotation", {}).get("dungeon_rotation_minutes", 0)),
                "seasonal_axes": ["event_rotation", "quest_repeatables", "guild_rivalry", "economy_observe"],
                "seasonal_progression": True,
                "seasonal_progression_arc": ["starter_track", "rivalry_track", "boss_unlock_track"],
                "badge_targets": sorted(((load_yaml(CONFIG / "prestige.yml").get("prestige", {}) or {}).get("badges", {}) or {}).keys()),
            },
            "validation": {
                "scope_fit": bool(scheduler) and bool(events),
                "scheduled_matches_source_events": all(event_id in events for event_id in scheduler),
                "exploration_os_compatible": True,
            },
            "verdict": "promote",
            "reason": "season artifact closes live content rotation as governed operating content",
        }
    )
    if experience_percent < 45.0 or experience_state in {"early", "mid"}:
        candidates.append(
            {
                "artifact_type": "onboarding",
                "artifact_id": "accelerated_first_loop_onboarding",
                "scaffold": {
                    "route_family": "fast_first_fun",
                    "target_servers": ["lobby", "events", "rpg_world"],
                },
                "generated_payload": {
                    "phases": ["instant_reward", "event_hook", "class_probe", "first_party_prompt"],
                    "reward_pool": "starter",
                    "idempotent_reward": True,
                    "tempo_bias": "fast",
                    "party_prompt": True,
                },
                "validation": {
                    "scope_fit": True,
                    "reward_pool_known": "starter" in reward_pools,
                    "exploration_os_compatible": True,
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers extra onboarding acceleration artifact",
            }
        )
        candidates.append(
            {
                "artifact_type": "social",
                "artifact_id": "returner_rivalry_week",
                "scaffold": {
                    "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                    "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
                },
                "generated_payload": {
                    "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                    "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                    "points": (guilds.get("progression", {}) or {}).get("points", {}),
                    "returner_bonus": True,
                    "shared_objectives": ["returner_guild_join", "rivalry_duo_clear", "guild_streak_bonus"],
                    "async_competition": True,
                },
                "validation": {
                    "scope_fit": bool(guilds),
                    "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                    "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers extra social rivalry artifact",
            }
        )
        candidates.append(
            {
                "artifact_type": "event",
                "artifact_id": "returner_flash_event",
                "scaffold": {
                    "event_type": "flash_reentry",
                    "reward_pool": "starter",
                },
                "generated_payload": {
                    "type": "flash_reentry",
                    "reward_pool": "starter",
                    "cooldown_minutes": 30,
                    "returner_bonus": True,
                    "broadcast_emphasis": "high",
                    "challenge_steps": ["join_window", "party_queue", "reward_claim"],
                },
                "validation": {
                    "scope_fit": True,
                    "reward_pool_known": "starter" in reward_pools,
                    "cooldown_governed": True,
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers extra re-entry event artifact",
            }
        )
        candidates.append(
            {
                "artifact_type": "onboarding",
                "artifact_id": "guided_party_launch_onboarding",
                "scaffold": {
                    "route_family": "guided_social_start",
                    "target_servers": ["lobby", "events", "dungeons"],
                },
                "generated_payload": {
                    "phases": ["instant_reward", "class_probe", "party_formation", "first_event", "first_dungeon_vote"],
                    "reward_pool": "starter",
                    "idempotent_reward": True,
                    "tempo_bias": "fast",
                    "party_prompt": True,
                },
                "validation": {
                    "scope_fit": True,
                    "reward_pool_known": "starter" in reward_pools,
                    "exploration_os_compatible": True,
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers a deeper first-session onboarding loop",
            }
        )
        candidates.append(
            {
                "artifact_type": "social",
                "artifact_id": "guild_returner_cohort",
                "scaffold": {
                    "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                    "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
                },
                "generated_payload": {
                    "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                    "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                    "points": (guilds.get("progression", {}) or {}).get("points", {}),
                    "returner_bonus": True,
                    "shared_objectives": ["cohort_matchmaking", "guild_assist_chain", "returner_boss_support"],
                    "async_competition": True,
                },
                "validation": {
                    "scope_fit": bool(guilds),
                    "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                    "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers a deeper social retention arc",
            }
        )
        candidates.append(
            {
                "artifact_type": "season",
                "artifact_id": "returner_reactivation_season",
                "scaffold": {
                    "scheduled_events": sorted(scheduler.keys()),
                    "content_sources": sorted(events.keys()),
                },
                "generated_payload": {
                    "season_objective": "reactivate returners through short social loops, flash events, and dungeon modifiers",
                    "cadence_minutes": int(load_yaml(CONFIG / "event_scheduler.yml").get("rotation", {}).get("event_window_minutes", 0)),
                    "seasonal_axes": ["returner_flash_events", "guild_cohorts", "starter_dungeon_variants", "fast_track_rewards", "streak_recovery"],
                    "seasonal_progression": True,
                    "seasonal_progression_arc": ["returner_catchup", "guild_race", "flash_dungeon_weekend", "prestige_bridge"],
                    "returner_catchup": True,
                    "badge_targets": sorted(((load_yaml(CONFIG / "prestige.yml").get("prestige", {}) or {}).get("badges", {}) or {}).keys()),
                },
                "validation": {
                    "scope_fit": bool(scheduler) and bool(events),
                    "scheduled_matches_source_events": all(event_id in events for event_id in scheduler),
                    "exploration_os_compatible": True,
                },
                "verdict": "promote",
                "reason": "low player-facing completeness triggers a deeper seasonal returner loop",
            }
        )
        if len(quest_items) >= 4:
            mastery_steps = []
            mastery_gold = 0
            mastery_xp = 0
            for quest_id, quest in quest_items[:4]:
                reward = quest.get("reward", {}) or {}
                mastery_steps.append(
                    {
                        "quest_id": quest_id,
                        "objective": quest.get("objective", "unknown"),
                        "amount": int(quest.get("amount", 0)),
                        "repeatable": bool(quest.get("repeatable", False)),
                    }
                )
                mastery_gold += int(reward.get("gold", 0))
                mastery_xp += int(reward.get("xp", 0))
            mastery_payload = {
                "steps": mastery_steps,
                "branching_rewards": True,
                "total_gold": mastery_gold,
                "total_xp": mastery_xp,
                "finale_gate": "rivalry_boss_unlock",
                "returner_bonus": True,
            }
            mastery_validation = {
                "scope_fit": len(mastery_steps) >= 4,
                "progression_curve_present": mastery_xp > 0,
                "economy_budget_governed": mastery_gold <= 420,
            }
            candidates.append(
                {
                    "artifact_type": "quest_chain",
                    "artifact_id": "returner_mastery_chain",
                    "scaffold": {
                        "step_count": len(mastery_steps),
                        "finale_gate": "rivalry_boss_unlock",
                    },
                    "generated_payload": mastery_payload,
                    "validation": mastery_validation,
                    "verdict": "promote" if all(mastery_validation.values()) else "hold",
                    "reason": "low player-facing completeness triggers a longer mastery quest chain" if all(mastery_validation.values()) else "mastery quest chain exceeds governed economy or progression bounds",
                }
            )
    if fatigue_high:
        candidates.extend(
            [
                {
                    "artifact_type": "event",
                    "artifact_id": "novelty_burst_week",
                    "scaffold": {
                        "event_type": "novelty_burst",
                        "reward_pool": "starter",
                    },
                    "generated_payload": {
                        "type": "novelty_burst",
                        "reward_pool": "starter",
                        "cooldown_minutes": 45,
                        "returner_bonus": True,
                        "broadcast_emphasis": "high",
                        "challenge_steps": ["flash_objective", "remix_route", "bonus_cache"],
                    },
                    "validation": {
                        "scope_fit": True,
                        "reward_pool_known": "starter" in reward_pools,
                        "cooldown_governed": True,
                    },
                    "verdict": "promote",
                    "reason": "fatigue pressure triggers a novelty burst event artifact",
                },
                {
                    "artifact_type": "social",
                    "artifact_id": "guild_rivalry_remix",
                    "scaffold": {
                        "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                        "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
                    },
                    "generated_payload": {
                        "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                        "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                        "points": (guilds.get("progression", {}) or {}).get("points", {}),
                        "returner_bonus": True,
                        "shared_objectives": ["guild_relay", "remix_rivalry", "shared_unlock"],
                        "async_competition": True,
                    },
                    "validation": {
                        "scope_fit": bool(guilds),
                        "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                        "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                    },
                    "verdict": "promote",
                    "reason": "fatigue pressure triggers a remix social artifact",
                },
                {
                    "artifact_type": "season",
                    "artifact_id": "returner_reactivation_season_plus",
                    "scaffold": {
                        "scheduled_events": sorted(scheduler.keys()),
                        "content_sources": sorted(events.keys()),
                    },
                    "generated_payload": {
                        "season_objective": "reactivate players with novelty bursts, remix rivalries, and returner mastery arcs",
                        "cadence_minutes": int(load_yaml(CONFIG / "event_scheduler.yml").get("rotation", {}).get("event_window_minutes", 0)),
                        "seasonal_axes": ["novelty_burst", "guild_remix", "returner_mastery", "boss_gauntlet"],
                        "seasonal_progression": True,
                        "seasonal_progression_arc": ["return", "remix", "mastery", "prestige"],
                        "returner_catchup": True,
                        "badge_targets": sorted(((load_yaml(CONFIG / "prestige.yml").get("prestige", {}) or {}).get("badges", {}) or {}).keys()),
                    },
                    "validation": {
                        "scope_fit": bool(scheduler) and bool(events),
                        "scheduled_matches_source_events": all(event_id in events for event_id in scheduler),
                        "exploration_os_compatible": True,
                    },
                    "verdict": "promote",
                    "reason": "fatigue pressure triggers a stronger reactivation season frame",
                },
            ]
        )
        for template_id, template in sorted(templates.items()):
            gauntlet_payload = {
                "base_template": template_id,
                "modifiers": ["timer_pressure", "elite_pack_rotation", "boss_enrage_window", "returner_bonus_window"],
                "weekly_rotation": True,
                "reward_tier": template.get("reward_tier", "starter"),
                "boss_rotation": template.get("boss_type", "") not in {"", "none"},
                "returner_bonus": True,
            }
            gauntlet_validation = {
                "scope_fit": bool(template.get("enemy_groups")),
                "modifier_count_valid": len(gauntlet_payload["modifiers"]) >= 4,
                "difficulty_governed": float(template.get("difficulty_scaling", 0.0)) <= 1.45,
            }
            candidates.append(
                {
                    "artifact_type": "dungeon_variation",
                    "artifact_id": f"{template_id}_boss_gauntlet_variation",
                    "scaffold": {
                        "base_template": template_id,
                        "layout_type": template.get("layout_type", "unknown"),
                    },
                    "generated_payload": gauntlet_payload,
                    "validation": gauntlet_validation,
                    "verdict": "promote" if all(gauntlet_validation.values()) else "hold",
                    "reason": "low player-facing completeness triggers a deeper boss gauntlet variation" if all(gauntlet_validation.values()) else "gauntlet variation exceeds governed dungeon bounds",
                }
            )
    if volume_low:
        candidates.extend(
            [
                {
                    "artifact_type": "event",
                    "artifact_id": "showcase_rotation_week",
                    "scaffold": {
                        "event_type": "showcase_rotation",
                        "reward_pool": "starter",
                    },
                    "generated_payload": {
                        "type": "showcase_rotation",
                        "reward_pool": "starter",
                        "cooldown_minutes": 40,
                        "broadcast_emphasis": "high",
                        "challenge_steps": ["daily_showcase", "party_showcase", "bonus_claim", "remix_vote"],
                        "returner_bonus": True,
                    },
                    "validation": {
                        "scope_fit": True,
                        "reward_pool_known": "starter" in reward_pools,
                        "cooldown_governed": True,
                    },
                    "verdict": "promote",
                    "reason": "low content volume triggers an extra showcase event rotation",
                },
                {
                    "artifact_type": "social",
                    "artifact_id": "guild_showcase_circuit",
                    "scaffold": {
                        "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                        "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
                    },
                    "generated_payload": {
                        "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                        "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                        "points": (guilds.get("progression", {}) or {}).get("points", {}),
                        "returner_bonus": True,
                        "shared_objectives": ["showcase_party_chain", "guild_route_clear", "rivalry_bonus_vote", "weekly_assist_bonus"],
                        "async_competition": True,
                    },
                    "validation": {
                        "scope_fit": bool(guilds),
                        "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                        "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                    },
                    "verdict": "promote",
                    "reason": "low content volume triggers an extra social showcase circuit",
                },
                {
                    "artifact_type": "onboarding",
                    "artifact_id": "showcase_path_onboarding",
                    "scaffold": {
                        "route_family": "spectacle_first_start",
                        "target_servers": ["lobby", "events", "boss_world"],
                    },
                    "generated_payload": {
                        "phases": ["instant_reward", "showcase_vote", "boss_preview", "party_prompt", "reward_preview"],
                        "reward_pool": "starter",
                        "idempotent_reward": True,
                        "tempo_bias": "fast",
                        "party_prompt": True,
                        "returner_bonus": True,
                    },
                    "validation": {
                        "scope_fit": True,
                        "reward_pool_known": "starter" in reward_pools,
                        "exploration_os_compatible": True,
                    },
                    "verdict": "promote",
                    "reason": "low content volume triggers a spectacle-first onboarding branch",
                },
                {
                    "artifact_type": "season",
                    "artifact_id": "showcase_ladder_season",
                    "scaffold": {
                        "scheduled_events": sorted(scheduler.keys()),
                        "content_sources": sorted(events.keys()),
                    },
                    "generated_payload": {
                        "season_objective": "expand visible content breadth with weekly showcases, social ladders, and boss previews",
                        "cadence_minutes": int(load_yaml(CONFIG / "event_scheduler.yml").get("rotation", {}).get("event_window_minutes", 0)),
                        "seasonal_axes": ["showcase_events", "guild_showcase", "boss_preview", "returner_bonus"],
                        "seasonal_progression": True,
                        "seasonal_progression_arc": ["showcase_entry", "group_route", "boss_preview", "prestige_bridge"],
                        "returner_catchup": True,
                        "badge_targets": sorted(((load_yaml(CONFIG / "prestige.yml").get("prestige", {}) or {}).get("badges", {}) or {}).keys()),
                    },
                    "validation": {
                        "scope_fit": bool(scheduler) and bool(events),
                        "scheduled_matches_source_events": all(event_id in events for event_id in scheduler),
                        "exploration_os_compatible": True,
                    },
                    "verdict": "promote",
                    "reason": "low content volume triggers a showcase-heavy seasonal frame",
                },
            ]
        )
        if len(quest_items) >= 5:
            showcase_steps = []
            showcase_gold = 0
            showcase_xp = 0
            for quest_id, quest in quest_items[:5]:
                reward = quest.get("reward", {}) or {}
                showcase_steps.append(
                    {
                        "quest_id": quest_id,
                        "objective": quest.get("objective", "unknown"),
                        "amount": int(quest.get("amount", 0)),
                        "repeatable": bool(quest.get("repeatable", False)),
                    }
                )
                showcase_gold += int(reward.get("gold", 0))
                showcase_xp += int(reward.get("xp", 0))
            showcase_payload = {
                "steps": showcase_steps,
                "branching_rewards": True,
                "total_gold": showcase_gold,
                "total_xp": showcase_xp,
                "finale_gate": "showcase_boss_vote",
                "returner_bonus": True,
            }
            showcase_validation = {
                "scope_fit": len(showcase_steps) >= 5,
                "progression_curve_present": showcase_xp > 0,
                "economy_budget_governed": showcase_gold <= 520,
            }
            candidates.append(
                {
                    "artifact_type": "quest_chain",
                    "artifact_id": "showcase_mastery_chain",
                    "scaffold": {
                        "step_count": len(showcase_steps),
                        "finale_gate": "showcase_boss_vote",
                    },
                    "generated_payload": showcase_payload,
                    "validation": showcase_validation,
                    "verdict": "promote" if all(showcase_validation.values()) else "hold",
                    "reason": "low content volume triggers a broader showcase quest chain" if all(showcase_validation.values()) else "showcase quest chain exceeds governed economy or progression bounds",
                }
            )
    if experience_state == "advanced" and fatigue_gap_score <= 0.3:
        candidates.extend(
            [
                {
                    "artifact_type": "onboarding",
                    "artifact_id": "advanced_returner_fastlane",
                    "scaffold": {
                        "route_family": "returner_fastlane",
                        "target_servers": ["lobby", "events", "dungeons", "boss_world"],
                    },
                    "generated_payload": {
                        "phases": ["returner_reward", "group_queue", "boss_preview", "season_track_pick", "party_rejoin"],
                        "reward_pool": "starter",
                        "idempotent_reward": True,
                        "tempo_bias": "fast",
                        "party_prompt": True,
                        "returner_bonus": True,
                    },
                    "validation": {
                        "scope_fit": True,
                        "reward_pool_known": "starter" in reward_pools,
                        "exploration_os_compatible": True,
                    },
                    "verdict": "promote",
                    "reason": "mature volume triggers an advanced returner fastlane branch",
                },
                {
                    "artifact_type": "social",
                    "artifact_id": "prestige_rivalry_circuit",
                    "scaffold": {
                        "guild_progression_levels": len((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                        "rivalry_threshold": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)),
                    },
                    "generated_payload": {
                        "reward_every": int((guilds.get("rivalry", {}) or {}).get("reward_every", 0)),
                        "broadcast_poll_seconds": int(guilds.get("broadcast_poll_seconds", 0)),
                        "points": (guilds.get("progression", {}) or {}).get("points", {}),
                        "returner_bonus": True,
                        "shared_objectives": ["prestige_race", "boss_support_chain", "guild_showcase_vote", "rivalry_streak_bonus"],
                        "async_competition": True,
                    },
                    "validation": {
                        "scope_fit": bool(guilds),
                        "rivalry_threshold_valid": int((guilds.get("rivalry", {}) or {}).get("created_threshold", 0)) >= 2,
                        "progression_defined": bool((guilds.get("progression", {}) or {}).get("level_thresholds", {})),
                    },
                    "verdict": "promote",
                    "reason": "mature volume triggers a denser prestige rivalry circuit",
                },
                {
                    "artifact_type": "season",
                    "artifact_id": "prestige_rotation_season",
                    "scaffold": {
                        "scheduled_events": sorted(scheduler.keys()),
                        "content_sources": sorted(events.keys()),
                    },
                    "generated_payload": {
                        "season_objective": "rotate prestige, rivalry, and boss-preview loops under a denser advanced season frame",
                        "cadence_minutes": int(load_yaml(CONFIG / "event_scheduler.yml").get("rotation", {}).get("event_window_minutes", 0)),
                        "seasonal_axes": ["prestige_race", "boss_preview", "guild_showcase", "returner_fastlane", "event_remix"],
                        "seasonal_progression": True,
                        "seasonal_progression_arc": ["fastlane", "rivalry_peak", "boss_gauntlet", "prestige_bridge"],
                        "returner_catchup": True,
                        "badge_targets": sorted(((load_yaml(CONFIG / "prestige.yml").get("prestige", {}) or {}).get("badges", {}) or {}).keys()),
                    },
                    "validation": {
                        "scope_fit": bool(scheduler) and bool(events),
                        "scheduled_matches_source_events": all(event_id in events for event_id in scheduler),
                        "exploration_os_compatible": True,
                    },
                    "verdict": "promote",
                    "reason": "mature volume triggers a denser prestige season frame",
                },
            ]
        )
    return candidates


def main() -> int:
    created_at = now_iso()
    control = load_yaml(CONTROL_STATE)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    execution_threshold_ready = bool(control.get("execution_threshold_ready", False))
    candidates = content_candidates() if execution_threshold_ready else []
    promoted = 0
    held = 0
    by_type: dict[str, int] = {}
    total_depth_score = 0.0
    total_retention_proxy = 0.0
    total_quality_score = 0.0
    starter_reward_strength = 0.0
    rivalry_reward_pull = 0.0

    for candidate in candidates:
        quality = score_candidate(
            artifact_type=candidate["artifact_type"],
            validation=candidate["validation"],
            generated_payload=candidate["generated_payload"],
        )
        if quality["depth_score"] < MIN_DEPTH_SCORE and candidate["verdict"] == "promote":
            candidate["verdict"] = "hold"
            candidate["reason"] = f"depth score {quality['depth_score']} is below governed content floor {MIN_DEPTH_SCORE}"
        artifact_id = f"content-{uuid.uuid4().hex[:12]}"
        payload = {
            "artifact_id": artifact_id,
            "created_at": created_at,
            "stage_flow": ["scaffold", "generate", "validate", "promote"],
            "artifact_type": candidate["artifact_type"],
            "artifact_key": candidate["artifact_id"],
            "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
            "scaffold": candidate["scaffold"],
            "generated_payload": candidate["generated_payload"],
            "validation": candidate["validation"],
            "quality": quality,
            "verdict": candidate["verdict"],
            "reason": candidate["reason"],
        }
        payload["signature"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        verdict_dir = CONTENT_DIR / candidate["verdict"]
        write_yaml(verdict_dir / f"{created_at.replace(':', '').replace('-', '')}_{artifact_id}.yml", payload)
        append_jsonl(
            LEDGER_PATH,
            {
                "created_at": created_at,
                "artifact_id": artifact_id,
                "artifact_type": candidate["artifact_type"],
                "artifact_key": candidate["artifact_id"],
                "verdict": candidate["verdict"],
                "signature": payload["signature"],
            },
        )
        by_type[candidate["artifact_type"]] = by_type.get(candidate["artifact_type"], 0) + 1
        total_depth_score += quality["depth_score"]
        total_retention_proxy += quality["retention_proxy"]
        total_quality_score += quality["total_score"]
        generated_payload = candidate["generated_payload"]
        artifact_type = candidate["artifact_type"]
        if artifact_type == "onboarding":
            starter_reward_strength += 0.9 if generated_payload.get("idempotent_reward", False) else 0.4
            starter_reward_strength += 0.5 if generated_payload.get("tempo_bias") == "fast" else 0.0
        elif artifact_type == "event":
            starter_reward_strength += 0.5 if generated_payload.get("reward_pool") == "starter" else 0.1
            starter_reward_strength += 0.35 if generated_payload.get("returner_bonus", False) else 0.0
        elif artifact_type == "quest_chain":
            starter_reward_strength += 0.45 if generated_payload.get("branching_rewards", False) else 0.1
        elif artifact_type == "season":
            starter_reward_strength += 0.3 if generated_payload.get("returner_catchup", False) else 0.0
        if artifact_type == "social":
            shared_objectives = generated_payload.get("shared_objectives", []) or []
            rivalry_reward_pull += min(1.0, len(shared_objectives) * 0.28)
            rivalry_reward_pull += 0.5 if generated_payload.get("async_competition", False) else 0.0
            rivalry_reward_pull += 0.4 if generated_payload.get("returner_bonus", False) else 0.0
        elif artifact_type == "season":
            rivalry_reward_pull += 0.3 if generated_payload.get("returner_catchup", False) else 0.0
        if candidate["verdict"] == "promote":
            promoted += 1
        else:
            held += 1

    summary = {
        "created_at": created_at,
        "generated": len(candidates),
        "promoted": promoted,
        "held": held,
        "by_type": by_type,
        "average_depth_score": round(total_depth_score / len(candidates), 2) if candidates else 0.0,
        "average_retention_proxy": round(total_retention_proxy / len(candidates), 2) if candidates else 0.0,
        "average_quality_score": round(total_quality_score / len(candidates), 2) if candidates else 0.0,
        "player_facing_generated": sum(by_type.get(name, 0) for name in ("onboarding", "social", "event", "season")),
        "first_loop_coverage_score": round(min(3.0, by_type.get("onboarding", 0) * 0.9 + by_type.get("event", 0) * 0.6 + by_type.get("quest_chain", 0) * 0.5), 2),
        "social_loop_density": round(min(3.0, by_type.get("social", 0) * 1.0 + by_type.get("season", 0) * 0.6), 2),
        "replayable_loop_score": round(min(3.0, by_type.get("dungeon_variation", 0) * 0.8 + by_type.get("season", 0) * 0.6 + by_type.get("event", 0) * 0.4), 2),
        "starter_reward_strength": round(min(3.0, starter_reward_strength), 2),
        "rivalry_reward_pull": round(min(3.0, rivalry_reward_pull), 2),
        "depth_floor": MIN_DEPTH_SCORE,
        "execution_threshold_ready": execution_threshold_ready,
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("CONTENT_GOVERNOR")
    print(f"GENERATED={len(candidates)}")
    print(f"PROMOTED={promoted}")
    print(f"HELD={held}")
    print(f"AVERAGE_DEPTH_SCORE={summary['average_depth_score']}")
    print(f"AVERAGE_QUALITY_SCORE={summary['average_quality_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

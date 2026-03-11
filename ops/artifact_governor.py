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
CONTROL_STATE = RUNTIME / "autonomy" / "control" / "state.yml"
SUMMARY_PATH = RUNTIME / "autonomy" / "artifact_governor_summary.yml"
CONTENT_SUMMARY_PATH = RUNTIME / "autonomy" / "content_governor_summary.yml"
CONTENT_STRATEGY_PATH = RUNTIME / "autonomy" / "content_strategy_summary.yml"
CONTENT_SOAK_PATH = RUNTIME / "autonomy" / "content_soak_summary.yml"
CONTENT_VOLUME_PATH = RUNTIME / "autonomy" / "content_volume_summary.yml"
REPO_BUNDLE_PATH = RUNTIME / "autonomy" / "repo_bundle_summary.yml"
MINECRAFT_BUNDLE_PATH = RUNTIME / "autonomy" / "minecraft_bundle_summary.yml"
MINECRAFT_STRATEGY_PATH = RUNTIME / "autonomy" / "minecraft_strategy_summary.yml"
MINECRAFT_SOAK_PATH = RUNTIME / "autonomy" / "minecraft_soak_summary.yml"
PLAYER_EXPERIENCE_PATH = RUNTIME / "autonomy" / "player_experience_summary.yml"
PLAYER_EXPERIENCE_SOAK_PATH = RUNTIME / "autonomy" / "player_experience_soak_summary.yml"
GAMEPLAY_PROGRESSION_PATH = RUNTIME / "autonomy" / "gameplay_progression_summary.yml"
ENGAGEMENT_FATIGUE_PATH = RUNTIME / "autonomy" / "engagement_fatigue_summary.yml"
SERVICE_RESPONSIVENESS_PATH = RUNTIME / "autonomy" / "service_responsiveness_summary.yml"
MATCHMAKING_QUALITY_PATH = RUNTIME / "autonomy" / "matchmaking_quality_summary.yml"
PROPOSAL_DIR = RUNTIME / "artifact_proposals"
CANONICAL_DIR = RUNTIME / "canonical_artifacts"
VERDICT_LOG = PROPOSAL_DIR / "verdicts.jsonl"
CANONICAL_LOG = CANONICAL_DIR / "registry.jsonl"


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


def proposal_key(scope: str, artifact_class: str) -> str:
    return f"{scope}:{artifact_class}"


def canonical_candidates(control: dict[str, Any]) -> list[dict[str, Any]]:
    content = load_yaml(CONTENT_SUMMARY_PATH)
    content_strategy = load_yaml(CONTENT_STRATEGY_PATH)
    content_soak = load_yaml(CONTENT_SOAK_PATH)
    content_volume = load_yaml(CONTENT_VOLUME_PATH)
    repo_bundle = load_yaml(REPO_BUNDLE_PATH)
    minecraft_bundle = load_yaml(MINECRAFT_BUNDLE_PATH)
    minecraft_strategy = load_yaml(MINECRAFT_STRATEGY_PATH)
    minecraft_soak = load_yaml(MINECRAFT_SOAK_PATH)
    player_experience = load_yaml(PLAYER_EXPERIENCE_PATH)
    player_experience_soak = load_yaml(PLAYER_EXPERIENCE_SOAK_PATH)
    gameplay_progression = load_yaml(GAMEPLAY_PROGRESSION_PATH)
    engagement_fatigue = load_yaml(ENGAGEMENT_FATIGUE_PATH)
    service_responsiveness = load_yaml(SERVICE_RESPONSIVENESS_PATH)
    matchmaking_quality = load_yaml(MATCHMAKING_QUALITY_PATH)
    streak = int(control.get("steady_noop_streak", 0))
    thresholds = {
        "execution": bool(control.get("execution_threshold_ready", False)),
        "operational": bool(control.get("operational_threshold_ready", False)),
        "autonomy": bool(control.get("autonomy_threshold_ready", False)),
        "final": bool(control.get("final_threshold_ready", False)),
    }
    if not thresholds["execution"]:
        return []
    proposals = [
        {
            "artifact_class": "consumer_health_rollup",
            "scope": "minecraft_runtime",
            "reason": "multi-consumer operating surface needs a canonical health rollup",
            "source": "runtime_summary",
            "criteria": {
                "scope_fit": True,
                "authority_fit": True,
                "upgrade_value": thresholds["operational"],
                "exploration_os_compatibility": True,
            },
            "payload": {
                "steady_noop_streak": streak,
                "thresholds": thresholds,
                "consumers": ["lobby", "rpg_world", "dungeons", "boss_world", "events"],
            },
        },
        {
            "artifact_class": "threshold_status_snapshot",
            "scope": "minecraft_runtime",
            "reason": "threshold progression needs a canonical append-only operating record",
            "source": "autonomy_control_state",
            "criteria": {
                "scope_fit": True,
                "authority_fit": True,
                "upgrade_value": True,
                "exploration_os_compatibility": True,
            },
            "payload": {
                "steady_noop_streak": streak,
                "thresholds": thresholds,
                "last_decision_path": control.get("last_decision_path", ""),
            },
        },
    ]
    if thresholds["autonomy"]:
        proposals.append(
            {
                "artifact_class": "stress_soak_comparison_report",
                "scope": "minecraft_runtime",
                "reason": "autonomous operation should preserve a governed comparison between steady state and validation branches",
                "source": "closed_loop_validation",
                "criteria": {
                    "scope_fit": True,
                    "authority_fit": True,
                    "upgrade_value": True,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "steady_noop_streak": streak,
                    "comparison_axes": ["stress", "soak", "recovery", "threshold"],
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "content_quality_profile",
                "scope": "minecraft_runtime",
                "reason": "content quality scoring should become a canonical operating input for replayable promotion decisions",
                "source": "content_governor",
                "criteria": {
                    "scope_fit": int(content.get("generated", 0)) > 0,
                    "authority_fit": thresholds["execution"],
                    "upgrade_value": float(content.get("average_quality_score", 0.0)) > 0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "generated": int(content.get("generated", 0)),
                    "promoted": int(content.get("promoted", 0)),
                    "held": int(content.get("held", 0)),
                    "families": len(content.get("by_type", {})),
                    "average_depth_score": float(content.get("average_depth_score", 0.0)),
                    "average_retention_proxy": float(content.get("average_retention_proxy", 0.0)),
                    "average_quality_score": float(content.get("average_quality_score", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "content_portfolio_strategy",
                "scope": "minecraft_runtime",
                "reason": "portfolio focus and repair priorities should be promoted into the governed operating surface",
                "source": "content_strategy_governor",
                "criteria": {
                    "scope_fit": bool(content_strategy.get("next_focus_csv", "")),
                    "authority_fit": thresholds["autonomy"],
                    "upgrade_value": int(content_strategy.get("recommended_repairs_count", 0)) >= 0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "next_focus_csv": str(content_strategy.get("next_focus_csv", "")),
                    "recommended_repairs_csv": str(content_strategy.get("recommended_repairs_csv", "")),
                    "runtime_queue_avg": float(content_strategy.get("runtime_queue_avg", 0.0)),
                    "runtime_event_join_avg": float(content_strategy.get("runtime_event_join_avg", 0.0)),
                    "runtime_return_player_reward_avg": float(content_strategy.get("runtime_return_player_reward_avg", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "content_volume_profile",
                "scope": "minecraft_runtime",
                "reason": "content volume and spectacle density should be governed as a canonical player-facing completeness input",
                "source": "content_volume_governor",
                "criteria": {
                    "scope_fit": float(content_volume.get("content_volume_score", 0.0)) >= 0.0,
                    "authority_fit": thresholds["autonomy"],
                    "upgrade_value": bool(content_volume.get("content_volume_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "content_volume_score": float(content_volume.get("content_volume_score", 0.0)),
                    "content_volume_state": str(content_volume.get("content_volume_state", "")),
                    "core_family_coverage": int(content_volume.get("core_family_coverage", 0)),
                    "progression_span": int(content_volume.get("progression_span", 0)),
                    "spectacle_density": int(content_volume.get("spectacle_density", 0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "content_soak_report",
                "scope": "minecraft_runtime",
                "reason": "content long-soak state should be governed for promotion and replay decisions",
                "source": "content_soak_governor",
                "criteria": {
                    "scope_fit": bool(content_soak.get("content_soak_state", "")),
                    "authority_fit": thresholds["autonomy"],
                    "upgrade_value": int(content_soak.get("steady_noop_streak", 0)) >= 0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "content_soak_state": str(content_soak.get("content_soak_state", "")),
                    "steady_noop_streak": int(content_soak.get("steady_noop_streak", 0)),
                    "recommended_repairs_count": int(content_soak.get("recommended_repairs_count", 0)),
                    "content_next_focus_csv": str(content_soak.get("content_next_focus_csv", "")),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "gameplay_progression_profile",
                "scope": "minecraft_runtime",
                "reason": "gameplay progression spine should become a governed operating artifact rather than a loose aggregate intuition",
                "source": "gameplay_progression_governor",
                "criteria": {
                    "scope_fit": float(gameplay_progression.get("progression_total_score", 0.0)) >= 0.0,
                    "authority_fit": thresholds["autonomy"],
                    "upgrade_value": bool(gameplay_progression.get("progression_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "progression_total_score": float(gameplay_progression.get("progression_total_score", 0.0)),
                    "progression_state": str(gameplay_progression.get("progression_state", "")),
                    "quest_chain_count": int(gameplay_progression.get("quest_chain_count", 0)),
                    "dungeon_variation_count": int(gameplay_progression.get("dungeon_variation_count", 0)),
                    "season_count": int(gameplay_progression.get("season_count", 0)),
                },
            }
        )
    if thresholds["final"]:
        proposals.append(
            {
                "artifact_class": "control_state_projection",
                "scope": "minecraft_runtime",
                "reason": "final threshold requires a governed projection artifact for future replay and consumer onboarding",
                "source": "threshold_projection",
                "criteria": {
                    "scope_fit": True,
                    "authority_fit": True,
                    "upgrade_value": True,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "steady_noop_streak": streak,
                    "projection": "final_threshold_governed_surface",
                    "constraints": ["exploration", "lineage", "replayability", "append_only_truth"],
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "repo_bundle_profile",
                "scope": "minecraft_runtime",
                "reason": "repo-scale large-bundle status should be governed as canonical operating context",
                "source": "repo_bundle_governor",
                "criteria": {
                    "scope_fit": int(repo_bundle.get("bundle_total", 0)) > 0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": int(repo_bundle.get("bundle_completed", 0)) >= 1,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "bundle_total": int(repo_bundle.get("bundle_total", 0)),
                    "bundle_completed": int(repo_bundle.get("bundle_completed", 0)),
                    "bundle_completion_percent": float(repo_bundle.get("bundle_completion_percent", 0.0)),
                    "governance_bundle_state": str(repo_bundle.get("governance_bundle_state", "")),
                    "autonomy_bundle_state": str(repo_bundle.get("autonomy_bundle_state", "")),
                    "docs_information_architecture_bundle_state": str(repo_bundle.get("docs_information_architecture_bundle_state", "")),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "minecraft_domain_bundle_profile",
                "scope": "minecraft_runtime",
                "reason": "minecraft-scale large-bundle status should be canonical for domain-level promotion and repair reasoning",
                "source": "minecraft_bundle_governor",
                "criteria": {
                    "scope_fit": int(minecraft_bundle.get("bundle_total", 0)) > 0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": int(minecraft_bundle.get("bundle_completed", 0)) >= 1,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "bundle_total": int(minecraft_bundle.get("bundle_total", 0)),
                    "bundle_completed": int(minecraft_bundle.get("bundle_completed", 0)),
                    "bundle_completion_percent": float(minecraft_bundle.get("bundle_completion_percent", 0.0)),
                    "gameplay_progression_bundle_state": str(minecraft_bundle.get("gameplay_progression_bundle_state", "")),
                    "economy_market_bundle_state": str(minecraft_bundle.get("economy_market_bundle_state", "")),
                    "social_liveops_bundle_state": str(minecraft_bundle.get("social_liveops_bundle_state", "")),
                    "anti_cheat_recovery_bundle_state": str(minecraft_bundle.get("anti_cheat_recovery_bundle_state", "")),
                    "governance_autonomy_bundle_state": str(minecraft_bundle.get("governance_autonomy_bundle_state", "")),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "minecraft_domain_strategy",
                "scope": "minecraft_runtime",
                "reason": "minecraft-scale next-focus and repair strategy should be canonical for cross-domain repair reasoning",
                "source": "minecraft_strategy_governor",
                "criteria": {
                    "scope_fit": bool(minecraft_strategy.get("next_focus_csv", "")),
                    "authority_fit": thresholds["final"],
                    "upgrade_value": int(minecraft_strategy.get("recommended_repairs_count", 0)) >= 0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "next_focus_csv": str(minecraft_strategy.get("next_focus_csv", "")),
                    "recommended_repairs_csv": str(minecraft_strategy.get("recommended_repairs_csv", "")),
                    "recommended_repairs_count": int(minecraft_strategy.get("recommended_repairs_count", 0)),
                    "top_focus_domain": str(minecraft_strategy.get("top_focus_domain", "")),
                    "inflation_ratio": float(minecraft_strategy.get("inflation_ratio", 0.0)),
                    "sandbox_cases": int(minecraft_strategy.get("sandbox_cases", 0)),
                    "content_soak_state": str(minecraft_strategy.get("content_soak_state", "")),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "minecraft_domain_soak_report",
                "scope": "minecraft_runtime",
                "reason": "minecraft-scale soak state should be canonical for long-running domain governance",
                "source": "minecraft_soak_governor",
                "criteria": {
                    "scope_fit": bool(minecraft_soak.get("minecraft_soak_state", "")),
                    "authority_fit": thresholds["final"],
                    "upgrade_value": int(minecraft_soak.get("steady_noop_streak", 0)) >= 0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "minecraft_soak_state": str(minecraft_soak.get("minecraft_soak_state", "")),
                    "steady_noop_streak": int(minecraft_soak.get("steady_noop_streak", 0)),
                    "recommended_repairs_count": int(minecraft_soak.get("recommended_repairs_count", 0)),
                    "minecraft_bundle_completion_percent": float(minecraft_soak.get("minecraft_bundle_completion_percent", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "service_responsiveness_profile",
                "scope": "minecraft_runtime",
                "reason": "queue immediacy and service responsiveness should be governed as a canonical player-facing service quality artifact",
                "source": "service_responsiveness_governor",
                "criteria": {
                    "scope_fit": float(service_responsiveness.get("responsiveness_score", 0.0)) >= 0.0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": bool(service_responsiveness.get("responsiveness_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "responsiveness_score": float(service_responsiveness.get("responsiveness_score", 0.0)),
                    "responsiveness_state": str(service_responsiveness.get("responsiveness_state", "")),
                    "queue_immediacy_score": float(service_responsiveness.get("queue_immediacy_score", 0.0)),
                    "latency_confidence": float(service_responsiveness.get("latency_confidence", 0.0)),
                    "density_balance_score": float(service_responsiveness.get("density_balance_score", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "matchmaking_quality_profile",
                "scope": "minecraft_runtime",
                "reason": "matchmaking fairness and routing clarity should be governed as canonical service quality signals",
                "source": "matchmaking_quality_governor",
                "criteria": {
                    "scope_fit": float(matchmaking_quality.get("matchmaking_quality_score", 0.0)) >= 0.0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": bool(matchmaking_quality.get("matchmaking_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "matchmaking_quality_score": float(matchmaking_quality.get("matchmaking_quality_score", 0.0)),
                    "matchmaking_state": str(matchmaking_quality.get("matchmaking_state", "")),
                    "routing_clarity_score": float(matchmaking_quality.get("routing_clarity_score", 0.0)),
                    "queue_fairness_score": float(matchmaking_quality.get("queue_fairness_score", 0.0)),
                    "social_match_score": float(matchmaking_quality.get("social_match_score", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "player_experience_profile",
                "scope": "minecraft_runtime",
                "reason": "player-facing completeness should be governed as an operating artifact rather than a loose narrative estimate",
                "source": "player_experience_governor",
                "criteria": {
                    "scope_fit": float(player_experience.get("estimated_completeness_percent", 0.0)) >= 0.0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": bool(player_experience.get("experience_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "estimated_completeness_percent": float(player_experience.get("estimated_completeness_percent", 0.0)),
                    "experience_state": str(player_experience.get("experience_state", "")),
                    "onboarding_tempo": float(player_experience.get("onboarding_tempo", 0.0)),
                    "reward_tempo": float(player_experience.get("reward_tempo", 0.0)),
                    "social_stickiness": float(player_experience.get("social_stickiness", 0.0)),
                    "replay_pull": float(player_experience.get("replay_pull", 0.0)),
                    "friction_penalty": float(player_experience.get("friction_penalty", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "engagement_fatigue_profile",
                "scope": "minecraft_runtime",
                "reason": "thinness, repetition fatigue, and novelty gap should be governed as a conservative operating surface rather than hidden in narrative review",
                "source": "engagement_fatigue_governor",
                "criteria": {
                    "scope_fit": float(engagement_fatigue.get("fatigue_gap_score", 0.0)) >= 0.0,
                    "authority_fit": thresholds["final"],
                    "upgrade_value": bool(engagement_fatigue.get("fatigue_state", "")),
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "fatigue_gap_score": float(engagement_fatigue.get("fatigue_gap_score", 0.0)),
                    "fatigue_state": str(engagement_fatigue.get("fatigue_state", "")),
                    "thinness_score": float(engagement_fatigue.get("thinness_score", 0.0)),
                    "repetition_score": float(engagement_fatigue.get("repetition_score", 0.0)),
                    "novelty_gap_score": float(engagement_fatigue.get("novelty_gap_score", 0.0)),
                },
            }
        )
        proposals.append(
            {
                "artifact_class": "player_experience_soak_report",
                "scope": "minecraft_runtime",
                "reason": "player-facing completeness should retain a governed long-soak state instead of a point-in-time estimate",
                "source": "player_experience_soak_governor",
                "criteria": {
                    "scope_fit": bool(player_experience_soak.get("player_experience_soak_state", "")),
                    "authority_fit": thresholds["final"],
                    "upgrade_value": float(player_experience_soak.get("estimated_completeness_percent", 0.0)) >= 0.0,
                    "exploration_os_compatibility": True,
                },
                "payload": {
                    "player_experience_soak_state": str(player_experience_soak.get("player_experience_soak_state", "")),
                    "estimated_completeness_percent": float(player_experience_soak.get("estimated_completeness_percent", 0.0)),
                    "experience_state": str(player_experience_soak.get("experience_state", "")),
                    "combined_recommended_repairs_count": int(player_experience_soak.get("combined_recommended_repairs_count", 0)),
                },
            }
        )
    return proposals


def main() -> int:
    control = load_yaml(CONTROL_STATE)
    created_at = now_iso()
    proposals = canonical_candidates(control)
    accepted = 0
    proposed = 0
    canonical_registry: list[str] = []

    for candidate in proposals:
        key = proposal_key(candidate["scope"], candidate["artifact_class"])
        proposal_id = "proposal-" + uuid.uuid4().hex[:12]
        criteria = candidate["criteria"]
        verdict = "accepted" if all(criteria.values()) else "rejected"
        proposed += 1
        proposal_payload = {
            "proposal_id": proposal_id,
            "created_at": created_at,
            "scope": candidate["scope"],
            "artifact_class": candidate["artifact_class"],
            "reason": candidate["reason"],
            "source": candidate["source"],
            "criteria": criteria,
            "verdict": verdict,
            "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
            "payload": candidate["payload"],
        }
        signature = hashlib.sha256(json.dumps(proposal_payload, sort_keys=True).encode("utf-8")).hexdigest()
        proposal_payload["signature"] = signature
        write_yaml(PROPOSAL_DIR / f"{created_at.replace(':', '').replace('-', '')}_{proposal_id}.yml", proposal_payload)
        append_jsonl(VERDICT_LOG, {"created_at": created_at, "proposal_id": proposal_id, "artifact_class": candidate["artifact_class"], "verdict": verdict, "signature": signature})

        if verdict != "accepted":
            continue
        accepted += 1
        canonical_id = "canonical-" + uuid.uuid4().hex[:12]
        canonical_payload = {
            "canonical_id": canonical_id,
            "created_at": created_at,
            "scope": candidate["scope"],
            "artifact_class": candidate["artifact_class"],
            "proposal_id": proposal_id,
            "lineage": {
                "control_state_signature": hashlib.sha256(json.dumps(control, sort_keys=True).encode("utf-8")).hexdigest(),
                "proposal_signature": signature,
            },
            "governance": {
                "append_only_truth": True,
                "replayability": True,
                "lineage_preserved": True,
                "exploration_os_compatibility": True,
            },
            "payload": candidate["payload"],
        }
        write_yaml(CANONICAL_DIR / f"{created_at.replace(':', '').replace('-', '')}_{canonical_id}.yml", canonical_payload)
        append_jsonl(CANONICAL_LOG, {"created_at": created_at, "canonical_id": canonical_id, "artifact_class": candidate["artifact_class"], "proposal_id": proposal_id})
        canonical_registry.append(key)

    summary = {
        "created_at": created_at,
        "proposed": proposed,
        "accepted": accepted,
        "canonical_classes": len(canonical_registry),
        "canonical_registry": canonical_registry,
        "thresholds": {
            "execution": bool(control.get("execution_threshold_ready", False)),
            "operational": bool(control.get("operational_threshold_ready", False)),
            "autonomy": bool(control.get("autonomy_threshold_ready", False)),
            "final": bool(control.get("final_threshold_ready", False)),
        },
    }
    write_yaml(SUMMARY_PATH, summary)
    print("ARTIFACT_GOVERNOR")
    print(f"PROPOSED={proposed}")
    print(f"ACCEPTED={accepted}")
    print(f"CANONICAL_CLASSES={len(canonical_registry)}")
    for key in canonical_registry:
        print(f"CANONICAL={key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

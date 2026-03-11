#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import json
import yaml

from final_threshold_eval import load_eval_bundle


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
CONTROL_STATE = RUNTIME / "autonomy" / "control" / "state.yml"
ARTIFACT_GOVERNOR_SUMMARY = RUNTIME / "autonomy" / "artifact_governor_summary.yml"
CONFORMANCE_AUDIT = RUNTIME / "audit" / "COVERAGE_AUDIT.yml"
CONTENT_GOVERNOR_SUMMARY = RUNTIME / "autonomy" / "content_governor_summary.yml"
ECONOMY_GOVERNOR_SUMMARY = RUNTIME / "autonomy" / "economy_governor_summary.yml"
ANTI_CHEAT_GOVERNOR_SUMMARY = RUNTIME / "autonomy" / "anti_cheat_governor_summary.yml"
LIVEOPS_GOVERNOR_SUMMARY = RUNTIME / "autonomy" / "liveops_governor_summary.yml"
FINAL_THRESHOLD_EVAL = RUNTIME / "autonomy" / "final_threshold_eval.json"
MATERIAL_INVENTORY_SUMMARY = RUNTIME / "autonomy" / "material_inventory_summary.yml"
RUNTIME_PARTITION_SUMMARY = RUNTIME / "autonomy" / "runtime_partition_summary.yml"
CONTENT_STRATEGY_SUMMARY = RUNTIME / "autonomy" / "content_strategy_summary.yml"
CONTENT_SOAK_SUMMARY = RUNTIME / "autonomy" / "content_soak_summary.yml"
CONTENT_VOLUME_SUMMARY = RUNTIME / "autonomy" / "content_volume_summary.yml"
CONTENT_BUNDLE_SUMMARY = RUNTIME / "autonomy" / "content_bundle_summary.yml"
REPO_BUNDLE_SUMMARY = RUNTIME / "autonomy" / "repo_bundle_summary.yml"
MINECRAFT_BUNDLE_SUMMARY = RUNTIME / "autonomy" / "minecraft_bundle_summary.yml"
MINECRAFT_STRATEGY_SUMMARY = RUNTIME / "autonomy" / "minecraft_strategy_summary.yml"
MINECRAFT_SOAK_SUMMARY = RUNTIME / "autonomy" / "minecraft_soak_summary.yml"
PLAYER_EXPERIENCE_SUMMARY = RUNTIME / "autonomy" / "player_experience_summary.yml"
PLAYER_EXPERIENCE_SOAK_SUMMARY = RUNTIME / "autonomy" / "player_experience_soak_summary.yml"
GAMEPLAY_PROGRESSION_SUMMARY = RUNTIME / "autonomy" / "gameplay_progression_summary.yml"
ENGAGEMENT_FATIGUE_SUMMARY = RUNTIME / "autonomy" / "engagement_fatigue_summary.yml"


def load_yaml(path: Path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def summarize_status() -> tuple[dict[str, int], list[str]]:
    totals = {
        "session_authority_conflicts": 0,
        "session_split_brain": 0,
        "transfer_failures": 0,
        "transfer_quarantines": 0,
        "reconciliation_mismatches": 0,
        "guild_drift": 0,
        "item_quarantine": 0,
        "exploit_incidents": 0,
        "instance_leaks": 0,
        "experiment_anomalies": 0,
        "knowledge_records": 0,
        "dungeons_started": 0,
        "dungeons_completed": 0,
        "bosses_killed": 0,
        "events_started": 0,
        "event_joins": 0,
        "rewards_distributed": 0,
        "economy_earn": 0,
        "economy_spend": 0,
        "gear_drop": 0,
        "gear_upgrade": 0,
        "progression_level_up": 0,
        "instance_spawn": 0,
        "instance_shutdown": 0,
        "queue_size": 0,
        "player_density": 0,
        "routing_latency_ms": 0,
        "exploit_flag": 0,
        "adaptive_adjustment": 0,
        "difficulty_change": 0,
        "reward_adjustment": 0,
        "event_frequency_change": 0,
        "matchmaking_adjustment": 0,
        "guild_created": 0,
        "guild_joined": 0,
        "prestige_gain": 0,
        "return_player_reward": 0,
        "streak_progress": 0,
        "rivalry_created": 0,
        "rivalry_match": 0,
        "rivalry_reward": 0,
    }
    details: list[str] = []

    for status_path in sorted((RUNTIME / "status").glob("*.yml")):
        status = load_yaml(status_path)
        server = status_path.stem
        session = status.get("session_authority_service", {}) or {}
        transfer = status.get("deterministic_transfer_service", {}) or {}
        knowledge = status.get("runtime_knowledge_index", {}) or {}

        session_conflicts = int(session.get("session_ownership_conflicts", 0))
        split_brain = int(session.get("split_brain_detections", 0))
        transfer_failures = int(transfer.get("lease_verification_failures", 0)) + int(status.get("transfer_fence_rejects", 0))
        transfer_quarantines = int(transfer.get("quarantines", 0))
        reconciliation = int(status.get("reconciliation_mismatches", 0))
        guild_drift = int(status.get("guild_value_drift", 0))
        item_quarantine = int(status.get("item_ownership_conflicts", 0)) + int(status.get("economy_item_authority_plane", {}).get("quarantined_items", 0))
        exploit_incidents = int(status.get("exploit_forensics_plane", {}).get("incident_total", 0))
        instance_leaks = int(status.get("orphan_instances", 0)) + int(status.get("instance_cleanup_failures", 0))
        experiment_anomalies = int(status.get("experiment_registry", {}).get("rollbacks", 0)) + int(status.get("policy_registry", {}).get("rollbacks", 0))
        knowledge_records = int(knowledge.get("records", 0))
        dungeons_started = int(status.get("dungeon_started", 0))
        dungeons_completed = int(status.get("dungeon_completed", 0))
        bosses_killed = int(status.get("boss_killed", 0))
        events_started = int(status.get("event_started", 0))
        event_joins = int(status.get("event_join_count", 0))
        rewards_distributed = int(status.get("reward_distributed", 0))
        economy_earn = int(status.get("economy_earn", 0))
        economy_spend = int(status.get("economy_spend", 0))
        gear_drop = int(status.get("gear_drop", 0))
        gear_upgrade = int(status.get("gear_upgrade", 0))
        progression_level_up = int(status.get("progression_level_up", 0))
        instance_spawn = int(status.get("instance_spawn", 0))
        instance_shutdown = int(status.get("instance_shutdown", 0))
        queue_size = int(status.get("queue_size", 0))
        player_density = int(status.get("player_density", 0))
        routing_latency_ms = int(float(status.get("network_routing_latency_ms", 0)))
        exploit_flag = int(status.get("exploit_flag", 0))
        adaptive_adjustment = int(status.get("adaptive_adjustment", 0))
        difficulty_change = int(status.get("difficulty_change", 0))
        reward_adjustment = int(status.get("reward_adjustment", 0))
        event_frequency_change = int(status.get("event_frequency_change", 0))
        matchmaking_adjustment = int(status.get("matchmaking_adjustment", 0))
        guild_created = int(status.get("guild_created", 0))
        guild_joined = int(status.get("guild_joined", 0))
        prestige_gain = int(status.get("prestige_gain", 0))
        return_player_reward = int(status.get("return_player_reward", 0))
        streak_progress = int(status.get("streak_progress", 0))
        rivalry_created = int(status.get("rivalry_created", 0))
        rivalry_match = int(status.get("rivalry_match", 0))
        rivalry_reward = int(status.get("rivalry_reward", 0))

        totals["session_authority_conflicts"] += session_conflicts
        totals["session_split_brain"] += split_brain
        totals["transfer_failures"] += transfer_failures
        totals["transfer_quarantines"] += transfer_quarantines
        totals["reconciliation_mismatches"] += reconciliation
        totals["guild_drift"] += guild_drift
        totals["item_quarantine"] += item_quarantine
        totals["exploit_incidents"] += exploit_incidents
        totals["instance_leaks"] += instance_leaks
        totals["experiment_anomalies"] += experiment_anomalies
        totals["knowledge_records"] += knowledge_records
        totals["dungeons_started"] += dungeons_started
        totals["dungeons_completed"] += dungeons_completed
        totals["bosses_killed"] += bosses_killed
        totals["events_started"] += events_started
        totals["event_joins"] += event_joins
        totals["rewards_distributed"] += rewards_distributed
        totals["economy_earn"] += economy_earn
        totals["economy_spend"] += economy_spend
        totals["gear_drop"] += gear_drop
        totals["gear_upgrade"] += gear_upgrade
        totals["progression_level_up"] += progression_level_up
        totals["instance_spawn"] += instance_spawn
        totals["instance_shutdown"] += instance_shutdown
        totals["queue_size"] += queue_size
        totals["player_density"] += player_density
        totals["routing_latency_ms"] += routing_latency_ms
        totals["exploit_flag"] += exploit_flag
        totals["adaptive_adjustment"] += adaptive_adjustment
        totals["difficulty_change"] += difficulty_change
        totals["reward_adjustment"] += reward_adjustment
        totals["event_frequency_change"] += event_frequency_change
        totals["matchmaking_adjustment"] += matchmaking_adjustment
        totals["guild_created"] += guild_created
        totals["guild_joined"] += guild_joined
        totals["prestige_gain"] += prestige_gain
        totals["return_player_reward"] += return_player_reward
        totals["streak_progress"] += streak_progress
        totals["rivalry_created"] += rivalry_created
        totals["rivalry_match"] += rivalry_match
        totals["rivalry_reward"] += rivalry_reward

        details.append(
            f"{server}: session_conflicts={session_conflicts} split_brain={split_brain} "
            f"transfer_failures={transfer_failures} transfer_quarantines={transfer_quarantines} "
            f"reconciliation={reconciliation} guild_drift={guild_drift} item_quarantine={item_quarantine} "
            f"exploit_incidents={exploit_incidents} instance_leaks={instance_leaks} "
            f"experiment_anomalies={experiment_anomalies} knowledge_records={knowledge_records} "
            f"dungeons_started={dungeons_started} dungeons_completed={dungeons_completed} "
            f"bosses_killed={bosses_killed} events_started={events_started} event_joins={event_joins} "
            f"rewards_distributed={rewards_distributed} economy_earn={economy_earn} economy_spend={economy_spend} "
            f"gear_drop={gear_drop} gear_upgrade={gear_upgrade} progression_level_up={progression_level_up} "
            f"instance_spawn={instance_spawn} instance_shutdown={instance_shutdown} queue_size={queue_size} "
            f"player_density={player_density} routing_latency_ms={routing_latency_ms} exploit_flag={exploit_flag} "
            f"adaptive_adjustment={adaptive_adjustment} difficulty_change={difficulty_change} "
            f"reward_adjustment={reward_adjustment} event_frequency_change={event_frequency_change} "
            f"matchmaking_adjustment={matchmaking_adjustment} guild_created={guild_created} "
            f"guild_joined={guild_joined} prestige_gain={prestige_gain} return_player_reward={return_player_reward} "
            f"streak_progress={streak_progress} rivalry_created={rivalry_created} rivalry_match={rivalry_match} rivalry_reward={rivalry_reward}"
        )

    return totals, details


def main() -> int:
    totals, details = summarize_status()
    autonomy_decisions = len(list((RUNTIME / "autonomy" / "decisions").glob("*.yml")))
    control = load_yaml(CONTROL_STATE)
    artifact_governor = load_yaml(ARTIFACT_GOVERNOR_SUMMARY)
    conformance = load_yaml(CONFORMANCE_AUDIT)
    content_governor = load_yaml(CONTENT_GOVERNOR_SUMMARY)
    economy_governor = load_yaml(ECONOMY_GOVERNOR_SUMMARY)
    anti_cheat_governor = load_yaml(ANTI_CHEAT_GOVERNOR_SUMMARY)
    liveops_governor = load_yaml(LIVEOPS_GOVERNOR_SUMMARY)
    final_threshold_eval = load_eval_bundle(refresh_if_stale=True)
    material_inventory = load_yaml(MATERIAL_INVENTORY_SUMMARY)
    runtime_partition = load_yaml(RUNTIME_PARTITION_SUMMARY)
    content_strategy = load_yaml(CONTENT_STRATEGY_SUMMARY)
    content_soak = load_yaml(CONTENT_SOAK_SUMMARY)
    content_volume = load_yaml(CONTENT_VOLUME_SUMMARY)
    content_bundle = load_yaml(CONTENT_BUNDLE_SUMMARY)
    repo_bundle = load_yaml(REPO_BUNDLE_SUMMARY)
    minecraft_bundle = load_yaml(MINECRAFT_BUNDLE_SUMMARY)
    minecraft_strategy = load_yaml(MINECRAFT_STRATEGY_SUMMARY)
    minecraft_soak = load_yaml(MINECRAFT_SOAK_SUMMARY)
    player_experience = load_yaml(PLAYER_EXPERIENCE_SUMMARY)
    player_experience_soak = load_yaml(PLAYER_EXPERIENCE_SOAK_SUMMARY)
    gameplay_progression = load_yaml(GAMEPLAY_PROGRESSION_SUMMARY)
    engagement_fatigue = load_yaml(ENGAGEMENT_FATIGUE_SUMMARY)
    print("RUNTIME_SUMMARY")
    print(f"AUTONOMY_DECISIONS={autonomy_decisions}")
    print(f"AUTONOMY_LAST_MODE={control.get('last_mode', 'unknown')}")
    print(f"AUTONOMY_LAST_REGIME={control.get('last_regime', 'unknown')}")
    print(f"AUTONOMY_ACTIVE_SOAK={control.get('active_soak', {}).get('decision_id', '')}")
    print(f"AUTONOMY_LAST_SOAK_RESOLUTION={control.get('last_soak_resolution', {}).get('resolution', '')}")
    print(f"AUTONOMY_EXECUTION_THRESHOLD_READY={1 if control.get('execution_threshold_ready', False) else 0}")
    print(f"AUTONOMY_OPERATIONAL_THRESHOLD_READY={1 if control.get('operational_threshold_ready', False) else 0}")
    print(f"AUTONOMY_AUTONOMY_THRESHOLD_READY={1 if control.get('autonomy_threshold_ready', False) else 0}")
    print(f"AUTONOMY_STEADY_NOOP_STREAK={int(control.get('steady_noop_streak', 0))}")
    print(f"AUTONOMY_FINAL_THRESHOLD_READY={1 if control.get('final_threshold_ready', False) else 0}")
    print(f"ARTIFACT_GOVERNOR_PROPOSED={int(artifact_governor.get('proposed', 0))}")
    print(f"ARTIFACT_GOVERNOR_ACCEPTED={int(artifact_governor.get('accepted', 0))}")
    print(f"ARTIFACT_GOVERNOR_CANONICAL_CLASSES={len(artifact_governor.get('canonical_registry', []))}")
    print(f"METAOS_CONFORMANCE_GAPS={len(conformance.get('gaps', []))}")
    print(f"CONTENT_GENERATED={int(content_governor.get('generated', 0))}")
    print(f"CONTENT_PROMOTED={int(content_governor.get('promoted', 0))}")
    print(f"CONTENT_HELD={int(content_governor.get('held', 0))}")
    print(f"CONTENT_FAMILIES={len(content_governor.get('by_type', {}))}")
    print(f"CONTENT_AVERAGE_DEPTH_SCORE={content_governor.get('average_depth_score', 0)}")
    print(f"CONTENT_AVERAGE_RETENTION_PROXY={content_governor.get('average_retention_proxy', 0)}")
    print(f"CONTENT_AVERAGE_QUALITY_SCORE={content_governor.get('average_quality_score', 0)}")
    print(f"CONTENT_FIRST_LOOP_COVERAGE_SCORE={content_governor.get('first_loop_coverage_score', 0)}")
    print(f"CONTENT_SOCIAL_LOOP_DENSITY={content_governor.get('social_loop_density', 0)}")
    print(f"CONTENT_REPLAYABLE_LOOP_SCORE={content_governor.get('replayable_loop_score', 0)}")
    print(f"CONTENT_ADVANCED_LOOP_STRENGTH={content_governor.get('advanced_loop_strength', 0)}")
    print(f"CONTENT_PRESTIGE_LOOP_STRENGTH={content_governor.get('prestige_loop_strength', 0)}")
    print(f"CONTENT_SOCIAL_PERSISTENCE_STRENGTH={content_governor.get('social_persistence_strength', 0)}")
    print(f"CONTENT_STARTER_REWARD_STRENGTH={content_governor.get('starter_reward_strength', 0)}")
    print(f"CONTENT_RIVALRY_REWARD_PULL={content_governor.get('rivalry_reward_pull', 0)}")
    print(f"CONTENT_VOLUME_SCORE={content_volume.get('content_volume_score', 0)}")
    print(f"CONTENT_VOLUME_STATE={content_volume.get('content_volume_state', '')}")
    print(f"CONTENT_NEXT_FOCUS={content_strategy.get('next_focus_csv', '')}")
    print(f"CONTENT_RECOMMENDED_REPAIRS={int(content_strategy.get('recommended_repairs_count', 0))}")
    print(f"CONTENT_RUNTIME_QUEUE_AVG={content_strategy.get('runtime_queue_avg', 0)}")
    print(f"CONTENT_RUNTIME_EVENT_JOIN_AVG={content_strategy.get('runtime_event_join_avg', 0)}")
    print(f"CONTENT_RUNTIME_RETURN_PLAYER_REWARD_AVG={content_strategy.get('runtime_return_player_reward_avg', 0)}")
    print(f"GAMEPLAY_PROGRESSION_TOTAL_SCORE={gameplay_progression.get('progression_total_score', 0)}")
    print(f"GAMEPLAY_PROGRESSION_STATE={gameplay_progression.get('progression_state', '')}")
    print(f"ENGAGEMENT_FATIGUE_GAP_SCORE={engagement_fatigue.get('fatigue_gap_score', 0)}")
    print(f"ENGAGEMENT_FATIGUE_STATE={engagement_fatigue.get('fatigue_state', '')}")
    print(f"CONTENT_SOAK_STATE={content_soak.get('content_soak_state', '')}")
    print(f"CONTENT_SOAK_RECOMMENDED_REPAIRS={int(content_soak.get('recommended_repairs_count', 0))}")
    print(f"CONTENT_BUNDLE_COMPLETED={int(content_bundle.get('bundle_completed', 0))}")
    print(f"CONTENT_BUNDLE_TOTAL={int(content_bundle.get('bundle_total', 0))}")
    print(f"CONTENT_BUNDLE_COMPLETION_PERCENT={content_bundle.get('bundle_completion_percent', 0)}")
    print(f"CONTENT_PLAYER_FACING_DEPTH_STATE={content_bundle.get('player_facing_depth_state', '')}")
    print(f"REPO_BUNDLE_COMPLETED={int(repo_bundle.get('bundle_completed', 0))}")
    print(f"REPO_BUNDLE_TOTAL={int(repo_bundle.get('bundle_total', 0))}")
    print(f"REPO_BUNDLE_COMPLETION_PERCENT={repo_bundle.get('bundle_completion_percent', 0)}")
    print(f"MINECRAFT_BUNDLE_COMPLETED={int(minecraft_bundle.get('bundle_completed', 0))}")
    print(f"MINECRAFT_BUNDLE_TOTAL={int(minecraft_bundle.get('bundle_total', 0))}")
    print(f"MINECRAFT_BUNDLE_COMPLETION_PERCENT={minecraft_bundle.get('bundle_completion_percent', 0)}")
    print(f"MINECRAFT_PLAYER_EXPERIENCE_BUNDLE_STATE={minecraft_bundle.get('player_experience_bundle_state', '')}")
    print(f"MINECRAFT_NEXT_FOCUS={minecraft_strategy.get('next_focus_csv', '')}")
    print(f"MINECRAFT_RECOMMENDED_REPAIRS={int(minecraft_strategy.get('recommended_repairs_count', 0))}")
    print(f"MINECRAFT_SOAK_STATE={minecraft_soak.get('minecraft_soak_state', '')}")
    print(f"PLAYER_EXPERIENCE_PERCENT={player_experience.get('estimated_completeness_percent', 0)}")
    print(f"PLAYER_EXPERIENCE_STATE={player_experience.get('experience_state', '')}")
    print(f"PLAYER_EXPERIENCE_FIRST_SESSION_STRENGTH={player_experience.get('first_session_strength', 0)}")
    print(f"PLAYER_EXPERIENCE_TRUST_PULL={player_experience.get('trust_pull', 0)}")
    print(f"PLAYER_EXPERIENCE_VOLUME_PULL={player_experience.get('volume_pull', 0)}")
    print(f"PLAYER_EXPERIENCE_SOAK_STATE={player_experience_soak.get('player_experience_soak_state', '')}")
    print(f"ECONOMY_ACTION={economy_governor.get('action', '')}")
    print(f"ECONOMY_INFLATION_RATIO={economy_governor.get('inflation_ratio', 0)}")
    print(f"ANTI_CHEAT_SANDBOX_CASES={int(anti_cheat_governor.get('sandbox_cases', 0))}")
    print(f"ANTI_CHEAT_MODE={anti_cheat_governor.get('mode', '')}")
    print(f"ANTI_CHEAT_PROGRESSION_PROTECTION_SCORE={anti_cheat_governor.get('progression_protection_score', 0)}")
    print(f"LIVEOPS_PROMOTED_ACTIONS={int(liveops_governor.get('promoted_actions', 0))}")
    print(f"LIVEOPS_HELD_ACTIONS={int(liveops_governor.get('held_actions', 0))}")
    print(f"LIVEOPS_BOOST_REENTRY={1 if liveops_governor.get('boost_reentry', False) else 0}")
    print(f"LIVEOPS_SUSTAIN_SOCIAL={1 if liveops_governor.get('sustain_social', False) else 0}")
    print(f"LIVEOPS_BOOST_NOVELTY={1 if liveops_governor.get('boost_novelty', False) else 0}")
    print(f"LIVEOPS_CADENCE_DIVERSITY_SCORE={liveops_governor.get('cadence_diversity_score', 0)}")
    print(f"MATERIAL_TOTAL_FILES={int(material_inventory.get('total_files', 0))}")
    print(f"MATERIAL_CANONICAL_SOURCE_FILES={int(material_inventory.get('canonical_source_files', 0))}")
    print(f"MATERIAL_APPEND_ONLY_RUNTIME_TRUTH_FILES={int(material_inventory.get('append_only_runtime_truth_files', 0))}")
    print(f"RUNTIME_PARTITION_FILES={int(runtime_partition.get('runtime_files', 0))}")
    print(f"RUNTIME_VOLATILE_FILES={int(runtime_partition.get('volatile_runtime_files', 0))}")
    print(f"RUNTIME_CANONICAL_SNAPSHOT_FILES={int(runtime_partition.get('canonical_snapshot_files', 0))}")
    print(f"RUNTIME_ARCHIVE_CANDIDATE_FILES={int(runtime_partition.get('archive_candidate_files', 0))}")
    print(f"FINAL_THRESHOLD_BUNDLE_READY={1 if final_threshold_eval.get('final_threshold_ready', False) else 0}")
    print(f"FINAL_THRESHOLD_BUNDLE_FAILED_CRITERIA={len(final_threshold_eval.get('failed_criteria', []))}")
    print(f"FINAL_THRESHOLD_BUNDLE_HUMAN_LIFT={final_threshold_eval.get('quality_lift_if_human_intervenes', 0)}")
    print(f"SESSION_AUTHORITY_CONFLICTS={totals['session_authority_conflicts']}")
    print(f"SESSION_SPLIT_BRAIN={totals['session_split_brain']}")
    print(f"TRANSFER_FAILURES={totals['transfer_failures']}")
    print(f"TRANSFER_QUARANTINES={totals['transfer_quarantines']}")
    print(f"RECONCILIATION_MISMATCHES={totals['reconciliation_mismatches']}")
    print(f"GUILD_DRIFT={totals['guild_drift']}")
    print(f"ITEM_QUARANTINE={totals['item_quarantine']}")
    print(f"EXPLOIT_INCIDENTS={totals['exploit_incidents']}")
    print(f"INSTANCE_LEAKS={totals['instance_leaks']}")
    print(f"EXPERIMENT_ANOMALIES={totals['experiment_anomalies']}")
    print(f"KNOWLEDGE_RECORDS={totals['knowledge_records']}")
    print(f"DUNGEONS_STARTED={totals['dungeons_started']}")
    print(f"DUNGEONS_COMPLETED={totals['dungeons_completed']}")
    print(f"BOSSES_KILLED={totals['bosses_killed']}")
    print(f"EVENTS_STARTED={totals['events_started']}")
    print(f"EVENT_JOINS={totals['event_joins']}")
    print(f"REWARDS_DISTRIBUTED={totals['rewards_distributed']}")
    print(f"ECONOMY_EARN={totals['economy_earn']}")
    print(f"ECONOMY_SPEND={totals['economy_spend']}")
    print(f"GEAR_DROP={totals['gear_drop']}")
    print(f"GEAR_UPGRADE={totals['gear_upgrade']}")
    print(f"PROGRESSION_LEVEL_UP={totals['progression_level_up']}")
    print(f"INSTANCE_SPAWN={totals['instance_spawn']}")
    print(f"INSTANCE_SHUTDOWN={totals['instance_shutdown']}")
    print(f"QUEUE_SIZE={totals['queue_size']}")
    print(f"PLAYER_DENSITY={totals['player_density']}")
    print(f"ROUTING_LATENCY_MS={totals['routing_latency_ms']}")
    print(f"EXPLOIT_FLAG={totals['exploit_flag']}")
    print(f"ADAPTIVE_ADJUSTMENT={totals['adaptive_adjustment']}")
    print(f"DIFFICULTY_CHANGE={totals['difficulty_change']}")
    print(f"REWARD_ADJUSTMENT={totals['reward_adjustment']}")
    print(f"EVENT_FREQUENCY_CHANGE={totals['event_frequency_change']}")
    print(f"MATCHMAKING_ADJUSTMENT={totals['matchmaking_adjustment']}")
    print(f"GUILD_CREATED={totals['guild_created']}")
    print(f"GUILD_JOINED={totals['guild_joined']}")
    print(f"PRESTIGE_GAIN={totals['prestige_gain']}")
    print(f"RETURN_PLAYER_REWARD={totals['return_player_reward']}")
    print(f"STREAK_PROGRESS={totals['streak_progress']}")
    print(f"RIVALRY_CREATED={totals['rivalry_created']}")
    print(f"RIVALRY_MATCH={totals['rivalry_match']}")
    print(f"RIVALRY_REWARD={totals['rivalry_reward']}")
    for detail in details:
        print(detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

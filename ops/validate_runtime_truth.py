#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"
CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    network = load(CONFIG / "network.yml")
    persistence = load(CONFIG / "persistence.yml")
    economy = load(CONFIG / "economy.yml")
    pressure = load(CONFIG / "pressure.yml")
    autonomy = load(CONFIG / "autonomy.yml")
    experiments = load(CONFIG / "experiments.yml")
    governance = load(CONFIG / "governance.yml")
    lobby = load(CONFIG / "lobby.yml")
    genres = load(CONFIG / "genres.yml")
    dungeon_templates = load(CONFIG / "dungeon_templates.yml")
    boss_behaviors = load(CONFIG / "boss_behaviors.yml")
    event_scheduler = load(CONFIG / "event_scheduler.yml")
    reward_pools = load(CONFIG / "reward_pools.yml")
    gear_tiers = load(CONFIG / "gear_tiers.yml")
    runtime_monitor = load(CONFIG / "runtime_monitor.yml")
    adaptive_rules = load(CONFIG / "adaptive_rules.yml")
    guilds_config = load(CONFIG / "guilds.yml")
    prestige = load(CONFIG / "prestige.yml")
    streaks = load(CONFIG / "streaks.yml")
    service_source = (CORE / "RpgNetworkService.java").read_text(encoding="utf-8")
    adaptive_source = (CORE / "TelemetryAdaptiveEngine.java").read_text(encoding="utf-8")
    content_source = (CORE / "ContentEngine.java").read_text(encoding="utf-8")
    session_source = (CORE / "SessionAuthorityService.java").read_text(encoding="utf-8")
    transfer_source = (CORE / "DeterministicTransferService.java").read_text(encoding="utf-8")
    artifact_source = (CORE / "GameplayArtifactRegistry.java").read_text(encoding="utf-8")
    governance_source = (CORE / "GovernancePolicyRegistry.java").read_text(encoding="utf-8")
    experiment_registry_source = (CORE / "ExperimentRegistry.java").read_text(encoding="utf-8")
    policy_registry_source = (CORE / "PolicyRegistry.java").read_text(encoding="utf-8")
    pressure_source = (CORE / "PressureControlPlane.java").read_text(encoding="utf-8")
    knowledge_source = (CORE / "RuntimeKnowledgeIndex.java").read_text(encoding="utf-8")
    lobby_source = (CORE / "LobbyInteractionController.java").read_text(encoding="utf-8")
    genre_source = (CORE / "GenreRegistry.java").read_text(encoding="utf-8")
    party_source = (CORE / "PartyService.java").read_text(encoding="utf-8")

    errors: list[str] = []

    if network["data_flow"]["live_session_state"] != "local_authoritative_lease_registry":
        errors.append("session_authority_claim_mismatch")
    if persistence["redis"]["required_for_session_authority"] is not False:
        errors.append("redis_authority_fiction_present")

    combined = "\n".join((session_source, transfer_source, artifact_source, governance_source, experiment_registry_source, policy_registry_source, pressure_source, knowledge_source, lobby_source, genre_source, party_source, service_source, adaptive_source, content_source))
    for marker in (
        "REGISTERED", "LEASED", "RECONNECT_HELD", "TRANSFERRING", "ACTIVE", "INVALIDATED", "EXPIRED",
        "INITIATED", "FREEZING", "PERSISTING", "ACTIVATING", "FAILED", "ROLLED_BACK",
        "LOOT_TABLE_VARIANT", "EXPLOIT_SIGNATURE", "RECOVERY_ACTION", "EXPERIMENT_RESULT", "GOVERNANCE_DECISION",
        "spawn_regulation", "reward_idempotency", "experiment_admission", "onboarding_reward", "LobbyRoute", "Navigator Compass", "GenreDefinition", "Party(",
        "PressureSnapshot", "KnowledgeRecord", "DungeonTemplate", "BossBehavior", "ScheduledEvent", "RewardPool", "composeRewardPool", "pollLobbyContentBroadcasts", "mastery_points", "normalizedTier", "progressionSummary", "craftGear", "repairGear", "runOperationsBrain", "quarantineInstance", "shouldQueueJoin", "forceEventStart", "operationsStatus", "TelemetryAdaptiveEngine", "DUNGEON_COMPLETION_TIME", "PLAYER_DEATH_RATE", "EVENT_JOIN_RATE", "QUEUE_TIME", "PLAYER_CHURN_SIGNAL", "recomputeAdaptiveGameplay", "adaptive_adjustment", "difficulty_change", "reward_adjustment", "event_frequency_change", "matchmaking_adjustment", "guild_created", "prestige_gain", "return_player_reward", "streak_progress", "rivalry_created", "rivalry_match", "rivalry_reward", "createGuild", "sendGuildChat", "grantReturnRewardIfEligible", "recordRivalryEncounter",
    ):
        if marker not in combined:
            errors.append(f"missing_marker:{marker}")

    for marker in ("session_authority_service", "deterministic_transfer_service", "gameplay_artifact_registry", "governance_policy_registry", "experiment_registry", "policy_registry", "runtime_knowledge_index", "pressure_control_plane", "genre_registry", "party_service"):
        if marker not in service_source:
            errors.append(f"status_export_missing:{marker}")

    if network["data_flow"].get("knowledge_index") != "runtime_data/knowledge":
        errors.append("knowledge_index_path_mismatch")
    if network["data_flow"].get("pressure_control") != "runtime_data/status":
        errors.append("pressure_control_path_mismatch")
    if not autonomy.get("loop", {}).get("enabled", False):
        errors.append("autonomy_loop_disabled")
    if "parameters" not in autonomy or not autonomy["parameters"]:
        errors.append("autonomy_parameters_missing")
    if not pressure["controls"]["noncritical_spawn_suppression"]:
        errors.append("pressure_noncritical_spawn_suppression_disabled")
    if not experiments["operations"]["attach_experiment_ids_to_mutations"]:
        errors.append("experiment_mutation_attribution_disabled")
    if not governance["operations"]["replay_attribution_required"]:
        errors.append("governance_replay_attribution_disabled")
    for required_route in ("start_adventure", "quick_match", "rotating_event", "explore_hub"):
        if required_route not in lobby["routes"]:
            errors.append(f"lobby_route_missing:{required_route}")
    for required_genre in ("lobby", "rpg", "minigame", "event", "dungeon"):
        if required_genre not in genres["genre_registry"]:
            errors.append(f"genre_missing:{required_genre}")
    if not dungeon_templates.get("templates"):
        errors.append("content_engine_missing_dungeon_templates")
    if not boss_behaviors.get("behaviors"):
        errors.append("content_engine_missing_boss_behaviors")
    if not event_scheduler.get("events"):
        errors.append("content_engine_missing_scheduled_events")
    if not reward_pools.get("pools"):
        errors.append("content_engine_missing_reward_pools")
    if not gear_tiers.get("tiers"):
        errors.append("economy_missing_gear_tiers")
    if not runtime_monitor.get("health_thresholds"):
        errors.append("ops_missing_runtime_monitor")
    for required_section in ("telemetry", "difficulty", "rewards", "events", "matchmaking", "churn", "safety"):
        if required_section not in adaptive_rules:
            errors.append(f"adaptive_rules_missing:{required_section}")
    if "guilds" not in guilds_config or "rivalry" not in guilds_config["guilds"]:
        errors.append("guilds_missing_rivalry")
    if "prestige" not in prestige or not prestige["prestige"].get("sources"):
        errors.append("prestige_missing_sources")
    if "streaks" not in streaks or not streaks["streaks"].get("daily_play"):
        errors.append("streaks_missing_daily_play")
    if economy.get("economy_model", {}).get("global_currency", {}).get("id") != "credits":
        errors.append("economy_global_currency_mismatch")
    if economy.get("economy_model", {}).get("progression_currency", {}).get("id") != "mastery_points":
        errors.append("economy_progression_currency_mismatch")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("RUNTIME_TRUTH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

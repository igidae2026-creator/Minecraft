#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"
OPS = ROOT / "ops"
PLUGINS = ROOT / "plugins"


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    network = load(CONFIG / "network.yml")
    persistence = load(CONFIG / "persistence.yml")
    scaling = load(CONFIG / "scaling.yml")
    guards = load(CONFIG / "exploit_guards.yml")
    economy = load(CONFIG / "economy.yml")
    items = load(CONFIG / "items.yml")
    mobs = load(CONFIG / "mobs.yml")
    quests = load(CONFIG / "quests.yml")
    bosses = load(CONFIG / "bosses.yml")
    dungeons = load(CONFIG / "dungeons.yml")
    dungeon_templates = load(CONFIG / "dungeon_templates.yml")
    gear_tiers = load(CONFIG / "gear_tiers.yml")
    events = load(CONFIG / "events.yml")
    boss_behaviors = load(CONFIG / "boss_behaviors.yml")
    event_scheduler = load(CONFIG / "event_scheduler.yml")
    reward_pools = load(CONFIG / "reward_pools.yml")
    runtime_monitor = load(CONFIG / "runtime_monitor.yml")
    adaptive_rules = load(CONFIG / "adaptive_rules.yml")
    autonomy = load(CONFIG / "autonomy.yml")
    guilds_config = load(CONFIG / "guilds.yml")
    prestige = load(CONFIG / "prestige.yml")
    streaks = load(CONFIG / "streaks.yml")
    lobby = load(CONFIG / "lobby.yml")
    genres = load(CONFIG / "genres.yml")
    pressure = load(CONFIG / "pressure.yml")
    experiments = load(CONFIG / "experiments.yml")
    governance = load(CONFIG / "governance.yml")
    matrix = load(OPS / "plugin_matrix.yml")

    build_gradle = (ROOT / "build.gradle").read_text(encoding="utf-8")
    core_source = (PLUGINS / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    errors: list[str] = []

    servers = network["servers"]
    try_order = network["proxy"]["try"]

    if not try_order:
        errors.append("proxy.try is empty")
    for server_name in try_order:
        if server_name not in servers:
            errors.append(f"proxy.try references unknown server: {server_name}")

    ports = []
    for server_name, data in servers.items():
        address = data["address"]
        host, port = address.split(":")
        ports.append(port)
        if host != "127.0.0.1":
            errors.append(f"{server_name} is not bound to localhost")
        role = data["role"]
        if data["view_distance"] > scaling["limits"]["max_view_distance_by_role"][role]:
            errors.append(f"{server_name} exceeds view-distance cap")
        if data["simulation_distance"] > scaling["limits"]["max_simulation_distance_by_role"][role]:
            errors.append(f"{server_name} exceeds simulation-distance cap")
        if data["simulation_distance"] > data["view_distance"]:
            errors.append(f"{server_name} simulation-distance exceeds view-distance")

    if len(set(ports)) != len(ports):
        errors.append("duplicate backend ports detected")

    if network["proxy"]["player_info_forwarding_mode"].lower() != "modern":
        errors.append("Velocity modern forwarding is not required")

    if not persistence["mysql"]["enabled"] or not persistence["redis"]["enabled"]:
        errors.append("mysql and redis must both be enabled")
    if persistence["redis"].get("required_for_session_authority", True):
        errors.append("redis.required_for_session_authority must remain false because session authority is in-repo authoritative")
    if not persistence["local_fallback"]["enabled"]:
        errors.append("local_fallback must remain enabled")
    if not persistence["write_policy"]["save_on_server_transfer"]:
        errors.append("save_on_server_transfer must remain enabled")

    if not guards["economy"]["duplicate_transaction_protection"]:
        errors.append("duplicate transaction protection is disabled")
    if not guards["network"]["direct_backend_join_block"]:
        errors.append("direct backend join protection is disabled")

    item_materials = set(items["materials"].keys())

    mob_drops = set()
    for mob_data in mobs.values():
        mob_drops.update(mob_data["drops"].keys())

    if "cave_map_scrap" not in mob_drops:
        errors.append("no mob provides dungeon entry material cave_map_scrap")

    dungeon_entry_items = set()
    dungeon_completion_rewards = set()
    for dungeon_data in dungeons.values():
        dungeon_entry_items.update(dungeon_data.get("entry_requirements", {}).keys())
        dungeon_completion_rewards.update(dungeon_data.get("completion_rewards", {}).keys())
        template_pool = dungeon_data.get("template_pool", [])
        if not template_pool:
            errors.append("dungeon template_pool must not be empty")
        for template_id in template_pool:
            if template_id not in dungeon_templates.get("templates", {}):
                errors.append(f"dungeon references missing template {template_id}")
        active_template = dungeon_data.get("active_template")
        if active_template not in dungeon_templates.get("templates", {}):
            errors.append(f"dungeon active_template missing template {active_template}")

    if not dungeon_entry_items.issubset(mob_drops | item_materials):
        errors.append("dungeon entry requirements are not obtainable")
    if not dungeon_completion_rewards:
        errors.append("dungeon completion rewards are empty")

    boss_summon_items = set()
    boss_drops = set()
    for boss_data in bosses.values():
        boss_summon_items.update(boss_data["summon"]["required_items"].keys())
        boss_drops.update(boss_data["drops"]["guaranteed"].keys())
        boss_drops.update(boss_data["drops"].get("rare", {}).keys())

    if not boss_summon_items.intersection(dungeon_completion_rewards | mob_drops | boss_drops):
        errors.append("boss summon materials are not connected to the loop")

    upgrade_requirements = set()
    for tier_data in items["tiers"].values():
        upgrade_requirements.update(tier_data.get("required_materials", {}).keys())
    for craft_data in items["crafting"].values():
        upgrade_requirements.update(craft_data.get("required_materials", {}).keys())

    if not upgrade_requirements.intersection(boss_drops):
        errors.append("boss drops do not feed into gear upgrades")

    quest_reward_items = set()
    for quest_data in quests.values():
        quest_reward_items.update(quest_data["reward"].get("items", {}).keys())
    if not quest_reward_items.intersection(dungeon_entry_items | boss_summon_items | upgrade_requirements):
        errors.append("quest rewards do not reinforce the loop")

    faucet_total = sum(economy["faucets"]["quests"].values()) + sum(economy["faucets"]["mobs"].values()) + sum(economy["faucets"]["dungeons"].values()) + sum(economy["faucets"]["bosses"].values())
    sink_total = economy["sinks"]["dungeon_entry"]["goblin_cave"] + economy["sinks"]["boss_summon"]["goblin_king"] + economy["sinks"]["boss_summon"]["forest_guardian"] + sum(economy["sinks"]["crafting_upgrade"].values()) + economy["sinks"]["travel"]["local_transfer_fee"]

    if economy["market_tax"] <= 0:
        errors.append("market_tax must be positive")
    if economy.get("economy_model", {}).get("global_currency", {}).get("id") != "credits":
        errors.append("global currency id drift detected")
    if economy.get("economy_model", {}).get("progression_currency", {}).get("id") != "mastery_points":
        errors.append("progression currency id drift detected")
    for required_genre_currency in ("rpg", "minigame", "event"):
        if required_genre_currency not in economy.get("economy_model", {}).get("genre_currency", {}):
            errors.append(f"genre currency missing: {required_genre_currency}")
    if economy["starting_balance"] >= economy["sinks"]["crafting_upgrade"]["rare_to_epic"]:
        errors.append("starting_balance bypasses early progression")
    if sink_total <= faucet_total / 2:
        errors.append("configured sinks are too small relative to faucets")
    if items["tiers"]["legendary"]["tradable"]:
        errors.append("legendary gear must remain non-tradable")

    event_defs = events.get("events", {})
    if not event_defs:
        errors.append("events.yml must define at least one event")
    for event_id, event_data in event_defs.items():
        mob_id = event_data["mob"]
        if mob_id not in mobs:
            errors.append(f"event {event_id} references missing mob {mob_id}")
        if event_data.get("bonus_item") not in item_materials:
            errors.append(f"event {event_id} references missing bonus_item")

    templates = dungeon_templates.get("templates", {})
    if not templates:
        errors.append("dungeon_templates.yml must define at least one template")
    for template_id, template_data in templates.items():
        for mob_id in template_data.get("enemy_groups", []):
            if mob_id not in mobs:
                errors.append(f"dungeon template {template_id} references missing mob {mob_id}")
        boss_id = template_data.get("boss_type")
        if boss_id and boss_id not in bosses:
            errors.append(f"dungeon template {template_id} references missing boss {boss_id}")

    behaviors = boss_behaviors.get("behaviors", {})
    if not behaviors:
        errors.append("boss_behaviors.yml must define at least one boss behavior")
    for boss_id, behavior in behaviors.items():
        if boss_id not in bosses:
            errors.append(f"boss behavior references missing boss {boss_id}")
        if not behavior.get("phases"):
            errors.append(f"boss behavior {boss_id} has no phases")

    pools = reward_pools.get("pools", {})
    if not pools:
        errors.append("reward_pools.yml must define at least one reward pool")
    for pool_id, pool_data in pools.items():
        for item_id in list((pool_data.get("guaranteed_items") or {}).keys()) + list((pool_data.get("weighted_items") or {}).keys()):
            if item_id not in item_materials:
                errors.append(f"reward pool {pool_id} references missing item {item_id}")

    normalized_tiers = gear_tiers.get("tiers", {})
    if not normalized_tiers:
        errors.append("gear_tiers.yml must define normalized tiers")
    for tier_id, tier_data in normalized_tiers.items():
        if tier_data.get("rank", 0) <= 0:
            errors.append(f"gear tier {tier_id} missing positive rank")
        if not tier_data.get("aliases"):
            errors.append(f"gear tier {tier_id} missing aliases")
    for genre_id in ("rpg", "minigame", "event", "boss", "dungeon"):
        if genre_id not in gear_tiers.get("genre_reward_mapping", {}):
            errors.append(f"gear tier genre mapping missing: {genre_id}")

    scheduled_events = event_scheduler.get("events", {})
    if not scheduled_events:
        errors.append("event_scheduler.yml must define at least one event")
    for event_id, event_data in scheduled_events.items():
        if event_id not in event_defs:
            errors.append(f"event scheduler references missing event {event_id}")
        if event_data.get("reward_pool") not in pools:
            errors.append(f"event scheduler {event_id} references missing reward pool")

    if "mysql-connector-j" not in build_gradle:
        errors.append("rpg_core must bundle a deployable mysql connector")

    for marker in ("mysqlDriverAvailable", "canAccessWorld", "canClaimReservedEntityKill", "isTravelAllowed", "trackHighValueItemMint", "exportArtifact", "reconcileItemAuthority", "sessionAuthorityService", "deterministicTransferService", "gameplayArtifactRegistry", "governancePolicyRegistry", "ContentEngine", "composeRewardPool", "resolveDungeonTemplate", "pollLobbyContentBroadcasts", "progressionSummary", "craftGear", "repairGear", "unlockCosmetic", "buyTemporaryBuff", "normalizedTier", "runOperationsBrain", "quarantineInstance", "shouldQueueJoin", "operationsStatus", "TelemetryAdaptiveEngine", "recomputeAdaptiveGameplay", "ingestTelemetry", "adaptiveDifficultyMultiplier", "adaptiveRewardWeightMultiplier", "adaptiveEventFrequencyMultiplier", "adaptiveMatchmakingRangeMultiplier", "createGuild", "inviteGuild", "joinGuild", "sendGuildChat", "setGuildRank", "addPrestige", "advanceStreak", "grantReturnRewardIfEligible", "recordRivalryEncounter"):
        if marker not in core_source:
            errors.append(f"rpg_core missing production patch marker: {marker}")

    if network["data_flow"].get("live_session_state") != "local_authoritative_lease_registry":
        errors.append("network.data_flow.live_session_state drift detected")
    if network["data_flow"].get("live_session_coordination") != "in_repo_deterministic_session_authority":
        errors.append("network.data_flow.live_session_coordination drift detected")
    if network["data_flow"].get("rare_item_authority") != "local_manifest_plus_ledger_lineage":
        errors.append("network.data_flow.rare_item_authority drift detected")
    if network["data_flow"].get("gameplay_artifacts") != "runtime_data/artifacts":
        errors.append("network.data_flow.gameplay_artifacts drift detected")
    if network["data_flow"].get("experiment_registry") != "runtime_data/experiments":
        errors.append("network.data_flow.experiment_registry drift detected")
    if network["data_flow"].get("incident_artifacts") != "runtime_data/incidents":
        errors.append("network.data_flow.incident_artifacts drift detected")
    if network["data_flow"].get("knowledge_index") != "runtime_data/knowledge":
        errors.append("network.data_flow.knowledge_index drift detected")
    if network["data_flow"].get("pressure_control") != "runtime_data/status":
        errors.append("network.data_flow.pressure_control drift detected")
    if network["data_flow"].get("genre_registry") != "configs/genres.yml":
        errors.append("network.data_flow.genre_registry drift detected")
    if not pressure["controls"]["noncritical_spawn_suppression"]:
        errors.append("pressure controls must suppress noncritical spawns")
    if not experiments["operations"]["kill_switch"]:
        errors.append("experiment kill switch must remain enabled")
    if not governance["operations"]["rollback_enabled"]:
        errors.append("governance rollback must remain enabled")
    if runtime_monitor["health_thresholds"]["tps_critical"] >= runtime_monitor["health_thresholds"]["tps_warning"]:
        errors.append("runtime monitor tps thresholds invalid")
    if not autonomy.get("loop", {}).get("enabled", False):
        errors.append("autonomy loop must remain enabled")
    if not autonomy.get("parameters"):
        errors.append("autonomy parameters must exist")
    if not runtime_monitor["queue"]["enabled"]:
        errors.append("runtime queue must remain enabled")
    for required_section in ("telemetry", "difficulty", "rewards", "events", "matchmaking", "churn", "safety"):
        if required_section not in adaptive_rules:
            errors.append(f"adaptive rules missing section: {required_section}")
    if "guilds" not in guilds_config or "progression" not in guilds_config["guilds"] or "rivalry" not in guilds_config["guilds"]:
        errors.append("guilds.yml missing social guild progression/rivalry sections")
    if "prestige" not in prestige or not prestige["prestige"].get("badges"):
        errors.append("prestige.yml missing badges")
    if "streaks" not in streaks or "return_reward" not in streaks["streaks"]:
        errors.append("streaks.yml missing return reward")
    if not lobby["routes"]:
        errors.append("lobby routes must not be empty")
    for required_route in ("start_adventure", "quick_match", "rotating_event", "explore_hub"):
        if required_route not in lobby["routes"]:
            errors.append(f"lobby route missing: {required_route}")
    for required_genre in ("lobby", "rpg", "minigame", "event", "dungeon"):
        if required_genre not in genres["genre_registry"]:
            errors.append(f"genre registry missing: {required_genre}")

    expected_plugins = {
        "rpg_core", "economy_engine", "quest_system", "boss_ai",
        "dungeon_system", "guild_system", "skill_system",
        "event_scheduler", "metrics_monitor"
    }
    actual_plugins = {path.name for path in PLUGINS.iterdir() if path.is_dir() and (path / "plugin.yml").is_file()}
    if actual_plugins != expected_plugins:
        errors.append("plugin directory set drift detected")

    for server_name, plugins in matrix.items():
        if server_name not in servers:
            errors.append(f"plugin matrix references unknown server {server_name}")
        if "rpg_core" not in plugins:
            errors.append(f"plugin matrix for {server_name} must include rpg_core")
        if "metrics_monitor" not in plugins:
            errors.append(f"plugin matrix for {server_name} must include metrics_monitor")
        if server_name == "dungeons" and "dungeon_system" not in plugins:
            errors.append("dungeons server must include dungeon_system")
        if server_name == "boss_world" and "boss_ai" not in plugins:
            errors.append("boss_world must include boss_ai")
        if server_name == "events" and "event_scheduler" not in plugins:
            errors.append("events must include event_scheduler")

    for plugin_name in expected_plugins:
        plugin_yml = load(PLUGINS / plugin_name / "plugin.yml")
        if plugin_yml["version"] != "1.2.0":
            errors.append(f"{plugin_name} plugin version must be 1.2.0")
        if plugin_name != "metrics_monitor" and not plugin_yml.get("commands"):
            errors.append(f"{plugin_name} must expose commands")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("VALIDATION_OK")
    print(f"SERVERS={len(servers)}")
    print(f"GAMEPLAY_LOOP=closed")
    print(f"ECONOMY_SINK_TOTAL={sink_total}")
    print(f"ECONOMY_FAUCET_TOTAL={faucet_total}")
    print(f"EVENTS={len(event_defs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

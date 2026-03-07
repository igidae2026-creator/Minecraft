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
    events = load(CONFIG / "events.yml")
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

    if "mysql-connector-j" not in build_gradle:
        errors.append("rpg_core must bundle a deployable mysql connector")

    for marker in ("mysqlDriverAvailable", "canAccessWorld", "canClaimReservedEntityKill", "isTravelAllowed"):
        if marker not in core_source:
            errors.append(f"rpg_core missing production patch marker: {marker}")

    expected_plugins = {
        "rpg_core", "economy_engine", "quest_system", "boss_ai",
        "dungeon_system", "guild_system", "skill_system",
        "event_scheduler", "metrics_monitor"
    }
    if set(path.name for path in PLUGINS.iterdir() if path.is_dir()) != expected_plugins:
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

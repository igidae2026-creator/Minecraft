#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from io import StringIO

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "runtime_data" / "status"
NETWORK_PATH = ROOT / "configs" / "network.yml"

TOP_LEVEL_KEYS = (
    "server", "role", "safe_mode", "safe_mode_reason", "reconciliation_mismatches",
    "guild_value_drift", "replay_divergence", "item_ownership_conflicts", "queue_size",
    "player_density", "network_routing_latency_ms", "runtime_composite_pressure", "runtime_tps",
    "dungeon_started", "dungeon_completed", "boss_killed", "event_started", "event_join_count",
    "reward_distributed", "economy_earn", "economy_spend", "gear_drop", "gear_upgrade",
    "progression_level_up", "instance_spawn", "instance_shutdown", "exploit_flag",
    "adaptive_adjustment", "difficulty_change", "reward_adjustment", "event_frequency_change",
    "matchmaking_adjustment", "guild_created", "guild_joined", "prestige_gain",
    "return_player_reward", "streak_progress", "rivalry_created", "rivalry_match", "rivalry_reward",
)

SECTION_KEYS = {
    "pressure_control_plane": ("composite", "captured_at"),
    "runtime_knowledge_index": ("records",),
    "exploit_forensics_plane": ("incident_total",),
    "session_authority_service": ("split_brain_detections", "session_ownership_conflicts"),
    "deterministic_transfer_service": ("lease_verification_failures", "quarantines", "stale_load_rejections"),
    "economy_item_authority_plane": ("quarantined_items",),
    "experiment_registry": ("rollbacks",),
    "policy_registry": ("rollbacks",),
}


def parse_scalar(raw: str):
    text = raw.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text == "''":
        return ""
    try:
        if any(ch in text for ch in (".", "e", "E")):
            return float(text)
        return int(text)
    except ValueError:
        return text


def extract(text: str) -> dict:
    result: dict = {}
    current_section = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            if key in SECTION_KEYS and value.strip() == "":
                current_section = key
                result.setdefault(key, {})
                continue
            current_section = None
            if key in TOP_LEVEL_KEYS:
                result[key] = parse_scalar(value)
            continue
        if indent == 2 and current_section in SECTION_KEYS and ":" in line:
            key, value = line.split(":", 1)
            if key in SECTION_KEYS[current_section]:
                result.setdefault(current_section, {})[key] = parse_scalar(value)
    return result


def main() -> int:
    network = {}
    if NETWORK_PATH.exists():
        with NETWORK_PATH.open("r", encoding="utf-8") as handle:
            network = yaml.safe_load(handle) or {}
    server_defs = (network.get("servers", {}) or {})
    rebuilt = 0
    for path in sorted(STATUS_DIR.glob("*.yml")):
        if path.name == ".gitkeep":
            continue
        text = path.read_text(encoding="utf-8")
        data = extract(text)
        server_name = path.stem
        server_cfg = server_defs.get(server_name, {}) or {}
        role = server_cfg.get("role", data.get("role", "unknown"))
        defaults = {
            "server": server_name,
            "role": role,
            "safe_mode": False,
            "safe_mode_reason": "",
            "reconciliation_mismatches": 0,
            "guild_value_drift": 0,
            "replay_divergence": 0,
            "item_ownership_conflicts": 0,
            "queue_size": 0,
            "player_density": 0,
            "network_routing_latency_ms": 0.0,
            "runtime_composite_pressure": 0.0,
            "runtime_tps": 20.0,
            "dungeon_started": 0,
            "dungeon_completed": 0,
            "boss_killed": 0,
            "event_started": 0,
            "event_join_count": 0,
            "reward_distributed": 0,
            "economy_earn": 0,
            "economy_spend": 0,
            "gear_drop": 0,
            "gear_upgrade": 0,
            "progression_level_up": 0,
            "instance_spawn": 0,
            "instance_shutdown": 0,
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
            "pressure_control_plane": {"composite": 0.0, "captured_at": 0},
            "runtime_knowledge_index": {"records": 1},
            "exploit_forensics_plane": {"incident_total": 0},
            "session_authority_service": {"split_brain_detections": 0, "session_ownership_conflicts": 0},
            "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0, "stale_load_rejections": 0},
            "economy_item_authority_plane": {"quarantined_items": 0},
            "experiment_registry": {"rollbacks": 0},
            "policy_registry": {"rollbacks": 0},
        }
        merged = defaults
        merged.update(data)
        for section_key in SECTION_KEYS:
            merged[section_key] = {**defaults[section_key], **(data.get(section_key, {}) or {})}
        if data:
            stream = StringIO()
            yaml.safe_dump(merged, stream, sort_keys=False, allow_unicode=True)
            path.write_text(stream.getvalue(), encoding="utf-8")
            rebuilt += 1
    print(f"REBUILT_STATUS_FILES={rebuilt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

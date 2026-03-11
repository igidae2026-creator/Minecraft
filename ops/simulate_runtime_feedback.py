#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "runtime_data" / "status"
CONFIG_DIR = ROOT / "configs"


PROFILES = {
    "healthy": {
        "lobby": {
            "event_started": 2,
            "event_join_count": 22,
            "reward_distributed": 16,
            "queue_size": 6,
            "player_density": 20,
            "network_routing_latency_ms": 12.0,
            "return_player_reward": 3,
            "streak_progress": 7,
            "rivalry_created": 1,
            "rivalry_match": 2,
            "runtime_composite_pressure": 0.22,
        },
        "progression": {
            "dungeon_started": 18,
            "dungeon_completed": 12,
            "reward_distributed": 28,
            "economy_earn": 2200,
            "economy_spend": 1500,
            "gear_drop": 12,
            "gear_upgrade": 4,
            "progression_level_up": 5,
            "queue_size": 9,
            "player_density": 26,
            "network_routing_latency_ms": 18.0,
            "runtime_composite_pressure": 0.38,
        },
        "instance": {
            "dungeon_started": 24,
            "dungeon_completed": 15,
            "boss_killed": 3,
            "reward_distributed": 31,
            "economy_earn": 1800,
            "economy_spend": 1200,
            "gear_drop": 18,
            "gear_upgrade": 5,
            "instance_spawn": 6,
            "instance_shutdown": 5,
            "player_density": 18,
            "network_routing_latency_ms": 15.0,
            "runtime_composite_pressure": 0.44,
        },
        "boss": {
            "boss_killed": 4,
            "reward_distributed": 14,
            "economy_earn": 900,
            "economy_spend": 500,
            "gear_drop": 6,
            "queue_size": 4,
            "player_density": 12,
            "network_routing_latency_ms": 11.0,
            "runtime_composite_pressure": 0.29,
        },
        "event": {
            "event_started": 5,
            "event_join_count": 64,
            "reward_distributed": 35,
            "economy_earn": 1600,
            "economy_spend": 700,
            "queue_size": 7,
            "player_density": 32,
            "network_routing_latency_ms": 14.0,
            "return_player_reward": 2,
            "streak_progress": 5,
            "runtime_composite_pressure": 0.34,
        },
    },
    "overloaded": {
        "lobby": {
            "event_started": 2,
            "event_join_count": 10,
            "reward_distributed": 12,
            "queue_size": 48,
            "player_density": 78,
            "network_routing_latency_ms": 115.0,
            "return_player_reward": 1,
            "streak_progress": 2,
            "runtime_composite_pressure": 0.84,
        },
        "progression": {
            "dungeon_started": 16,
            "dungeon_completed": 9,
            "reward_distributed": 20,
            "economy_earn": 1500,
            "economy_spend": 900,
            "gear_drop": 7,
            "gear_upgrade": 2,
            "progression_level_up": 2,
            "queue_size": 42,
            "player_density": 74,
            "network_routing_latency_ms": 120.0,
            "runtime_composite_pressure": 0.88,
        },
        "instance": {
            "dungeon_started": 22,
            "dungeon_completed": 11,
            "boss_killed": 1,
            "reward_distributed": 20,
            "economy_earn": 1300,
            "economy_spend": 1000,
            "gear_drop": 10,
            "gear_upgrade": 2,
            "instance_spawn": 9,
            "instance_shutdown": 3,
            "player_density": 72,
            "network_routing_latency_ms": 132.0,
            "runtime_composite_pressure": 0.91,
        },
        "boss": {
            "boss_killed": 2,
            "reward_distributed": 8,
            "economy_earn": 600,
            "economy_spend": 400,
            "gear_drop": 3,
            "queue_size": 24,
            "player_density": 55,
            "network_routing_latency_ms": 96.0,
            "runtime_composite_pressure": 0.76,
        },
        "event": {
            "event_started": 6,
            "event_join_count": 18,
            "reward_distributed": 22,
            "economy_earn": 1200,
            "economy_spend": 600,
            "queue_size": 35,
            "player_density": 68,
            "network_routing_latency_ms": 101.0,
            "return_player_reward": 1,
            "streak_progress": 2,
            "runtime_composite_pressure": 0.79,
        },
    },
    "low_completion": {
        "lobby": {
            "event_started": 2,
            "event_join_count": 16,
            "reward_distributed": 10,
            "queue_size": 8,
            "player_density": 22,
            "network_routing_latency_ms": 14.0,
            "runtime_composite_pressure": 0.30,
        },
        "progression": {
            "dungeon_started": 20,
            "dungeon_completed": 7,
            "reward_distributed": 18,
            "economy_earn": 1400,
            "economy_spend": 1200,
            "gear_drop": 7,
            "gear_upgrade": 2,
            "progression_level_up": 2,
            "queue_size": 10,
            "player_density": 28,
            "network_routing_latency_ms": 22.0,
            "runtime_composite_pressure": 0.41,
        },
        "instance": {
            "dungeon_started": 28,
            "dungeon_completed": 10,
            "boss_killed": 1,
            "reward_distributed": 24,
            "economy_earn": 1600,
            "economy_spend": 1400,
            "gear_drop": 12,
            "gear_upgrade": 2,
            "instance_spawn": 7,
            "instance_shutdown": 5,
            "player_density": 24,
            "network_routing_latency_ms": 18.0,
            "runtime_composite_pressure": 0.46,
        },
        "boss": {
            "boss_killed": 1,
            "reward_distributed": 7,
            "economy_earn": 500,
            "economy_spend": 300,
            "gear_drop": 2,
            "queue_size": 4,
            "player_density": 12,
            "network_routing_latency_ms": 12.0,
            "runtime_composite_pressure": 0.27,
        },
        "event": {
            "event_started": 3,
            "event_join_count": 25,
            "reward_distributed": 15,
            "economy_earn": 900,
            "economy_spend": 500,
            "queue_size": 7,
            "player_density": 24,
            "network_routing_latency_ms": 15.0,
            "runtime_composite_pressure": 0.32,
        },
    },
    "low_engagement": {
        "lobby": {
            "event_started": 4,
            "event_join_count": 2,
            "reward_distributed": 7,
            "queue_size": 5,
            "player_density": 18,
            "network_routing_latency_ms": 10.0,
            "return_player_reward": 0,
            "streak_progress": 1,
            "runtime_composite_pressure": 0.24,
        },
        "progression": {
            "dungeon_started": 12,
            "dungeon_completed": 10,
            "reward_distributed": 20,
            "economy_earn": 1800,
            "economy_spend": 1000,
            "gear_drop": 10,
            "gear_upgrade": 3,
            "progression_level_up": 3,
            "queue_size": 7,
            "player_density": 22,
            "network_routing_latency_ms": 16.0,
            "runtime_composite_pressure": 0.33,
        },
        "instance": {
            "dungeon_started": 14,
            "dungeon_completed": 11,
            "boss_killed": 2,
            "reward_distributed": 18,
            "economy_earn": 1400,
            "economy_spend": 900,
            "gear_drop": 10,
            "gear_upgrade": 3,
            "instance_spawn": 4,
            "instance_shutdown": 4,
            "player_density": 20,
            "network_routing_latency_ms": 16.0,
            "runtime_composite_pressure": 0.35,
        },
        "boss": {
            "boss_killed": 2,
            "reward_distributed": 9,
            "economy_earn": 600,
            "economy_spend": 350,
            "gear_drop": 3,
            "queue_size": 4,
            "player_density": 12,
            "network_routing_latency_ms": 10.0,
            "runtime_composite_pressure": 0.25,
        },
        "event": {
            "event_started": 7,
            "event_join_count": 4,
            "reward_distributed": 10,
            "economy_earn": 700,
            "economy_spend": 450,
            "queue_size": 6,
            "player_density": 20,
            "network_routing_latency_ms": 12.0,
            "return_player_reward": 0,
            "streak_progress": 1,
            "runtime_composite_pressure": 0.28,
        },
    },
    "inflation": {
        "lobby": {
            "event_started": 2,
            "event_join_count": 8,
            "reward_distributed": 18,
            "economy_earn": 1200,
            "economy_spend": 300,
            "queue_size": 8,
            "player_density": 24,
            "network_routing_latency_ms": 18.0,
            "runtime_composite_pressure": 0.42,
        },
        "progression": {
            "dungeon_started": 18,
            "dungeon_completed": 12,
            "reward_distributed": 30,
            "economy_earn": 5400,
            "economy_spend": 1200,
            "gear_drop": 10,
            "gear_upgrade": 2,
            "progression_level_up": 4,
            "queue_size": 8,
            "player_density": 28,
            "network_routing_latency_ms": 20.0,
            "runtime_composite_pressure": 0.46,
        },
        "instance": {
            "dungeon_started": 22,
            "dungeon_completed": 14,
            "boss_killed": 2,
            "reward_distributed": 36,
            "economy_earn": 6200,
            "economy_spend": 1400,
            "gear_drop": 14,
            "gear_upgrade": 3,
            "instance_spawn": 6,
            "instance_shutdown": 5,
            "player_density": 24,
            "network_routing_latency_ms": 18.0,
            "runtime_composite_pressure": 0.48,
        },
        "boss": {
            "boss_killed": 3,
            "reward_distributed": 16,
            "economy_earn": 2400,
            "economy_spend": 500,
            "gear_drop": 5,
            "queue_size": 4,
            "player_density": 14,
            "network_routing_latency_ms": 12.0,
            "runtime_composite_pressure": 0.31,
        },
        "event": {
            "event_started": 4,
            "event_join_count": 28,
            "reward_distributed": 24,
            "economy_earn": 3600,
            "economy_spend": 800,
            "queue_size": 6,
            "player_density": 26,
            "network_routing_latency_ms": 15.0,
            "runtime_composite_pressure": 0.39,
        },
    },
    "exploit": {
        "lobby": {
            "event_started": 1,
            "event_join_count": 4,
            "reward_distributed": 8,
            "queue_size": 12,
            "player_density": 30,
            "network_routing_latency_ms": 32.0,
            "runtime_composite_pressure": 0.52,
            "exploit_flag": 2,
        },
        "progression": {
            "dungeon_started": 12,
            "dungeon_completed": 8,
            "reward_distributed": 18,
            "economy_earn": 2800,
            "economy_spend": 1000,
            "gear_drop": 8,
            "gear_upgrade": 2,
            "progression_level_up": 2,
            "queue_size": 14,
            "player_density": 34,
            "network_routing_latency_ms": 40.0,
            "runtime_composite_pressure": 0.57,
            "exploit_flag": 3,
        },
        "instance": {
            "dungeon_started": 16,
            "dungeon_completed": 9,
            "boss_killed": 1,
            "reward_distributed": 20,
            "economy_earn": 2600,
            "economy_spend": 1200,
            "gear_drop": 10,
            "gear_upgrade": 1,
            "instance_spawn": 6,
            "instance_shutdown": 3,
            "player_density": 28,
            "network_routing_latency_ms": 38.0,
            "runtime_composite_pressure": 0.62,
            "exploit_flag": 4,
        },
        "boss": {
            "boss_killed": 1,
            "reward_distributed": 8,
            "economy_earn": 1200,
            "economy_spend": 400,
            "gear_drop": 4,
            "queue_size": 6,
            "player_density": 18,
            "network_routing_latency_ms": 25.0,
            "runtime_composite_pressure": 0.41,
            "exploit_flag": 2,
        },
        "event": {
            "event_started": 3,
            "event_join_count": 10,
            "reward_distributed": 12,
            "economy_earn": 2200,
            "economy_spend": 700,
            "queue_size": 10,
            "player_density": 24,
            "network_routing_latency_ms": 28.0,
            "runtime_composite_pressure": 0.49,
            "exploit_flag": 3,
        },
    },
    "mixed": {
        "lobby": {
            "event_started": 3,
            "event_join_count": 4,
            "reward_distributed": 10,
            "queue_size": 28,
            "player_density": 52,
            "network_routing_latency_ms": 74.0,
            "return_player_reward": 1,
            "streak_progress": 2,
            "runtime_composite_pressure": 0.66,
            "exploit_flag": 1,
        },
        "progression": {
            "dungeon_started": 20,
            "dungeon_completed": 8,
            "reward_distributed": 22,
            "economy_earn": 4200,
            "economy_spend": 1300,
            "gear_drop": 9,
            "gear_upgrade": 2,
            "progression_level_up": 2,
            "queue_size": 26,
            "player_density": 58,
            "network_routing_latency_ms": 82.0,
            "runtime_composite_pressure": 0.73,
            "exploit_flag": 2,
        },
        "instance": {
            "dungeon_started": 24,
            "dungeon_completed": 9,
            "boss_killed": 1,
            "reward_distributed": 24,
            "economy_earn": 3900,
            "economy_spend": 1200,
            "gear_drop": 10,
            "gear_upgrade": 2,
            "instance_spawn": 8,
            "instance_shutdown": 4,
            "player_density": 62,
            "network_routing_latency_ms": 96.0,
            "runtime_composite_pressure": 0.81,
            "exploit_flag": 3,
        },
        "boss": {
            "boss_killed": 2,
            "reward_distributed": 10,
            "economy_earn": 1700,
            "economy_spend": 500,
            "gear_drop": 4,
            "queue_size": 10,
            "player_density": 26,
            "network_routing_latency_ms": 36.0,
            "runtime_composite_pressure": 0.52,
            "exploit_flag": 1,
        },
        "event": {
            "event_started": 5,
            "event_join_count": 8,
            "reward_distributed": 14,
            "economy_earn": 2600,
            "economy_spend": 800,
            "queue_size": 20,
            "player_density": 40,
            "network_routing_latency_ms": 58.0,
            "return_player_reward": 1,
            "streak_progress": 2,
            "runtime_composite_pressure": 0.61,
            "exploit_flag": 2,
        },
    },
}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def add_metric(payload: dict, key: str, delta) -> None:
    current = payload.get(key, 0)
    if isinstance(delta, float):
        payload[key] = round(float(current) + delta, 3)
    else:
        payload[key] = int(current) + int(delta)


def set_metric(payload: dict, key: str, value) -> None:
    if isinstance(value, float):
        payload[key] = round(float(value), 3)
    else:
        payload[key] = int(value)


def safe_int(value, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def bump_nested(payload: dict, key: str, subkey: str, delta: int) -> None:
    section = payload.setdefault(key, {}) or {}
    section[subkey] = int(section.get(subkey, 0)) + delta
    payload[key] = section


def control_feedback(updates: dict, *, market_tax: float) -> dict:
    adjusted = dict(updates)
    earn = float(adjusted.get("economy_earn", 0))
    spend = float(adjusted.get("economy_spend", 0))
    if earn > 0 or spend > 0:
        earn_multiplier = max(0.5, 1.0 - (market_tax * 1.5))
        spend_multiplier = min(1.5, 1.0 + (market_tax * 2.5))
        adjusted["economy_earn"] = int(round(earn * earn_multiplier))
        adjusted["economy_spend"] = int(round(spend * spend_multiplier))
    return adjusted


def main(argv: list[str]) -> int:
    cycles = 1
    profile = "healthy"
    mode = "accumulate"
    if len(argv) >= 2 and argv[0] == "--cycles":
        cycles = max(1, int(argv[1]))
        argv = argv[2:]
    if len(argv) >= 2 and argv[0] == "--profile":
        profile = argv[1]
        argv = argv[2:]
    if len(argv) >= 2 and argv[0] == "--mode":
        mode = argv[1]
    if profile not in PROFILES:
        print(f"UNKNOWN_PROFILE={profile}", file=sys.stderr)
        return 1
    if mode not in {"accumulate", "replace"}:
        print(f"UNKNOWN_MODE={mode}", file=sys.stderr)
        return 1
    economy = load_yaml(CONFIG_DIR / "economy.yml")
    market_tax = float(economy.get("market_tax", 0.08))

    updated = 0
    role_updates = PROFILES[profile]
    tracked_override_keys = {
        "dungeon_started",
        "dungeon_completed",
        "boss_killed",
        "event_started",
        "event_join_count",
        "reward_distributed",
        "economy_earn",
        "economy_spend",
        "gear_drop",
        "gear_upgrade",
        "progression_level_up",
        "instance_spawn",
        "instance_shutdown",
        "queue_size",
        "player_density",
        "network_routing_latency_ms",
        "return_player_reward",
        "streak_progress",
        "rivalry_created",
        "rivalry_match",
        "runtime_composite_pressure",
        "exploit_flag",
    }
    for _ in range(cycles):
        for path in sorted(STATUS_DIR.glob("*.yml")):
            if path.name == ".gitkeep":
                continue
            status = load_yaml(path)
            role = str(status.get("role", ""))
            updates = role_updates.get(role)
            if not updates:
                continue
            controlled_updates = control_feedback(updates, market_tax=market_tax)
            if mode == "replace":
                for key in tracked_override_keys:
                    if key in {"network_routing_latency_ms", "runtime_composite_pressure"}:
                        status[key] = 0.0
                    else:
                        status[key] = 0
            for key, delta in controlled_updates.items():
                if key in {"runtime_composite_pressure", "network_routing_latency_ms", "queue_size", "player_density"}:
                    set_metric(status, key, delta)
                else:
                    add_metric(status, key, delta)
            pressure = status.setdefault("pressure_control_plane", {}) or {}
            pressure["composite"] = round(float(status.get("runtime_composite_pressure", pressure.get("composite", 0.0))), 3)
            pressure["captured_at"] = safe_int(pressure.get("captured_at", 0), 0) + 1
            status["pressure_control_plane"] = pressure
            bump_nested(status, "runtime_knowledge_index", "records", 4)
            status.setdefault("exploit_forensics_plane", {})
            status["exploit_forensics_plane"]["incident_total"] = int(status.get("exploit_flag", 0))
            add_metric(status, "adaptive_adjustment", 1)
            add_metric(status, "event_frequency_change", 1 if role in {"lobby", "event"} else 0)
            write_yaml(path, status)
            updated += 1

    print(f"SIMULATED_STATUS_FILES={updated}")
    print(f"CYCLES={cycles}")
    print(f"PROFILE={profile}")
    print(f"MODE={mode}")
    print(f"MARKET_TAX={market_tax:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

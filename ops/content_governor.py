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

    for candidate in candidates:
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
        "execution_threshold_ready": execution_threshold_ready,
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("CONTENT_GOVERNOR")
    print(f"GENERATED={len(candidates)}")
    print(f"PROMOTED={promoted}")
    print(f"HELD={held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

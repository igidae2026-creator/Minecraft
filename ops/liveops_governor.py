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
SUMMARY_PATH = RUNTIME / "autonomy" / "liveops_governor_summary.yml"
LIVEOPS_DIR = RUNTIME / "live_ops"
LEDGER_PATH = LIVEOPS_DIR / "ledger.jsonl"
PLAYER_EXPERIENCE_PATH = RUNTIME / "autonomy" / "player_experience_summary.yml"
FATIGUE_PATH = RUNTIME / "autonomy" / "engagement_fatigue_summary.yml"


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


def main() -> int:
    created_at = now_iso()
    control = load_yaml(CONTROL_STATE)
    LIVEOPS_DIR.mkdir(parents=True, exist_ok=True)
    scheduler = load_yaml(CONFIG / "event_scheduler.yml")
    events = load_yaml(CONFIG / "events.yml").get("events", {})
    player_experience = load_yaml(PLAYER_EXPERIENCE_PATH)
    fatigue = load_yaml(FATIGUE_PATH)
    rotation = scheduler.get("rotation", {})
    scheduled_events = scheduler.get("events", {})
    migration_required = int(rotation.get("dungeon_rotation_minutes", 0)) < 10
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_state = str(player_experience.get("experience_state", ""))
    boost_reentry = experience_percent < 50.0 or experience_state in {"early", "mid"}
    sustain_social = experience_percent >= 60.0 and experience_state == "advanced"
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 0.0))
    fatigue_state = str(fatigue.get("fatigue_state", ""))
    boost_novelty = fatigue_gap_score >= 0.38 or fatigue_state in {"watch", "high"}
    distinct_reward_pools = len({str(event.get("reward_pool", "")) for event in scheduled_events.values() if event.get("reward_pool")})
    distinct_event_types = len({str(event.get("type", "")) for event in scheduled_events.values() if event.get("type")})
    cadence_diversity_score = round(min(1.0, distinct_event_types / 4.0 + distinct_reward_pools / 4.0), 2)
    party_concurrency_support = 0.0

    action_id = f"liveops-{uuid.uuid4().hex[:12]}"
    scaffolded_actions = [
        {"action": "event_rotation", "mode": "promote", "event_ids": sorted(scheduled_events.keys())[:2]},
        {"action": "hotfix_window", "mode": "hold" if migration_required else "promote", "migration_plan_required": bool(migration_required)},
        {"action": "rollback_plan", "mode": "promote", "source": "append_only_lineage"},
    ]
    if boost_reentry:
        scaffolded_actions.extend(
            [
                {
                    "action": "returner_flash_week",
                    "mode": "promote",
                    "cohort": "returners",
                    "tempo_bias": "fast",
                    "reward_bias": "starter_plus",
                },
                {
                    "action": "guild_cohort_weekend",
                    "mode": "promote",
                    "cohort": "guild_social",
                    "objective": "cohort_progression",
                },
            ]
        )
    if boost_novelty:
        scaffolded_actions.extend(
            [
                {
                    "action": "novelty_burst_night",
                    "mode": "promote",
                    "cohort": "all_active",
                    "objective": "break_repetition",
                },
                {
                    "action": "remix_rivalry_week",
                    "mode": "promote",
                    "cohort": "guild_social",
                    "objective": "reignite_social_loop",
                },
            ]
        )
    if sustain_social:
        scaffolded_actions.extend(
            [
                {
                    "action": "guild_legacy_cycle",
                    "mode": "promote",
                    "cohort": "advanced_guilds",
                    "objective": "maintain_social_reentry",
                },
                {
                    "action": "mentor_returner_night",
                    "mode": "promote",
                    "cohort": "advanced_returners",
                    "objective": "long_tail_party_rejoin",
                },
                {
                    "action": "returner_legend_week",
                    "mode": "promote",
                    "cohort": "advanced_returners",
                    "objective": "persistent_mastery_reactivation",
                },
                {
                    "action": "seasonal_prestige_campaign",
                    "mode": "promote",
                    "cohort": "advanced_all",
                    "objective": "multi_week_campaign_arc",
                },
                {
                    "action": "party_raid_marathon",
                    "mode": "promote",
                    "cohort": "advanced_parties",
                    "objective": "sustain_group_concurrency",
                },
            ]
        )
        party_concurrency_support += 0.8
    if boost_reentry:
        party_concurrency_support += 0.35
    if boost_novelty:
        party_concurrency_support += 0.2
    payload = {
        "action_id": action_id,
        "created_at": created_at,
        "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
        "season_plan": {
            "rotation_minutes": int(rotation.get("dungeon_rotation_minutes", 0)),
            "event_count": len(scheduled_events),
            "broadcast_poll_seconds": int(rotation.get("lobby_broadcast_poll_seconds", 0)),
        },
        "scaffolded_actions": scaffolded_actions,
        "consumer_signals": {
            "live_events_defined": len(events),
            "scheduled_events_defined": len(scheduled_events),
            "estimated_completeness_percent": experience_percent,
            "experience_state": experience_state,
            "fatigue_gap_score": fatigue_gap_score,
            "fatigue_state": fatigue_state,
            "cadence_diversity_score": cadence_diversity_score,
        },
    }
    payload["signature"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    write_yaml(LIVEOPS_DIR / f"{created_at.replace(':', '').replace('-', '')}_{action_id}.yml", payload)
    append_jsonl(
        LEDGER_PATH,
        {
            "created_at": created_at,
            "action_id": action_id,
            "migration_required": bool(migration_required),
            "scheduled_events": len(scheduled_events),
            "boost_reentry": boost_reentry,
            "signature": payload["signature"],
        },
    )
    summary = {
        "created_at": created_at,
        "action_id": action_id,
        "migration_required": bool(migration_required),
        "scheduled_events": len(scheduled_events),
        "live_events_defined": len(events),
        "boost_reentry": boost_reentry,
        "sustain_social": sustain_social,
        "boost_novelty": boost_novelty,
        "returner_reactivation_depth": 1 if sustain_social else (1 if boost_reentry else 0),
        "liveops_depth_strength": round(
            min(
                3.0,
                sum(1 for action in payload["scaffolded_actions"] if action["mode"] == "promote") * 0.35
                + cadence_diversity_score * 0.8
                + (0.5 if sustain_social else 0.0)
                + (0.3 if boost_novelty else 0.0),
            ),
            2,
        ),
        "cadence_diversity_score": cadence_diversity_score,
        "party_concurrency_support": round(min(1.0, party_concurrency_support), 2),
        "distinct_event_types": distinct_event_types,
        "distinct_reward_pools": distinct_reward_pools,
        "promoted_actions": sum(1 for action in payload["scaffolded_actions"] if action["mode"] == "promote"),
        "held_actions": sum(1 for action in payload["scaffolded_actions"] if action["mode"] == "hold"),
        "estimated_completeness_percent": experience_percent,
        "fatigue_gap_score": fatigue_gap_score,
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("LIVEOPS_GOVERNOR")
    print(f"SCHEDULED_EVENTS={len(scheduled_events)}")
    print(f"PROMOTED_ACTIONS={summary['promoted_actions']}")
    print(f"HELD_ACTIONS={summary['held_actions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

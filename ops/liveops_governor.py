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
    rotation = scheduler.get("rotation", {})
    scheduled_events = scheduler.get("events", {})
    migration_required = int(rotation.get("dungeon_rotation_minutes", 0)) < 10

    action_id = f"liveops-{uuid.uuid4().hex[:12]}"
    payload = {
        "action_id": action_id,
        "created_at": created_at,
        "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
        "season_plan": {
            "rotation_minutes": int(rotation.get("dungeon_rotation_minutes", 0)),
            "event_count": len(scheduled_events),
            "broadcast_poll_seconds": int(rotation.get("lobby_broadcast_poll_seconds", 0)),
        },
        "scaffolded_actions": [
            {"action": "event_rotation", "mode": "promote", "event_ids": sorted(scheduled_events.keys())[:2]},
            {"action": "hotfix_window", "mode": "hold" if migration_required else "promote", "migration_plan_required": bool(migration_required)},
            {"action": "rollback_plan", "mode": "promote", "source": "append_only_lineage"},
        ],
        "consumer_signals": {
            "live_events_defined": len(events),
            "scheduled_events_defined": len(scheduled_events),
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
            "signature": payload["signature"],
        },
    )
    summary = {
        "created_at": created_at,
        "action_id": action_id,
        "migration_required": bool(migration_required),
        "scheduled_events": len(scheduled_events),
        "live_events_defined": len(events),
        "promoted_actions": sum(1 for action in payload["scaffolded_actions"] if action["mode"] == "promote"),
        "held_actions": sum(1 for action in payload["scaffolded_actions"] if action["mode"] == "hold"),
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

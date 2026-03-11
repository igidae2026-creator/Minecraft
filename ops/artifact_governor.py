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

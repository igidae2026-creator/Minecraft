#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"


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

        details.append(
            f"{server}: session_conflicts={session_conflicts} split_brain={split_brain} "
            f"transfer_failures={transfer_failures} transfer_quarantines={transfer_quarantines} "
            f"reconciliation={reconciliation} guild_drift={guild_drift} item_quarantine={item_quarantine} "
            f"exploit_incidents={exploit_incidents} instance_leaks={instance_leaks} "
            f"experiment_anomalies={experiment_anomalies} knowledge_records={knowledge_records}"
        )

    return totals, details


def main() -> int:
    totals, details = summarize_status()
    print("RUNTIME_SUMMARY")
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
    for detail in details:
        print(detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

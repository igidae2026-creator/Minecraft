#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from material_inventory import load_or_build_inventory


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUDIT = RUNTIME / "audit"
AUTONOMY = RUNTIME / "autonomy"
INVENTORY_PATH = AUDIT / "MATERIAL_INVENTORY.yml"
PARTITION_PATH = AUDIT / "RUNTIME_PARTITION.yml"
SUMMARY_PATH = AUTONOMY / "runtime_partition_summary.yml"


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


def classify_runtime_path(rel_path: str, material_class: str) -> tuple[str, str]:
    if any(token in rel_path for token in ("/control/", "/decisions/", "/artifact_proposals/", "/canonical_artifacts/")):
        return "canonical_snapshot", "governed_or_lineage_surface"
    if rel_path.endswith(".jsonl"):
        return "canonical_snapshot", "append_only_ledger"
    if any(token in rel_path for token in ("/supervisor/", "/core/jobs/", "/core/snapshots/", "/status/")):
        return "volatile_runtime", "live_runtime_state"
    if rel_path.endswith("_summary.yml") or rel_path.endswith("final_threshold_eval.json"):
        return "canonical_snapshot", "governed_summary_surface"
    if material_class == "append_only_runtime_truth":
        return "canonical_snapshot", "append_only_truth"
    return "archive_candidate", "derived_or_historical_snapshot"


def main() -> int:
    inventory, _inventory_summary = load_or_build_inventory(refresh=True)
    entries = inventory.get("entries", [])
    runtime_entries: list[dict[str, Any]] = []
    by_partition: dict[str, int] = {}
    by_role: dict[str, int] = {}

    for entry in entries:
        path = str(entry.get("path", ""))
        if not path.startswith("runtime_data/"):
            continue
        partition_class, role = classify_runtime_path(path, str(entry.get("material_class", "")))
        row = {
            "path": path,
            "material_class": entry.get("material_class", ""),
            "partition_class": partition_class,
            "role": role,
            "bytes": int(entry.get("bytes", 0)),
        }
        runtime_entries.append(row)
        by_partition[partition_class] = by_partition.get(partition_class, 0) + 1
        by_role[role] = by_role.get(role, 0) + 1

    payload = {
        "created_at": now_iso(),
        "counts": {
            "runtime_files": len(runtime_entries),
            "by_partition": by_partition,
            "by_role": by_role,
        },
        "entries": runtime_entries,
    }
    write_yaml(PARTITION_PATH, payload)
    summary = {
        "created_at": payload["created_at"],
        "runtime_files": len(runtime_entries),
        "volatile_runtime_files": by_partition.get("volatile_runtime", 0),
        "canonical_snapshot_files": by_partition.get("canonical_snapshot", 0),
        "archive_candidate_files": by_partition.get("archive_candidate", 0),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("RUNTIME_PARTITION")
    print(f"RUNTIME_FILES={summary['runtime_files']}")
    print(f"VOLATILE_RUNTIME_FILES={summary['volatile_runtime_files']}")
    print(f"CANONICAL_SNAPSHOT_FILES={summary['canonical_snapshot_files']}")
    print(f"ARCHIVE_CANDIDATE_FILES={summary['archive_candidate_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

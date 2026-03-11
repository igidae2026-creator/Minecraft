#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUDIT = RUNTIME / "audit"
INVENTORY_PATH = AUDIT / "MATERIAL_INVENTORY.yml"
SUMMARY_PATH = RUNTIME / "autonomy" / "material_inventory_summary.yml"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def classify(path: Path) -> tuple[str, str]:
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith("configs/"):
        return "canonical_source", "gameplay_or_policy_source"
    if rel.startswith("docs/"):
        return "governed_doc", "governance_or_operator_doc"
    if rel.startswith("ops/"):
        return "runtime_tooling", "operating_surface_code"
    if rel.startswith("tests/"):
        return "verification_surface", "test_or_contract"
    if rel.startswith("runtime_data/"):
        if "/control/" in rel or "/decisions/" in rel or rel.endswith(".jsonl"):
            return "append_only_runtime_truth", "lineage_or_ledger"
        if "/artifact_proposals/" in rel or "/canonical_artifacts/" in rel:
            return "governed_runtime_artifact", "proposal_or_canonical_artifact"
        return "runtime_snapshot", "derived_runtime_state"
    return "unclassified", "unknown"


def build_inventory() -> tuple[dict[str, Any], dict[str, Any]]:
    roots = ["configs", "docs", "ops", "tests", "runtime_data"]
    entries: list[dict[str, Any]] = []
    by_class: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for root_name in roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if "__pycache__" in rel.parts:
                continue
            material_class, role = classify(path)
            entry = {
                "path": rel.as_posix(),
                "material_class": material_class,
                "role": role,
                "bytes": path.stat().st_size,
            }
            entries.append(entry)
            by_class[material_class] = by_class.get(material_class, 0) + 1
            by_role[role] = by_role.get(role, 0) + 1

    payload = {
        "created_at": now_iso(),
        "roots": roots,
        "counts": {
            "total_files": len(entries),
            "by_class": by_class,
            "by_role": by_role,
        },
        "entries": entries,
    }
    write_yaml(INVENTORY_PATH, payload)
    summary = {
        "created_at": payload["created_at"],
        "total_files": len(entries),
        "canonical_source_files": by_class.get("canonical_source", 0),
        "governed_doc_files": by_class.get("governed_doc", 0),
        "runtime_tooling_files": by_class.get("runtime_tooling", 0),
        "verification_surface_files": by_class.get("verification_surface", 0),
        "append_only_runtime_truth_files": by_class.get("append_only_runtime_truth", 0),
        "runtime_snapshot_files": by_class.get("runtime_snapshot", 0),
    }
    write_yaml(SUMMARY_PATH, summary)
    return payload, summary


def load_or_build_inventory(*, refresh: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    if refresh or not INVENTORY_PATH.exists() or not SUMMARY_PATH.exists():
        return build_inventory()
    with INVENTORY_PATH.open("r", encoding="utf-8") as handle:
        inventory = yaml.safe_load(handle) or {}
    with SUMMARY_PATH.open("r", encoding="utf-8") as handle:
        summary = yaml.safe_load(handle) or {}
    return inventory, summary


def main() -> int:
    _payload, summary = build_inventory()
    print("MATERIAL_INVENTORY")
    print(f"TOTAL_FILES={summary['total_files']}")
    for key, value in summary.items():
        if key in {"created_at", "total_files"}:
            continue
        print(f"{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

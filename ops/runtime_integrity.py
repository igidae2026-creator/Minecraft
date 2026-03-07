#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"


def load_yaml(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    errors: list[str] = []

    artifacts = RUNTIME / "artifacts"
    policies = RUNTIME / "policies"
    item_authority = RUNTIME / "item_authority" / "owners"
    status_dir = RUNTIME / "status"

    for required in (artifacts, policies, item_authority, status_dir):
        if not required.exists():
            errors.append(f"missing_runtime_surface:{required.relative_to(ROOT)}")

    seen_item_instances: dict[str, str] = {}
    if item_authority.exists():
        for manifest_path in sorted(item_authority.glob("*.yml")):
            manifest = load_yaml(manifest_path) or {}
            owner_ref = manifest.get("owner_ref", "")
            items = manifest.get("items", {}) or {}
            for item_instance_id in items:
                previous = seen_item_instances.get(item_instance_id)
                if previous and previous != owner_ref:
                    errors.append(f"duplicate_item_instance:{item_instance_id}:{previous}:{owner_ref}")
                seen_item_instances[item_instance_id] = owner_ref

    if status_dir.exists():
        for status_path in sorted(status_dir.glob("*.yml")):
            status = load_yaml(status_path) or {}
            if status.get("safe_mode"):
                errors.append(f"safe_mode:{status_path.stem}:{status.get('safe_mode_reason', '')}")
            if status.get("reconciliation_mismatches", 0) > 0:
                errors.append(f"reconciliation_mismatch:{status_path.stem}")
            if status.get("item_ownership_conflicts", 0) > 0:
                errors.append(f"item_ownership_conflict:{status_path.stem}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("RUNTIME_INTEGRITY_OK")
    print(f"ARTIFACTS={len(list(artifacts.glob('*.yml'))) if artifacts.exists() else 0}")
    print(f"ITEM_MANIFESTS={len(list(item_authority.glob('*.yml'))) if item_authority.exists() else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

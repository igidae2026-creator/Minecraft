#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    issues: list[str] = []
    owners = RUNTIME / "item_authority" / "owners"
    seen: dict[str, str] = {}

    for manifest_path in sorted(owners.glob("*.yml")):
        manifest = load_yaml(manifest_path) or {}
        owner_ref = manifest.get("owner_ref", "")
        for item_instance_id in (manifest.get("items", {}) or {}):
            previous = seen.get(item_instance_id)
            if previous and previous != owner_ref:
                issues.append(f"duplicate_item_instance:{item_instance_id}:{previous}:{owner_ref}")
            seen[item_instance_id] = owner_ref

    for status_path in sorted((RUNTIME / "status").glob("*.yml")):
        status = load_yaml(status_path) or {}
        transfer = status.get("deterministic_transfer_service", {}) or {}
        session = status.get("session_authority_service", {}) or {}
        if status.get("reconciliation_mismatches", 0) > 0:
            issues.append(f"reconciliation_mismatch:{status_path.stem}")
        if status.get("guild_value_drift", 0) > 0:
            issues.append(f"guild_drift:{status_path.stem}")
        if status.get("replay_divergence", 0) > 0:
            issues.append(f"replay_divergence:{status_path.stem}")
        if transfer.get("quarantines", 0) > 0:
            issues.append(f"transfer_quarantine:{status_path.stem}")
        if session.get("split_brain_detections", 0) > 0:
            issues.append(f"split_brain:{status_path.stem}")

    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1

    print("RECONCILE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

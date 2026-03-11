#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
CONFIG = ROOT / "configs"
CONTROL_STATE = RUNTIME / "autonomy" / "control" / "state.yml"
SUMMARY_PATH = RUNTIME / "autonomy" / "runtime_integrity_summary.yml"
DEGRADED_DB_FALLBACK_REASONS = {
    "MySQL backend unavailable",
    "Unsafe degraded local-authority mode is disabled in production",
}


def load_yaml(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def main() -> int:
    errors: list[str] = []
    persistence = load_yaml(CONFIG / "persistence.yml") or {}
    fallback_enabled = bool((persistence.get("local_fallback", {}) or {}).get("enabled", False))
    fallback_writes = bool((persistence.get("local_fallback", {}) or {}).get("allow_writes_when_db_unavailable", False))

    artifacts = RUNTIME / "artifacts"
    policies = RUNTIME / "policies"
    experiments = RUNTIME / "experiments"
    incidents = RUNTIME / "incidents"
    coordination = RUNTIME / "coordination"
    knowledge = RUNTIME / "knowledge"
    artifact_proposals = RUNTIME / "artifact_proposals"
    canonical_artifacts = RUNTIME / "canonical_artifacts"
    audit = RUNTIME / "audit"
    content_pipeline = RUNTIME / "content_pipeline"
    economy_operations = RUNTIME / "economy_operations"
    anti_cheat = RUNTIME / "anti_cheat"
    live_ops = RUNTIME / "live_ops"
    content_volume = RUNTIME / "content_volume"
    item_authority = RUNTIME / "item_authority" / "owners"
    status_dir = RUNTIME / "status"
    control = load_yaml(CONTROL_STATE) or {}

    required_surfaces = [artifacts, policies, experiments, incidents, coordination, knowledge, artifact_proposals, canonical_artifacts, audit, item_authority, status_dir]
    if bool(control.get("autonomy_threshold_ready", False)):
        required_surfaces.extend([content_pipeline, economy_operations, anti_cheat, live_ops, content_volume])

    for required in required_surfaces:
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
            transfer = status.get("deterministic_transfer_service", {}) or {}
            session = status.get("session_authority_service", {}) or {}
            knowledge_index = status.get("runtime_knowledge_index", {}) or {}
            pressure_plane = status.get("pressure_control_plane", {}) or {}
            degraded_db_fallback = (
                status.get("safe_mode")
                and fallback_enabled
                and fallback_writes
                and status.get("safe_mode_reason", "") in DEGRADED_DB_FALLBACK_REASONS
            )
            if status.get("safe_mode") and not degraded_db_fallback:
                errors.append(f"safe_mode:{status_path.stem}:{status.get('safe_mode_reason', '')}")
            if status.get("reconciliation_mismatches", 0) > 0:
                errors.append(f"reconciliation_mismatch:{status_path.stem}")
            if status.get("item_ownership_conflicts", 0) > 0:
                errors.append(f"item_ownership_conflict:{status_path.stem}")
            if transfer.get("stale_load_rejections", 0) > 0:
                errors.append(f"stale_transfer_load:{status_path.stem}")
            if transfer.get("quarantines", 0) > 0:
                errors.append(f"transfer_quarantine:{status_path.stem}")
            if session.get("split_brain_detections", 0) > 0:
                errors.append(f"split_brain:{status_path.stem}")
            if knowledge_index.get("records", 0) <= 0:
                errors.append(f"knowledge_missing:{status_path.stem}")
            if pressure_plane.get("composite", 0) >= 1.0:
                errors.append(f"pressure_saturated:{status_path.stem}")

    if errors:
        write_yaml(
            SUMMARY_PATH,
            {
                "integrity_ok": False,
                "error_count": len(errors),
                "runtime_scale_confidence": 0.0,
                "status_file_count": len(list(status_dir.glob("*.yml"))) if status_dir.exists() else 0,
                "content_artifacts": len(list(content_pipeline.rglob('*.yml'))) if content_pipeline.exists() else 0,
                "liveops_artifacts": len(list(live_ops.glob('*.yml'))) if live_ops.exists() else 0,
            },
        )
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    status_count = len(list(status_dir.glob("*.yml"))) if status_dir.exists() else 0
    content_count = len(list(content_pipeline.rglob('*.yml'))) if content_pipeline.exists() else 0
    liveops_count = len(list(live_ops.glob('*.yml'))) if live_ops.exists() else 0
    canonical_count = len(list(canonical_artifacts.glob('*.yml'))) if canonical_artifacts.exists() else 0
    scale_readiness = round(
        min(
            1.0,
            (status_count / 5.0) * 0.25
            + min(1.0, content_count / 20.0) * 0.3
            + min(1.0, liveops_count / 6.0) * 0.2
            + min(1.0, canonical_count / 16.0) * 0.25,
        ),
        2,
    )
    write_yaml(
        SUMMARY_PATH,
        {
            "integrity_ok": True,
            "error_count": 0,
            "runtime_scale_confidence": scale_readiness,
            "status_file_count": status_count,
            "content_artifacts": content_count,
            "liveops_artifacts": liveops_count,
            "canonical_artifacts": canonical_count,
        },
    )
    print("RUNTIME_INTEGRITY_OK")
    print(f"ARTIFACTS={len(list(artifacts.glob('*.yml'))) if artifacts.exists() else 0}")
    print(f"ITEM_MANIFESTS={len(list(item_authority.glob('*.yml'))) if item_authority.exists() else 0}")
    print(f"EXPERIMENTS={len(list(experiments.glob('*.yml'))) if experiments.exists() else 0}")
    print(f"KNOWLEDGE={len(list(knowledge.glob('*.yml'))) if knowledge.exists() else 0}")
    print(f"ARTIFACT_PROPOSALS={len(list(artifact_proposals.glob('*.yml'))) if artifact_proposals.exists() else 0}")
    print(f"CANONICAL_ARTIFACTS={canonical_count}")
    print(f"CONTENT_ARTIFACTS={content_count}")
    print(f"ECONOMY_ARTIFACTS={len(list(economy_operations.glob('*.yml'))) if economy_operations.exists() else 0}")
    print(f"ANTI_CHEAT_ARTIFACTS={len(list(anti_cheat.glob('*.yml'))) if anti_cheat.exists() else 0}")
    print(f"LIVEOPS_ARTIFACTS={liveops_count}")
    print(f"CONTENT_VOLUME_ARTIFACTS={len(list(content_volume.glob('*.json'))) if content_volume.exists() else 0}")
    print(f"RUNTIME_SCALE_CONFIDENCE={scale_readiness}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

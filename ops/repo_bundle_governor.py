#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
AUDIT = RUNTIME / "audit"
SUMMARY_PATH = AUTONOMY / "repo_bundle_summary.yml"
BUNDLE_DIR = RUNTIME / "repo_bundles"


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


def state(ready: bool) -> str:
    return "complete" if ready else "partial"


def main() -> int:
    created_at = now_iso()
    control = load_yaml(AUTONOMY / "control" / "state.yml")
    content_bundle = load_yaml(AUTONOMY / "content_bundle_summary.yml")
    content_strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    content_soak = load_yaml(AUTONOMY / "content_soak_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    material_inventory = load_yaml(AUTONOMY / "material_inventory_summary.yml")
    runtime_partition = load_yaml(AUTONOMY / "runtime_partition_summary.yml")
    conformance = load_yaml(AUDIT / "COVERAGE_AUDIT.yml")

    bundles = {
        "governance_bundle": {
            "ready": len(conformance.get("gaps", [])) == 0,
            "evidence": f"conformance_gaps={len(conformance.get('gaps', []))}",
        },
        "autonomy_bundle": {
            "ready": bool(control.get("execution_threshold_ready", False))
            and bool(control.get("operational_threshold_ready", False))
            and bool(control.get("autonomy_threshold_ready", False))
            and bool(control.get("final_threshold_ready", False)),
            "evidence": f"steady_noop_streak={control.get('steady_noop_streak', 0)} control_final_ready={control.get('final_threshold_ready', False)}",
        },
        "content_bundle": {
            "ready": int(content_bundle.get("bundle_completed", 0)) >= int(content_bundle.get("bundle_total", 0)) > 0,
            "evidence": f"bundle_completed={content_bundle.get('bundle_completed', 0)} bundle_total={content_bundle.get('bundle_total', 0)}",
        },
        "recovery_audit_bundle": {
            "ready": int(content_strategy.get("recommended_repairs_count", 0)) >= 0 and bool(content_soak.get("content_soak_state", "")),
            "evidence": f"recommended_repairs={content_strategy.get('recommended_repairs_count', 0)} content_soak_state={content_soak.get('content_soak_state', '')}",
        },
        "docs_information_architecture_bundle": {
            "ready": (ROOT / "docs" / "DOCUMENTATION_MAP.md").exists()
            and (ROOT / "ops" / "DOCUMENT_AUDIT.md").exists()
            and (ROOT / "ops" / "OPS_COMMANDS.md").exists()
            and (ROOT / "ops" / "AUTONOMY_SURFACES.md").exists()
            and (ROOT / "ops" / "RECOVERY_PLAYBOOK.md").exists(),
            "evidence": "documentation_map_and_audit_present",
        },
        "player_experience_bundle": {
            "ready": (ROOT / "ops" / "CONTENT_COMPLETENESS_KR.md").exists()
            and float(player_experience.get("estimated_completeness_percent", 0.0)) >= 0.0
            and bool(player_experience.get("experience_state", "")),
            "evidence": (
                f"experience_percent={player_experience.get('estimated_completeness_percent', 0)} "
                f"experience_state={player_experience.get('experience_state', '')}"
            ),
        },
        "information_hygiene_bundle": {
            "ready": int(material_inventory.get("canonical_source_files", 0)) > 0 and int(runtime_partition.get("runtime_files", 0)) > 0,
            "evidence": f"canonical_source_files={material_inventory.get('canonical_source_files', 0)} runtime_files={runtime_partition.get('runtime_files', 0)}",
        },
    }

    completed = sum(1 for item in bundles.values() if item["ready"])
    payload = {
        "created_at": created_at,
        "bundle_total": len(bundles),
        "bundle_completed": completed,
        "bundle_completion_percent": round((completed / max(1, len(bundles))) * 100, 1),
        "bundles": {
            name: {"state": state(info["ready"]), "ready": bool(info["ready"]), "evidence": info["evidence"]}
            for name, info in bundles.items()
        },
    }
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    (BUNDLE_DIR / f"{created_at.replace(':', '').replace('-', '')}_repo_bundles.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "created_at": created_at,
        "bundle_total": payload["bundle_total"],
        "bundle_completed": payload["bundle_completed"],
        "bundle_completion_percent": payload["bundle_completion_percent"],
        "governance_bundle_state": payload["bundles"]["governance_bundle"]["state"],
        "autonomy_bundle_state": payload["bundles"]["autonomy_bundle"]["state"],
        "content_bundle_state": payload["bundles"]["content_bundle"]["state"],
        "recovery_audit_bundle_state": payload["bundles"]["recovery_audit_bundle"]["state"],
        "docs_information_architecture_bundle_state": payload["bundles"]["docs_information_architecture_bundle"]["state"],
        "player_experience_bundle_state": payload["bundles"]["player_experience_bundle"]["state"],
        "information_hygiene_bundle_state": payload["bundles"]["information_hygiene_bundle"]["state"],
    }
    write_yaml(SUMMARY_PATH, summary)
    print("REPO_BUNDLE_GOVERNOR")
    print(f"BUNDLE_COMPLETED={summary['bundle_completed']}")
    print(f"BUNDLE_TOTAL={summary['bundle_total']}")
    print(f"BUNDLE_COMPLETION_PERCENT={summary['bundle_completion_percent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

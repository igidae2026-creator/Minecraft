#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "governance"
RUNTIME = ROOT / "runtime_data"
AUDIT_DIR = RUNTIME / "audit"
COVERAGE_PATH = AUDIT_DIR / "COVERAGE_AUDIT.yml"
CONFLICT_PATH = AUDIT_DIR / "CONFLICT_LOG.jsonl"
CONTROL = RUNTIME / "autonomy" / "control" / "state.yml"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def main() -> int:
    created_at = now_iso()
    control = load_yaml(CONTROL)
    required = {
        "l0_rule_cards": DOCS / "RULE_CARDS.md",
        "l1_constitution": DOCS / "METAOS_CONSTITUTION.md",
        "a2_conflict_log": DOCS / "CONFLICT_LOG.md",
        "consumer_api": ROOT / "ops" / "consumer_api.py",
        "consumer_control": ROOT / "ops" / "consumer_control.py",
        "consumer_interventions": ROOT / "ops" / "consumer_interventions.py",
        "consumer_reporting": ROOT / "ops" / "consumer_reporting.py",
        "consumer_soak": ROOT / "ops" / "consumer_soak.py",
        "adapter_runtime_summary": ROOT / "ops" / "adapter_runtime_summary.py",
        "metaos_conformance": ROOT / "ops" / "metaos_conformance.py",
        "content_governor": ROOT / "ops" / "content_governor.py",
        "economy_governor": ROOT / "ops" / "economy_governor.py",
        "anti_cheat_governor": ROOT / "ops" / "anti_cheat_governor.py",
        "liveops_governor": ROOT / "ops" / "liveops_governor.py",
        "gameplay_progression_governor": ROOT / "ops" / "gameplay_progression_governor.py",
        "content_volume_governor": ROOT / "ops" / "content_volume_governor.py",
        "engagement_fatigue_governor": ROOT / "ops" / "engagement_fatigue_governor.py",
        "service_responsiveness_governor": ROOT / "ops" / "service_responsiveness_governor.py",
        "material_inventory": ROOT / "ops" / "material_inventory.py",
        "runtime_partition_governor": ROOT / "ops" / "runtime_partition_governor.py",
        "content_strategy_governor": ROOT / "ops" / "content_strategy_governor.py",
        "content_soak_governor": ROOT / "ops" / "content_soak_governor.py",
        "content_bundle_governor": ROOT / "ops" / "content_bundle_governor.py",
        "repo_bundle_governor": ROOT / "ops" / "repo_bundle_governor.py",
        "minecraft_bundle_governor": ROOT / "ops" / "minecraft_bundle_governor.py",
        "minecraft_strategy_governor": ROOT / "ops" / "minecraft_strategy_governor.py",
        "minecraft_soak_governor": ROOT / "ops" / "minecraft_soak_governor.py",
        "player_experience_governor": ROOT / "ops" / "player_experience_governor.py",
        "player_experience_soak_governor": ROOT / "ops" / "player_experience_soak_governor.py",
        "final_threshold_eval": ROOT / "ops" / "final_threshold_eval.py",
        "final_threshold_repair": ROOT / "ops" / "final_threshold_repair.py",
        "runtime_summary": ROOT / "ops" / "runtime_summary.py",
        "metrics_exporter": ROOT / "ops" / "metrics_exporter.sh",
        "documentation_map": ROOT / "docs" / "DOCUMENTATION_MAP.md",
        "document_audit": ROOT / "ops" / "DOCUMENT_AUDIT.md",
        "content_bundle_upper_bound": ROOT / "ops" / "CONTENT_BUNDLE_UPPER_BOUND.md",
        "repo_bundle_upper_bound": ROOT / "ops" / "REPO_BUNDLE_UPPER_BOUND.md",
        "minecraft_bundle_upper_bound": ROOT / "ops" / "MINECRAFT_BUNDLE_UPPER_BOUND.md",
        "content_completeness_kr": ROOT / "ops" / "CONTENT_COMPLETENESS_KR.md",
    }
    gaps = [name for name, path in required.items() if not path.exists()]
    payload = {
        "created_at": created_at,
        "gaps": gaps,
        "coverage": {name: path.exists() for name, path in required.items()},
        "thresholds": {
            "execution": bool(control.get("execution_threshold_ready", False)),
            "operational": bool(control.get("operational_threshold_ready", False)),
            "autonomy": bool(control.get("autonomy_threshold_ready", False)),
            "final": bool(control.get("final_threshold_ready", False)),
        },
        "repo_mapping": {
            "consumer_layer": [name for name in required if name.startswith("consumer_")],
            "adapter_layer": [name for name in required if name.startswith("adapter_")],
            "governance_layer": ["l0_rule_cards", "l1_constitution", "a2_conflict_log"],
        },
    }
    write_yaml(COVERAGE_PATH, payload)
    for tension in (
        "runtime convenience vs exploration identity",
        "aggressive rollout vs fail-closed policy",
        "consumer specificity vs generic core",
        "fast onboarding vs replayable governance",
    ):
        append_jsonl(
            CONFLICT_PATH,
            {
                "created_at": created_at,
                "tension": tension,
                "status": "tracked",
                "steady_noop_streak": int(control.get("steady_noop_streak", 0)),
            },
        )
    print("METAOS_CONFORMANCE")
    print(f"GAPS={len(gaps)}")
    print(f"CONFLICTS=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

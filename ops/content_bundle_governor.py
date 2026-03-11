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
CONTROL_PATH = AUTONOMY / "control" / "state.yml"
CONTENT_SUMMARY_PATH = AUTONOMY / "content_governor_summary.yml"
CONTENT_STRATEGY_PATH = AUTONOMY / "content_strategy_summary.yml"
CONTENT_SOAK_PATH = AUTONOMY / "content_soak_summary.yml"
ARTIFACT_SUMMARY_PATH = AUTONOMY / "artifact_governor_summary.yml"
FINAL_EVAL_PATH = AUTONOMY / "final_threshold_eval.json"
SUMMARY_PATH = AUTONOMY / "content_bundle_summary.yml"
BUNDLE_DIR = RUNTIME / "content_bundles"


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


def bundle_state(ready: bool) -> str:
    return "complete" if ready else "partial"


def canonical_registry_contains(registry: list[Any], artifact_class: str) -> bool:
    for item in registry or []:
        if isinstance(item, str) and artifact_class in item:
            return True
        if isinstance(item, dict) and artifact_class in item.values():
            return True
    return False


def main() -> int:
    created_at = now_iso()
    control = load_yaml(CONTROL_PATH)
    content = load_yaml(CONTENT_SUMMARY_PATH)
    strategy = load_yaml(CONTENT_STRATEGY_PATH)
    soak = load_yaml(CONTENT_SOAK_PATH)
    artifact = load_yaml(ARTIFACT_SUMMARY_PATH)

    canonical_registry = artifact.get("canonical_registry", []) or []
    bundles = {
        "content_depth": {
            "ready": int(content.get("generated", 0)) >= 12 and len(content.get("by_type", {}) or {}) >= 8,
            "evidence": f"generated={content.get('generated', 0)} families={len(content.get('by_type', {}) or {})}",
        },
        "content_evaluation": {
            "ready": float(content.get("average_quality_score", 0.0)) > 0 and canonical_registry_contains(canonical_registry, "content_quality_profile"),
            "evidence": f"avg_quality={content.get('average_quality_score', 0)} canonical={canonical_registry_contains(canonical_registry, 'content_quality_profile')}",
        },
        "player_facing_depth": {
            "ready": float(content.get("first_loop_coverage_score", 0.0)) >= 2.0 and float(content.get("social_loop_density", 0.0)) >= 1.5,
            "evidence": (
                f"first_loop_coverage={content.get('first_loop_coverage_score', 0)} "
                f"social_loop_density={content.get('social_loop_density', 0)}"
            ),
        },
        "portfolio_strategy": {
            "ready": bool(strategy.get("next_focus_csv", "")) and canonical_registry_contains(canonical_registry, "content_portfolio_strategy"),
            "evidence": f"next_focus={strategy.get('next_focus_csv', '')}",
        },
        "live_data_absorption": {
            "ready": float(strategy.get("runtime_event_join_avg", 0.0)) > 0 and float(strategy.get("runtime_queue_avg", 0.0)) > 0,
            "evidence": f"queue_avg={strategy.get('runtime_queue_avg', 0)} event_join_avg={strategy.get('runtime_event_join_avg', 0)}",
        },
        "recovery_coupling": {
            "ready": int(strategy.get("recommended_repairs_count", 0)) > 0,
            "evidence": f"recommended_repairs={strategy.get('recommended_repairs_count', 0)}",
        },
        "long_soak_canonicalization": {
            "ready": bool(soak.get("content_soak_state", "")) and canonical_registry_contains(canonical_registry, "content_soak_report") and bool(control.get("final_threshold_ready", False)),
            "evidence": f"content_soak_state={soak.get('content_soak_state', '')} control_final_ready={control.get('final_threshold_ready', False)}",
        },
    }

    completed = sum(1 for bundle in bundles.values() if bundle["ready"])
    payload = {
        "created_at": created_at,
        "bundle_total": len(bundles),
        "bundle_completed": completed,
        "bundle_completion_percent": round((completed / max(1, len(bundles))) * 100, 1),
        "bundles": {
            name: {
                "state": bundle_state(info["ready"]),
                "ready": bool(info["ready"]),
                "evidence": info["evidence"],
            }
            for name, info in bundles.items()
        },
    }
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    (BUNDLE_DIR / f"{created_at.replace(':', '').replace('-', '')}_content_bundles.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "created_at": created_at,
        "bundle_total": payload["bundle_total"],
        "bundle_completed": payload["bundle_completed"],
        "bundle_completion_percent": payload["bundle_completion_percent"],
        "content_depth_state": payload["bundles"]["content_depth"]["state"],
        "content_evaluation_state": payload["bundles"]["content_evaluation"]["state"],
        "player_facing_depth_state": payload["bundles"]["player_facing_depth"]["state"],
        "portfolio_strategy_state": payload["bundles"]["portfolio_strategy"]["state"],
        "live_data_absorption_state": payload["bundles"]["live_data_absorption"]["state"],
        "recovery_coupling_state": payload["bundles"]["recovery_coupling"]["state"],
        "long_soak_canonicalization_state": payload["bundles"]["long_soak_canonicalization"]["state"],
    }
    write_yaml(SUMMARY_PATH, summary)
    print("CONTENT_BUNDLE_GOVERNOR")
    print(f"BUNDLE_COMPLETED={summary['bundle_completed']}")
    print(f"BUNDLE_TOTAL={summary['bundle_total']}")
    print(f"BUNDLE_COMPLETION_PERCENT={summary['bundle_completion_percent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
SUMMARY_PATH = AUTONOMY / "minecraft_bundle_summary.yml"
BUNDLE_DIR = RUNTIME / "minecraft_bundles"


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


def status_rollup() -> dict[str, float]:
    totals = {
        "status_files": 0,
        "dungeon_completed": 0,
        "event_started": 0,
        "guild_joined": 0,
        "rivalry_match": 0,
        "reconciliation_mismatches": 0,
        "item_ownership_conflicts": 0,
    }
    for path in sorted((RUNTIME / "status").glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1
        for key in totals:
            if key == "status_files":
                continue
            totals[key] += float(payload.get(key, 0) or 0)
    return totals


def main() -> int:
    created_at = now_iso()
    control = load_yaml(AUTONOMY / "control" / "state.yml")
    conformance = load_yaml(AUDIT / "COVERAGE_AUDIT.yml")
    content = load_yaml(AUTONOMY / "content_governor_summary.yml")
    strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    soak = load_yaml(AUTONOMY / "content_soak_summary.yml")
    content_bundle = load_yaml(AUTONOMY / "content_bundle_summary.yml")
    repo_bundle = load_yaml(AUTONOMY / "repo_bundle_summary.yml")
    economy = load_yaml(AUTONOMY / "economy_governor_summary.yml")
    anti_cheat = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    player_experience_soak = load_yaml(AUTONOMY / "player_experience_soak_summary.yml")
    status = status_rollup()
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_state = str(player_experience.get("experience_state", ""))
    first_session_strength = float(player_experience.get("first_session_strength", 0.0))
    trust_pull = float(player_experience.get("trust_pull", 0.0))
    player_experience_soak_state = str(player_experience_soak.get("player_experience_soak_state", ""))
    boost_reentry = bool(liveops.get("boost_reentry", False))
    cadence_diversity_score = float(liveops.get("cadence_diversity_score", 0.0))
    promoted_actions = int(liveops.get("promoted_actions", 0))
    social_liveops_ready = (
        promoted_actions >= 3
        and float(strategy.get("runtime_event_join_avg", 0.0)) >= 1200.0
        and experience_percent >= 45.0
        and (
            boost_reentry
            or cadence_diversity_score >= 0.9
            or status.get("guild_joined", 0) > 0
            or status.get("rivalry_match", 0) > 0
        )
    )

    bundles = {
        "gameplay_progression_bundle": {
            "ready": int(content.get("generated", 0)) >= 12
            and float(content.get("average_depth_score", 0.0)) > 0
            and int(status.get("status_files", 0)) >= 5
            and (status.get("dungeon_completed", 0) > 0 or status.get("event_started", 0) > 0),
            "evidence": (
                f"generated={content.get('generated', 0)} "
                f"avg_depth={content.get('average_depth_score', 0)} "
                f"dungeon_completed={status.get('dungeon_completed', 0)} "
                f"event_started={status.get('event_started', 0)}"
            ),
        },
        "economy_market_bundle": {
            "ready": float(economy.get("inflation_ratio", 0.0)) > 0
            and str(economy.get("action", "")) in {"adjust", "observe"}
            and float(strategy.get("runtime_return_player_reward_avg", 0.0)) > 0,
            "evidence": (
                f"inflation_ratio={economy.get('inflation_ratio', 0)} "
                f"economy_action={economy.get('action', '')} "
                f"return_player_reward_avg={strategy.get('runtime_return_player_reward_avg', 0)}"
            ),
        },
        "social_liveops_bundle": {
            "ready": social_liveops_ready,
            "evidence": (
                f"liveops_promoted={promoted_actions} "
                f"boost_reentry={boost_reentry} "
                f"cadence_diversity_score={cadence_diversity_score} "
                f"event_join_avg={strategy.get('runtime_event_join_avg', 0)} "
                f"experience_percent={experience_percent} "
                f"next_focus={strategy.get('next_focus_csv', '')}"
            ),
        },
        "player_experience_bundle": {
            "ready": experience_percent >= 40.0 and experience_state in {"mid", "advanced"} and first_session_strength >= 0.9 and trust_pull >= 0.7 and player_experience_soak_state in {"observe", "stable"},
            "evidence": (
                f"experience_percent={experience_percent} "
                f"experience_state={experience_state} "
                f"first_session_strength={first_session_strength} "
                f"trust_pull={trust_pull} "
                f"player_experience_soak_state={player_experience_soak_state}"
            ),
        },
        "anti_cheat_recovery_bundle": {
            "ready": int(anti_cheat.get("sandbox_cases", 0)) >= 1
            and bool(soak.get("content_soak_state", ""))
            and int(status.get("reconciliation_mismatches", 0)) == 0
            and int(status.get("item_ownership_conflicts", 0)) == 0,
            "evidence": (
                f"sandbox_cases={anti_cheat.get('sandbox_cases', 0)} "
                f"content_soak_state={soak.get('content_soak_state', '')} "
                f"reconciliation_mismatches={status.get('reconciliation_mismatches', 0)} "
                f"item_conflicts={status.get('item_ownership_conflicts', 0)} "
                f"progression_protection_score={anti_cheat.get('progression_protection_score', 0)}"
            ),
        },
        "governance_autonomy_bundle": {
            "ready": bool(control.get("final_threshold_ready", False))
            and len(conformance.get("gaps", [])) == 0
            and int(content_bundle.get("bundle_completed", 0)) >= int(content_bundle.get("bundle_total", 0)) > 0
            and int(repo_bundle.get("bundle_completed", 0)) >= int(repo_bundle.get("bundle_total", 0)) > 0,
            "evidence": (
                f"final_threshold_ready={control.get('final_threshold_ready', False)} "
                f"conformance_gaps={len(conformance.get('gaps', []))} "
                f"content_bundle={content_bundle.get('bundle_completed', 0)}/{content_bundle.get('bundle_total', 0)} "
                f"repo_bundle={repo_bundle.get('bundle_completed', 0)}/{repo_bundle.get('bundle_total', 0)}"
            ),
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
    (BUNDLE_DIR / f"{created_at.replace(':', '').replace('-', '')}_minecraft_bundles.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "created_at": created_at,
        "bundle_total": payload["bundle_total"],
        "bundle_completed": payload["bundle_completed"],
        "bundle_completion_percent": payload["bundle_completion_percent"],
        "gameplay_progression_bundle_state": payload["bundles"]["gameplay_progression_bundle"]["state"],
        "economy_market_bundle_state": payload["bundles"]["economy_market_bundle"]["state"],
        "social_liveops_bundle_state": payload["bundles"]["social_liveops_bundle"]["state"],
        "player_experience_bundle_state": payload["bundles"]["player_experience_bundle"]["state"],
        "anti_cheat_recovery_bundle_state": payload["bundles"]["anti_cheat_recovery_bundle"]["state"],
        "governance_autonomy_bundle_state": payload["bundles"]["governance_autonomy_bundle"]["state"],
    }
    write_yaml(SUMMARY_PATH, summary)
    print("MINECRAFT_BUNDLE_GOVERNOR")
    print(f"BUNDLE_COMPLETED={summary['bundle_completed']}")
    print(f"BUNDLE_TOTAL={summary['bundle_total']}")
    print(f"BUNDLE_COMPLETION_PERCENT={summary['bundle_completion_percent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

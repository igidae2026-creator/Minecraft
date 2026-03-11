#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
CONFIG = ROOT / "configs"
OUTPUT_PATH = AUTONOMY / "final_threshold_eval.json"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()[-limit:]
    payloads: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payloads.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return payloads


def file_has_tracked_lines(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def evaluate() -> dict[str, Any]:
    control = load_yaml(AUTONOMY / "control" / "state.yml")
    heartbeat = json.loads((RUNTIME / "autonomy" / "supervisor" / "heartbeat.json").read_text(encoding="utf-8")) if (RUNTIME / "autonomy" / "supervisor" / "heartbeat.json").exists() else {}
    conformance = load_yaml(RUNTIME / "audit" / "COVERAGE_AUDIT.yml")
    artifact_governor = load_yaml(AUTONOMY / "artifact_governor_summary.yml")
    content_governor = load_yaml(AUTONOMY / "content_governor_summary.yml")
    economy_governor = load_yaml(AUTONOMY / "economy_governor_summary.yml")
    anti_cheat_governor = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    liveops_governor = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    autonomy_cfg = load_yaml(CONFIG / "autonomy.yml")
    event_tail = tail_jsonl(AUTONOMY / "core" / "event_log.jsonl", 48)
    status_dir = RUNTIME / "status"

    quality_targets = (autonomy_cfg.get("quality_targets", {}) or {})
    final_cfg = (autonomy_cfg.get("final_threshold", {}) or {})
    required_streak = int(final_cfg.get("required_steady_noop_streak", 12))
    steady_streak = int(control.get("steady_noop_streak", 0))

    total_status = 0
    hard_faults = 0
    replay_divergence = 0
    transfer_quarantines = 0
    split_brain = 0
    consumer_health_signals = 0
    for status_path in sorted(status_dir.glob("*.yml")):
        status = load_yaml(status_path)
        total_status += 1
        transfer_quarantines += int((status.get("deterministic_transfer_service", {}) or {}).get("quarantines", 0))
        split_brain += int((status.get("session_authority_service", {}) or {}).get("split_brain_detections", 0))
        replay_divergence += int(status.get("replay_divergence", 0))
        hard_faults += int(status.get("reconciliation_mismatches", 0))
        hard_faults += int(status.get("item_ownership_conflicts", 0))
        consumer_health_signals += int(status.get("queue_size", 0)) + int(status.get("dungeon_completed", 0)) + int(status.get("event_started", 0))

    seeded = any(event.get("event_type") == "queue.seeded" for event in event_tail)
    loop_finished = any(event.get("event_type") == "loop.finished" for event in event_tail)
    jobs_done = {event.get("payload", {}).get("job_type", "") for event in event_tail if event.get("event_type") == "job.done"}
    required_recent_jobs = {
        "autonomous_quality_loop",
        "runtime_summary",
        "content_governor",
        "economy_governor",
        "anti_cheat_governor",
        "liveops_governor",
    }

    criteria: dict[str, tuple[bool, str, str, list[str]]] = {
        "closed_loop_complete": (
            seeded and loop_finished and heartbeat.get("last_status") == "ok",
            "queue.seeded / loop.finished / heartbeat ok not all present",
            f"seeded={seeded} loop_finished={loop_finished} heartbeat_status={heartbeat.get('last_status', '')}",
            ["validate_runtime_truth", "reconcile_runtime", "autonomous_quality_loop"],
        ),
        "quality_gate_fail_closed": (
            transfer_quarantines == 0 and split_brain == 0 and hard_faults == 0 and bool((autonomy_cfg.get("controls", {}) or {}).get("fail_closed_on_conflict", False)),
            "fail-closed blockers remain or control missing",
            f"transfer_quarantines={transfer_quarantines} split_brain={split_brain} hard_faults={hard_faults}",
            ["runtime_integrity", "reconcile_runtime", "autonomous_quality_loop"],
        ),
        "append_only_truth_replayability": (
            file_has_tracked_lines(AUTONOMY / "control" / "lineage.jsonl")
            and len(list((AUTONOMY / "decisions").glob("*.yml"))) > 0
            and file_has_tracked_lines(RUNTIME / "audit" / "CONFLICT_LOG.jsonl")
            and replay_divergence == 0,
            "lineage/replayability surface is incomplete or diverged",
            f"lineage_exists={file_has_tracked_lines(AUTONOMY / 'control' / 'lineage.jsonl')} decisions={len(list((AUTONOMY / 'decisions').glob('*.yml')))} replay_divergence={replay_divergence}",
            ["metaos_conformance", "artifact_governor"],
        ),
        "metaos_identity_preserved": (
            len(conformance.get("gaps", [])) == 0 and file_has_tracked_lines(ROOT / "docs" / "governance" / "RULE_CARDS.md") and file_has_tracked_lines(ROOT / "docs" / "governance" / "METAOS_CONSTITUTION.md"),
            "MetaOS governance surface is incomplete",
            f"conformance_gaps={len(conformance.get('gaps', []))}",
            ["metaos_conformance"],
        ),
        "consumer_and_migration_stability": (
            total_status >= 5 and consumer_health_signals > 0 and len(artifact_governor.get("canonical_registry", [])) >= 1,
            "consumer lifecycle or governed promotion surface is weak",
            f"status_files={total_status} consumer_health_signals={consumer_health_signals} canonical_artifacts={len(artifact_governor.get('canonical_registry', []))}",
            ["artifact_governor", "metaos_conformance"],
        ),
        "queue_supervisor_soak_reporting_stable": (
            heartbeat.get("queue_pending", 1) == 0 and heartbeat.get("last_status") == "ok" and (not heartbeat.get("active_soak") or control.get("last_mode") in {"hold", "promote", "noop", "apply"}),
            "queue/supervisor/control state is not stable",
            f"queue_pending={heartbeat.get('queue_pending', '')} active_soak={heartbeat.get('active_soak', '')} last_mode={control.get('last_mode', '')}",
            ["autonomous_quality_loop", "runtime_summary"],
        ),
        "expansion_policy_handled": (
            int(content_governor.get("generated", 0)) > 0 and int(liveops_governor.get("promoted_actions", 0)) >= 1,
            "content or live-ops expansion artifacts are missing",
            f"content_generated={content_governor.get('generated', 0)} liveops_promoted={liveops_governor.get('promoted_actions', 0)}",
            ["content_governor", "liveops_governor"],
        ),
        "long_soak_steady_noop": (
            steady_streak >= required_streak and bool(control.get("final_threshold_ready", False)),
            "steady/noop soak has not converged long enough",
            f"steady_noop_streak={steady_streak} required={required_streak} final_threshold_ready={bool(control.get('final_threshold_ready', False))}",
            ["autonomous_quality_loop"],
        ),
        "fault_injection_recovery_or_safe_block": (
            transfer_quarantines == 0 and split_brain == 0 and hard_faults == 0,
            "fault recovery or safe block is not proven cleanly",
            f"transfer_quarantines={transfer_quarantines} split_brain={split_brain} hard_faults={hard_faults}",
            ["reconcile_runtime", "runtime_integrity"],
        ),
        "human_marginal_gain_near_zero": (
            bool(control.get("final_threshold_ready", False)) and control.get("last_mode") in {"noop", "promote"} and steady_streak >= required_streak,
            "human intervention could still materially improve runtime",
            f"last_mode={control.get('last_mode', '')} steady_noop_streak={steady_streak}",
            ["autonomous_quality_loop"],
        ),
        "new_scope_authority_policy_inputs_auto_handled": (
            required_recent_jobs.issubset(jobs_done),
            "new scope/policy inputs are not all processed in the recent loop",
            f"recent_jobs_done={sorted(job for job in jobs_done if job)}",
            ["content_governor", "economy_governor", "anti_cheat_governor", "liveops_governor", "metaos_conformance"],
        ),
        "reporting_and_state_transitions_closed_loop": (
            file_has_tracked_lines(AUTONOMY / "artifact_governor_summary.yml") and file_has_tracked_lines(AUTONOMY / "content_governor_summary.yml") and file_has_tracked_lines(AUTONOMY / "economy_governor_summary.yml"),
            "reporting/control-state surface is incomplete",
            "artifact/content/economy summaries missing",
            ["runtime_summary", "content_governor", "economy_governor"],
        ),
        "market_consumer_feedback_generates_next_work": (
            float(economy_governor.get("inflation_ratio", 0.0)) <= float(quality_targets.get("economy_inflation_ratio_warning", 1.35))
            and int(anti_cheat_governor.get("sandbox_cases", 0)) >= 1
            and int(content_governor.get("generated", 0)) >= 1,
            "market/economy/consumer feedback loop is not fully linked to next work",
            f"inflation_ratio={economy_governor.get('inflation_ratio', 0.0)} sandbox_cases={anti_cheat_governor.get('sandbox_cases', 0)} content_generated={content_governor.get('generated', 0)}",
            ["economy_governor", "anti_cheat_governor", "content_governor"],
        ),
    }

    failed_criteria = [name for name, criterion in criteria.items() if not criterion[0]]
    blocking_evidence = [f"{name}:{criterion[2]}" for name, criterion in criteria.items() if not criterion[0]]
    next_required_repairs: list[str] = []
    for name, criterion in criteria.items():
        if criterion[0]:
            continue
        for repair in criterion[3]:
            if repair not in next_required_repairs:
                next_required_repairs.append(repair)

    quality_lift = min(1.0, round(len(failed_criteria) * 0.08 + (0.12 if failed_criteria else 0.0), 3))
    if bool(control.get("final_threshold_ready", False)) and steady_streak >= required_streak:
        quality_lift = 0.02 if failed_criteria else 0.0

    return {
        "final_threshold_ready": len(failed_criteria) == 0,
        "failed_criteria": failed_criteria,
        "blocking_evidence": blocking_evidence,
        "next_required_repairs": next_required_repairs,
        "quality_lift_if_human_intervenes": quality_lift,
    }


def main() -> int:
    payload = evaluate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print("FINAL_THRESHOLD_EVAL")
    print(f"FINAL_THRESHOLD_READY={1 if payload['final_threshold_ready'] else 0}")
    print(f"FAILED_CRITERIA={len(payload['failed_criteria'])}")
    print(f"QUALITY_LIFT_IF_HUMAN_INTERVENES={payload['quality_lift_if_human_intervenes']}")
    for criterion in payload["failed_criteria"]:
        print(f"FAILED={criterion}")
    for repair in payload["next_required_repairs"]:
        print(f"REPAIR={repair}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

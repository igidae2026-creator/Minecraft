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
CONTROL_PATH = AUTONOMY / "control" / "state.yml"
HEARTBEAT_PATH = AUTONOMY / "supervisor" / "heartbeat.json"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except Exception:
        if path == CONTROL_PATH:
            return load_control_state_fallback(path)
        return {}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"{}", "[]"}:
        return {} if value == "{}" else []
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("'\"")


def load_control_state_fallback(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    current_map: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if not raw.startswith(" "):
            current_map = None
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                payload[key] = {}
                current_map = key
                continue
            payload[key] = parse_scalar(value)
            continue
        if current_map and raw.startswith("  ") and not raw.lstrip().startswith("- ") and ":" in raw:
            key, value = raw.strip().split(":", 1)
            payload.setdefault(current_map, {})[key.strip()] = parse_scalar(value)
    return payload


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


def canonical_registry_contains(registry: list[Any], artifact_class: str) -> bool:
    for item in registry or []:
        if isinstance(item, str) and artifact_class in item:
            return True
        if isinstance(item, dict) and artifact_class in item.values():
            return True
    return False


def output_is_stale() -> bool:
    if not OUTPUT_PATH.exists():
        return True
    output_mtime = OUTPUT_PATH.stat().st_mtime
    dependency_paths = [
        CONTROL_PATH,
        HEARTBEAT_PATH,
        AUTONOMY / "artifact_governor_summary.yml",
        AUTONOMY / "content_strategy_summary.yml",
        AUTONOMY / "content_soak_summary.yml",
        AUTONOMY / "content_bundle_summary.yml",
        AUTONOMY / "repo_bundle_summary.yml",
        AUTONOMY / "minecraft_bundle_summary.yml",
        AUTONOMY / "minecraft_strategy_summary.yml",
        AUTONOMY / "minecraft_soak_summary.yml",
        AUTONOMY / "player_experience_summary.yml",
        AUTONOMY / "player_experience_soak_summary.yml",
        AUTONOMY / "engagement_fatigue_summary.yml",
        RUNTIME / "audit" / "COVERAGE_AUDIT.yml",
    ]
    newest_dependency = max((path.stat().st_mtime for path in dependency_paths if path.exists()), default=0.0)
    if newest_dependency > output_mtime:
        return True
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    control = load_yaml(CONTROL_PATH)
    if bool(control.get("final_threshold_ready", False)) and not bool(payload.get("final_threshold_ready", False)):
        return True
    return False


def evaluate() -> dict[str, Any]:
    control = load_yaml(CONTROL_PATH)
    heartbeat = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8")) if HEARTBEAT_PATH.exists() else {}
    conformance = load_yaml(RUNTIME / "audit" / "COVERAGE_AUDIT.yml")
    artifact_governor = load_yaml(AUTONOMY / "artifact_governor_summary.yml")
    content_governor = load_yaml(AUTONOMY / "content_governor_summary.yml")
    economy_governor = load_yaml(AUTONOMY / "economy_governor_summary.yml")
    anti_cheat_governor = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    liveops_governor = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    content_strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    content_soak = load_yaml(AUTONOMY / "content_soak_summary.yml")
    repo_bundle = load_yaml(AUTONOMY / "repo_bundle_summary.yml")
    minecraft_bundle = load_yaml(AUTONOMY / "minecraft_bundle_summary.yml")
    minecraft_strategy = load_yaml(AUTONOMY / "minecraft_strategy_summary.yml")
    minecraft_soak = load_yaml(AUTONOMY / "minecraft_soak_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    player_experience_soak = load_yaml(AUTONOMY / "player_experience_soak_summary.yml")
    engagement_fatigue = load_yaml(AUTONOMY / "engagement_fatigue_summary.yml")
    canonical_registry = artifact_governor.get("canonical_registry", []) or []
    autonomy_cfg = load_yaml(CONFIG / "autonomy.yml")
    event_tail = tail_jsonl(AUTONOMY / "core" / "event_log.jsonl", 160)
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
    heartbeat_status = str(heartbeat.get("last_status", ""))
    queue_pending = int(heartbeat.get("queue_pending", 0) or 0)
    actively_processing = heartbeat_status == "running" and queue_pending <= 6
    steady_cycle_processing = (
        heartbeat_status == "running"
        and queue_pending <= 40
        and str(control.get("last_regime", "")) == "steady"
        and str(control.get("last_mode", "")) == "noop"
        and bool(control.get("final_threshold_ready", False))
    )
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
            seeded and (loop_finished or actively_processing) and heartbeat_status in {"ok", "running"},
            "queue.seeded / loop.finished / heartbeat ok not all present",
            f"seeded={seeded} loop_finished={loop_finished} heartbeat_status={heartbeat_status} queue_pending={queue_pending}",
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
            ((queue_pending == 0 and heartbeat_status == "ok") or actively_processing or steady_cycle_processing)
            and (not heartbeat.get("active_soak") or control.get("last_mode") in {"hold", "promote", "noop", "apply"}),
            "queue/supervisor/control state is not stable",
            f"queue_pending={queue_pending} heartbeat_status={heartbeat_status} active_soak={heartbeat.get('active_soak', '')} last_mode={control.get('last_mode', '')}",
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
        "content_strategy_canonicalized": (
            bool(content_strategy.get("next_focus_csv", ""))
            and int(content_strategy.get("recommended_repairs_count", 0)) >= 0
            and canonical_registry_contains(canonical_registry, "content_portfolio_strategy"),
            "content strategy is not yet governed as a canonical operating artifact",
            f"next_focus_csv={content_strategy.get('next_focus_csv', '')} canonical_registry={canonical_registry}",
            ["content_strategy_governor", "artifact_governor"],
        ),
        "content_long_soak_governed": (
            bool(content_soak.get("content_soak_state", ""))
            and canonical_registry_contains(canonical_registry, "content_soak_report"),
            "content soak state is not yet governed as a canonical operating artifact",
            f"content_soak_state={content_soak.get('content_soak_state', '')} canonical_registry={canonical_registry}",
            ["content_soak_governor", "artifact_governor"],
        ),
        "repo_and_minecraft_bundle_governed": (
            int(repo_bundle.get("bundle_completed", 0)) >= int(repo_bundle.get("bundle_total", 0)) > 0
            and int(minecraft_bundle.get("bundle_completed", 0)) >= int(minecraft_bundle.get("bundle_total", 0)) > 0,
            "large-bundle repo or minecraft surface is incomplete",
            (
                f"repo_bundle={repo_bundle.get('bundle_completed', 0)}/{repo_bundle.get('bundle_total', 0)} "
                f"minecraft_bundle={minecraft_bundle.get('bundle_completed', 0)}/{minecraft_bundle.get('bundle_total', 0)}"
            ),
            ["repo_bundle_governor", "minecraft_bundle_governor"],
        ),
        "minecraft_strategy_canonicalized": (
            bool(minecraft_strategy.get("next_focus_csv", ""))
            and canonical_registry_contains(canonical_registry, "minecraft_domain_strategy"),
            "minecraft-scale strategy is not yet governed as a canonical operating artifact",
            f"next_focus_csv={minecraft_strategy.get('next_focus_csv', '')} canonical_registry={canonical_registry}",
            ["minecraft_strategy_governor", "artifact_governor"],
        ),
        "minecraft_soak_governed": (
            bool(minecraft_soak.get("minecraft_soak_state", ""))
            and canonical_registry_contains(canonical_registry, "minecraft_domain_soak_report"),
            "minecraft-scale soak state is not yet governed as a canonical operating artifact",
            f"minecraft_soak_state={minecraft_soak.get('minecraft_soak_state', '')} canonical_registry={canonical_registry}",
            ["minecraft_soak_governor", "artifact_governor"],
        ),
        "player_experience_governed": (
            float(player_experience.get("estimated_completeness_percent", 0.0)) >= 0.0
            and canonical_registry_contains(canonical_registry, "player_experience_profile"),
            "player-facing completeness is not yet governed as a canonical operating artifact",
            f"experience_percent={player_experience.get('estimated_completeness_percent', 0)} canonical_registry={canonical_registry}",
            ["player_experience_governor", "artifact_governor"],
        ),
        "player_experience_long_soak_governed": (
            bool(player_experience_soak.get("player_experience_soak_state", ""))
            and canonical_registry_contains(canonical_registry, "player_experience_soak_report"),
            "player-facing completeness does not yet preserve a governed long-soak artifact",
            f"player_experience_soak_state={player_experience_soak.get('player_experience_soak_state', '')} canonical_registry={canonical_registry}",
            ["player_experience_soak_governor", "artifact_governor"],
        ),
        "engagement_fatigue_governed": (
            float(engagement_fatigue.get("fatigue_gap_score", 0.0)) >= 0.0
            and canonical_registry_contains(canonical_registry, "engagement_fatigue_profile"),
            "thinness and repetition fatigue are not yet governed as a canonical operating artifact",
            f"fatigue_gap_score={engagement_fatigue.get('fatigue_gap_score', '')} canonical_registry={canonical_registry}",
            ["engagement_fatigue_governor", "artifact_governor"],
        ),
        "engagement_fatigue_under_control": (
            float(engagement_fatigue.get("fatigue_gap_score", 1.0)) <= 0.55,
            "thinness, repetition fatigue, or novelty gap remains too high for the conservative bar",
            f"fatigue_gap_score={engagement_fatigue.get('fatigue_gap_score', '')} fatigue_state={engagement_fatigue.get('fatigue_state', '')}",
            ["content_governor", "content_strategy_governor", "engagement_fatigue_governor", "player_experience_governor"],
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


def write_payload(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def load_eval_bundle(*, refresh_if_stale: bool = True) -> dict[str, Any]:
    if refresh_if_stale and output_is_stale():
        payload = evaluate()
        write_payload(payload)
        return payload
    if OUTPUT_PATH.exists():
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    payload = evaluate()
    write_payload(payload)
    return payload


def main() -> int:
    payload = evaluate()
    write_payload(payload)
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

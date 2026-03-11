#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import shutil
import sys
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
DEGRADED_DB_FALLBACK_REASONS = {
    "MySQL backend unavailable",
    "Unsafe degraded local-authority mode is disabled in production",
}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def nested_get(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for key in dotted.split("."):
        if not isinstance(current, dict):
            raise KeyError(dotted)
        current = current[key]
    return current


def nested_set(payload: dict[str, Any], dotted: str, value: Any) -> None:
    current: dict[str, Any] = payload
    parts = dotted.split(".")
    for key in parts[:-1]:
        current = current.setdefault(key, {})
    current[parts[-1]] = value


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def number_like(previous: Any, candidate: float) -> Any:
    if isinstance(previous, int) and not isinstance(previous, bool):
        return int(round(candidate))
    return round(candidate, 4)


@dataclass
class Change:
    file_key: str
    dotted_key: str
    previous: Any
    next_value: Any
    reason: str


class AutonomyLoop:
    def __init__(self, *, dry_run: bool = False, ignore_cooldown: bool = False):
        self.dry_run = dry_run
        self.ignore_cooldown = ignore_cooldown
        self.autonomy = load_yaml(CONFIG / "autonomy.yml")
        self.persistence = load_yaml(CONFIG / "persistence.yml")
        self.adaptive_rules = load_yaml(CONFIG / "adaptive_rules.yml")
        self.runtime_monitor = load_yaml(CONFIG / "runtime_monitor.yml")
        self.pressure = load_yaml(CONFIG / "pressure.yml")
        self.economy = load_yaml(CONFIG / "economy.yml")
        self.configs = {
            "adaptive_rules": self.adaptive_rules,
            "runtime_monitor": self.runtime_monitor,
            "pressure": self.pressure,
            "economy": self.economy,
        }
        surfaces = self.autonomy.get("surfaces", {})
        self.decisions_dir = ROOT / surfaces.get("decisions_dir", "runtime_data/autonomy/decisions")
        self.backups_dir = ROOT / surfaces.get("backups_dir", "runtime_data/autonomy/backups")
        self.policy_exports_dir = ROOT / surfaces.get("policy_exports_dir", "runtime_data/policies")
        self.knowledge_exports_dir = ROOT / surfaces.get("knowledge_exports_dir", "runtime_data/knowledge")
        self.control_state_path = AUTONOMY / "control" / "state.yml"
        self.control_lineage_path = AUTONOMY / "control" / "lineage.jsonl"
        self.control_state = load_yaml(self.control_state_path)
        self.runtime_fingerprint = ""
        self.soak_update: dict[str, Any] | None = None

    def change_signature(self, changes: list[Change]) -> str:
        payload = [
            {
                "file_key": change.file_key,
                "dotted_key": change.dotted_key,
                "direction": 0 if change.next_value == change.previous else (1 if change.next_value > change.previous else -1),
            }
            for change in changes
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def aggregate_signature(self, aggregate: dict[str, float]) -> str:
        return hashlib.sha256(json.dumps(aggregate, sort_keys=True).encode("utf-8")).hexdigest()

    def recent_apply_plateau(self, aggregate: dict[str, float], changes: list[Change]) -> bool:
        window = max(2, int((self.autonomy.get("convergence", {}) or {}).get("repeated_apply_window", 3)))
        current_aggregate_signature = self.aggregate_signature(aggregate)
        current_change_signature = self.change_signature(changes)
        matched = 0
        for path in sorted(self.decisions_dir.glob("*.yml"), reverse=True):
            decision = load_yaml(path)
            if not decision or decision.get("mode") != "apply":
                continue
            if decision.get("aggregate_signature") != current_aggregate_signature:
                break
            historical_changes = [
                Change(
                    file_key=change["file_key"],
                    dotted_key=change["dotted_key"],
                    previous=change["previous"],
                    next_value=change["next_value"],
                    reason=change.get("reason", ""),
                )
                for change in decision.get("changes", [])
            ]
            if self.change_signature(historical_changes) != current_change_signature:
                break
            matched += 1
            if matched >= window:
                return True
        return False

    def persist_control_state(self) -> None:
        write_yaml(self.control_state_path, self.control_state)

    def append_control_lineage(self, payload: dict[str, Any]) -> None:
        self.control_lineage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.control_lineage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")

    def last_decision_age_seconds(self) -> float | None:
        latest: Path | None = None
        for path in sorted(self.decisions_dir.glob("*.yml")):
            latest = path
        if latest is None:
            return None
        decision = load_yaml(latest)
        created_at = decision.get("created_at")
        if not created_at:
            return None
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - created).total_seconds())

    def summarize(self) -> tuple[dict[str, float], list[str]]:
        samples = []
        blockers: list[str] = []
        fingerprint_source: dict[str, Any] = {}
        fallback = self.persistence.get("local_fallback", {}) or {}
        fallback_enabled = bool(fallback.get("enabled", False))
        fallback_writes = bool(fallback.get("allow_writes_when_db_unavailable", False))
        for status_path in sorted((RUNTIME / "status").glob("*.yml")):
            status = load_yaml(status_path)
            if not status:
                continue
            fingerprint_source[str(status_path.relative_to(ROOT))] = status
            transfer = status.get("deterministic_transfer_service", {}) or {}
            session = status.get("session_authority_service", {}) or {}
            pressure_plane = status.get("pressure_control_plane", {}) or {}
            experiment = status.get("experiment_registry", {}) or {}
            policy = status.get("policy_registry", {}) or {}
            exploit = status.get("exploit_forensics_plane", {}) or {}
            economy_authority = status.get("economy_item_authority_plane", {}) or {}

            degraded_db_fallback = (
                status.get("safe_mode")
                and fallback_enabled
                and fallback_writes
                and status.get("safe_mode_reason", "") in DEGRADED_DB_FALLBACK_REASONS
            )
            if status.get("safe_mode") and not degraded_db_fallback:
                blockers.append(f"safe_mode:{status_path.stem}")
            if int(status.get("reconciliation_mismatches", 0)) > 0:
                blockers.append(f"reconciliation_mismatch:{status_path.stem}")
            if int(status.get("guild_value_drift", 0)) > 0:
                blockers.append(f"guild_drift:{status_path.stem}")
            if int(status.get("replay_divergence", 0)) > 0:
                blockers.append(f"replay_divergence:{status_path.stem}")
            if int(status.get("item_ownership_conflicts", 0)) > 0:
                blockers.append(f"item_conflict:{status_path.stem}")
            if int(transfer.get("quarantines", 0)) > 0:
                blockers.append(f"transfer_quarantine:{status_path.stem}")
            if int(session.get("split_brain_detections", 0)) > 0:
                blockers.append(f"split_brain:{status_path.stem}")

            samples.append(
                {
                    "queue_size": float(status.get("queue_size", 0)),
                    "player_density": float(status.get("player_density", 0)),
                    "routing_latency_ms": float(status.get("network_routing_latency_ms", 0)),
                    "runtime_tps": float(status.get("runtime_tps", 20.0)),
                    "pressure": float(status.get("runtime_composite_pressure", pressure_plane.get("composite", 0.0))),
                    "dungeons_started": float(status.get("dungeon_started", 0)),
                    "dungeons_completed": float(status.get("dungeon_completed", 0)),
                    "events_started": float(status.get("event_started", 0)),
                    "event_joins": float(status.get("event_join_count", 0)),
                    "economy_earn": float(status.get("economy_earn", 0)),
                    "economy_spend": float(status.get("economy_spend", 0)),
                    "progression_level_up": float(status.get("progression_level_up", 0)),
                    "return_player_reward": float(status.get("return_player_reward", 0)),
                    "streak_progress": float(status.get("streak_progress", 0)),
                    "rivalry_match": float(status.get("rivalry_match", 0)),
                    "exploit_incidents": float(exploit.get("incident_total", 0)),
                    "experiment_rollbacks": float(experiment.get("rollbacks", 0)) + float(policy.get("rollbacks", 0)),
                    "transfer_failures": float(transfer.get("lease_verification_failures", 0)) + float(status.get("transfer_fence_rejects", 0)),
                    "item_quarantine": float(economy_authority.get("quarantined_items", 0)),
                }
            )

        if len(samples) < int(self.autonomy.get("loop", {}).get("min_status_samples", 1)):
            blockers.append("insufficient_status_samples")

        if not samples:
            return {"sample_count": 0.0}, blockers

        aggregate: dict[str, float] = {"sample_count": float(len(samples))}
        for key in samples[0]:
            aggregate[f"avg_{key}"] = sum(sample[key] for sample in samples) / len(samples)

        started = aggregate.get("avg_dungeons_started", 0.0)
        completed = aggregate.get("avg_dungeons_completed", 0.0)
        events_started = aggregate.get("avg_events_started", 0.0)
        event_joins = aggregate.get("avg_event_joins", 0.0)
        aggregate["completion_rate"] = 1.0 if started <= 0 else completed / max(1.0, started)
        aggregate["event_join_rate"] = 0.0 if events_started <= 0 else event_joins / max(1.0, events_started)
        economy_spend = aggregate.get("avg_economy_spend", 0.0)
        aggregate["economy_inflation_ratio"] = (
            aggregate.get("avg_economy_earn", 0.0) / max(1.0, economy_spend if economy_spend > 0 else 1.0)
        )
        aggregate["engagement_score"] = (
            aggregate.get("avg_progression_level_up", 0.0)
            + aggregate.get("avg_return_player_reward", 0.0)
            + aggregate.get("avg_streak_progress", 0.0)
            + aggregate.get("avg_rivalry_match", 0.0)
        )
        aggregate["risk_score"] = (
            aggregate.get("avg_queue_size", 0.0)
            + aggregate.get("avg_routing_latency_ms", 0.0) / 10.0
            + aggregate.get("avg_exploit_incidents", 0.0) * 4.0
            + aggregate.get("avg_transfer_failures", 0.0) * 3.0
            + aggregate.get("avg_item_quarantine", 0.0) * 2.0
            + aggregate.get("avg_experiment_rollbacks", 0.0) * 2.0
        )
        self.runtime_fingerprint = hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True).encode("utf-8")).hexdigest()
        return aggregate, blockers

    def regime_for(self, aggregate: dict[str, float]) -> str:
        targets = self.autonomy.get("quality_targets", {})
        queue_warning = float(targets.get("queue_size_warning", 25))
        pressure_warning = float(targets.get("pressure_warning", 0.72))
        routing_warning = float(targets.get("routing_latency_warning_ms", 80.0))
        completion_floor = float(targets.get("completion_rate_floor", 0.55))
        event_join_floor = float(targets.get("event_join_floor", 1.25))
        economy_inflation_warning = float(targets.get("economy_inflation_ratio_warning", 1.35))
        exploit_incident_warning = float(targets.get("exploit_incident_warning", 2.0))

        healthy = (
            aggregate.get("completion_rate", 0.0) >= completion_floor + 0.10
            and aggregate.get("event_join_rate", 0.0) >= event_join_floor + 4.0
            and aggregate.get("avg_queue_size", 0.0) <= max(5.0, queue_warning / 3.0)
            and aggregate.get("avg_pressure", 0.0) <= max(0.35, pressure_warning - 0.20)
            and aggregate.get("economy_inflation_ratio", 0.0) <= max(1.05, economy_inflation_warning - 0.20)
            and aggregate.get("avg_exploit_incidents", 0.0) <= 0.0
            and aggregate.get("risk_score", 0.0) <= 5.0
        )
        if healthy:
            return "healthy"
        pressured = (
            aggregate.get("avg_queue_size", 0.0) >= queue_warning
            or aggregate.get("avg_routing_latency_ms", 0.0) >= routing_warning
            or aggregate.get("avg_pressure", 0.0) >= pressure_warning
            or aggregate.get("completion_rate", 1.0) < completion_floor
            or aggregate.get("event_join_rate", event_join_floor) < event_join_floor
            or aggregate.get("economy_inflation_ratio", 0.0) >= economy_inflation_warning
            or aggregate.get("avg_exploit_incidents", 0.0) >= exploit_incident_warning
        )
        if pressured:
            return "pressured"
        return "steady"

    def soak_evaluation(
        self,
        active_soak: dict[str, Any],
        aggregate: dict[str, float],
        blockers: list[str],
    ) -> tuple[str, list[Change], list[str], dict[str, Any]]:
        soak_policy = self.autonomy.get("soak", {}) or {}
        observations = int(active_soak.get("observations", 0)) + 1
        required_observations = max(1, int(soak_policy.get("required_observations", 2)))
        baseline = active_soak.get("baseline", {}) or {}
        regressions: list[str] = []

        if blockers:
            regressions.extend(f"blocked:{blocker}" for blocker in blockers)

        completion_delta = baseline.get("completion_rate", aggregate.get("completion_rate", 0.0)) - aggregate.get("completion_rate", 0.0)
        if completion_delta > float(soak_policy.get("max_regression_completion_rate", 0.08)):
            regressions.append("completion_rate_regressed")

        join_delta = baseline.get("event_join_rate", aggregate.get("event_join_rate", 0.0)) - aggregate.get("event_join_rate", 0.0)
        if join_delta > float(soak_policy.get("max_regression_event_join_rate", 0.2)):
            regressions.append("event_join_rate_regressed")

        pressure_delta = aggregate.get("avg_pressure", 0.0) - baseline.get("avg_pressure", aggregate.get("avg_pressure", 0.0))
        if pressure_delta > float(soak_policy.get("max_pressure_increase", 0.12)):
            regressions.append("pressure_regressed")

        risk_delta = aggregate.get("risk_score", 0.0) - baseline.get("risk_score", aggregate.get("risk_score", 0.0))
        if risk_delta > float(soak_policy.get("max_risk_increase", 6.0)):
            regressions.append("risk_regressed")

        if regressions:
            revert_changes = [
                Change(
                    file_key=change["file_key"],
                    dotted_key=change["dotted_key"],
                    previous=change["next_value"],
                    next_value=change["previous"],
                    reason=f"reject soak lineage {active_soak.get('decision_id', 'unknown')} after regression",
                )
                for change in active_soak.get("changes", [])
            ]
            active_soak.update(
                {
                    "observations": observations,
                    "last_outcome": "rejected",
                    "last_outcome_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "regressions": regressions,
                }
            )
            return "reject", revert_changes, regressions, active_soak

        active_soak.update(
            {
                "observations": observations,
                "last_outcome": "hold" if observations < required_observations else "promote",
                "last_outcome_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "regressions": [],
            }
        )
        if observations < required_observations:
            return "hold", [], [], active_soak
        return "promote", [], [], active_soak

    def propose_change(self, changes: list[Change], file_key: str, dotted_key: str, direction: float, reason: str) -> None:
        parameter_key = f"{file_key}.{dotted_key}"
        policy = self.autonomy.get("parameters", {}).get(parameter_key)
        if not policy:
            return
        payload = self.configs[file_key]
        previous = nested_get(payload, dotted_key)
        candidate = float(previous) + (policy["step"] * direction)
        candidate = clamp(candidate, float(policy["min"]), float(policy["max"]))
        next_value = number_like(previous, candidate)
        if next_value == previous:
            return
        changes.append(Change(file_key=file_key, dotted_key=dotted_key, previous=previous, next_value=next_value, reason=reason))

    def decide(self, aggregate: dict[str, float], blockers: list[str]) -> tuple[str, list[Change], list[str]]:
        loop_policy = self.autonomy.get("loop", {})
        targets = self.autonomy.get("quality_targets", {})
        active_soak = self.control_state.get("active_soak", {}) or {}

        if active_soak:
            mode, changes, soak_blockers, soak_state = self.soak_evaluation(active_soak, aggregate, blockers)
            self.soak_update = soak_state
            return mode, changes, soak_blockers

        if blockers and self.autonomy.get("controls", {}).get("fail_closed_on_conflict", True):
            return "blocked", [], blockers

        cooldown = float(loop_policy.get("decision_cooldown_seconds", 300))
        age = self.last_decision_age_seconds()
        if not self.ignore_cooldown and age is not None and age < cooldown:
            return "cooldown", [], [f"cooldown:{int(age)}<{int(cooldown)}"]

        changes: list[Change] = []
        queue_warning = float(targets.get("queue_size_warning", 25))
        pressure_warning = float(targets.get("pressure_warning", 0.72))
        routing_warning = float(targets.get("routing_latency_warning_ms", 80.0))
        completion_floor = float(targets.get("completion_rate_floor", 0.55))
        event_join_floor = float(targets.get("event_join_floor", 12.0))
        economy_inflation_warning = float(targets.get("economy_inflation_ratio_warning", 1.35))
        exploit_incident_warning = float(targets.get("exploit_incident_warning", 2.0))
        abnormal_currency_warning = float(targets.get("abnormal_currency_warning", 1800.0))
        density_limit = float(self.runtime_monitor.get("health_thresholds", {}).get("player_density_limit", 80))
        density_ratio = aggregate.get("avg_player_density", 0.0) / max(1.0, density_limit)

        if aggregate.get("avg_queue_size", 0.0) >= queue_warning or aggregate.get("avg_routing_latency_ms", 0.0) >= routing_warning:
            self.propose_change(changes, "adaptive_rules", "matchmaking.high_queue_seconds", -1.0, "queue and routing pressure require earlier matchmaking widening")
            self.propose_change(changes, "pressure", "controls.queue_admission_threshold", -1.0, "queue pressure requires earlier admission throttling")

        if density_ratio >= 0.85 or aggregate.get("avg_pressure", 0.0) >= pressure_warning:
            self.propose_change(changes, "runtime_monitor", "scaling.density_scale_trigger", -1.0, "density pressure requires earlier instance scaling")
            self.propose_change(changes, "pressure", "controls.noncritical_spawn_suppression_threshold", -1.0, "pressure requires earlier noncritical spawn suppression")

        if aggregate.get("completion_rate", 1.0) < completion_floor:
            self.propose_change(changes, "adaptive_rules", "rewards.low_completion_rate", 1.0, "weak dungeon completion should trigger reward support sooner")

        if aggregate.get("event_join_rate", event_join_floor) < event_join_floor:
            self.propose_change(changes, "adaptive_rules", "events.low_join_rate", 1.0, "weak event participation should trigger event support sooner")

        net_currency_gain = aggregate.get("avg_economy_earn", 0.0) - aggregate.get("avg_economy_spend", 0.0)
        if (
            aggregate.get("economy_inflation_ratio", 0.0) >= economy_inflation_warning
            or net_currency_gain >= abnormal_currency_warning
        ):
            self.propose_change(changes, "economy", "market_tax", 1.0, "inflation pressure should raise market tax to absorb excess currency")
            self.propose_change(changes, "runtime_monitor", "exploit_detection.abnormal_currency_gain", -1.0, "currency inflation should tighten abnormal gain detection")

        if aggregate.get("avg_exploit_incidents", 0.0) >= exploit_incident_warning:
            self.propose_change(changes, "runtime_monitor", "exploit_detection.duplicate_reward_spike", -1.0, "exploit activity should tighten duplicate reward detection")
            self.propose_change(changes, "runtime_monitor", "exploit_detection.abnormal_currency_gain", -1.0, "exploit activity should tighten abnormal currency detection")

        if self.regime_for(aggregate) == "healthy":
            self.propose_change(changes, "adaptive_rules", "matchmaking.high_queue_seconds", 1.0, "stable healthy runtime can delay queue widening to preserve match quality")
            self.propose_change(changes, "pressure", "controls.queue_admission_threshold", 1.0, "healthy runtime can admit more load before throttling")
            self.propose_change(changes, "runtime_monitor", "scaling.density_scale_trigger", 1.0, "healthy density can delay scaling to reduce fragmentation")
            self.propose_change(changes, "pressure", "controls.noncritical_spawn_suppression_threshold", 1.0, "healthy runtime can restore exploratory spawn headroom")
            self.propose_change(changes, "adaptive_rules", "rewards.low_completion_rate", -1.0, "healthy completion can taper reward assistance")
            self.propose_change(changes, "adaptive_rules", "events.low_join_rate", -1.0, "healthy event demand can taper event assistance")
            self.propose_change(changes, "economy", "market_tax", -1.0, "healthy economy can ease market tax to preserve trading fluidity")
            self.propose_change(changes, "runtime_monitor", "exploit_detection.abnormal_currency_gain", 1.0, "healthy economy can relax abnormal gain detection slightly")
            self.propose_change(changes, "runtime_monitor", "exploit_detection.duplicate_reward_spike", 1.0, "healthy exploit surface can relax duplicate reward sensitivity slightly")

        max_adjustments = int(loop_policy.get("max_adjustments_per_pass", 6))
        bounded_changes = changes[:max_adjustments]
        if bounded_changes and self.recent_apply_plateau(aggregate, bounded_changes):
            return "plateau", [], ["plateau_repeated_apply_signature"]
        return ("apply" if bounded_changes else "noop"), bounded_changes, []

    def persist_decision(self, mode: str, aggregate: dict[str, float], blockers: list[str], changes: list[Change]) -> Path:
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        decision_id = "aql-" + uuid.uuid4().hex[:12]
        previous_head = self.control_state.get("lineage_head", "")
        aggregate_signature = self.aggregate_signature(aggregate)
        signature = hashlib.sha256(
            json.dumps(
                {
                    "aggregate": aggregate,
                    "aggregate_signature": aggregate_signature,
                    "blockers": blockers,
                    "changes": [change.__dict__ for change in changes],
                    "mode": mode,
                    "previous_head": previous_head,
                    "runtime_fingerprint": self.runtime_fingerprint,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        payload = {
            "decision_id": decision_id,
            "created_at": created_at,
            "mode": "dry_run" if self.dry_run and mode == "apply" else mode,
            "regime": self.regime_for(aggregate),
            "aggregate": aggregate,
            "aggregate_signature": aggregate_signature,
            "blockers": blockers,
            "changes": [change.__dict__ for change in changes],
            "lineage": {
                "previous_head": previous_head,
                "head": signature,
                "runtime_fingerprint": self.runtime_fingerprint,
            },
            "signature": signature,
        }
        filename = f"{created_at.replace(':', '').replace('-', '')}_{decision_id}.yml"
        decision_path = self.decisions_dir / filename
        write_yaml(decision_path, payload)
        write_yaml(self.policy_exports_dir / f"{created_at.replace(':', '').replace('-', '')}_{decision_id}_policy.yml", payload)
        knowledge_payload = {
            "artifact_id": f"artifact:autonomy:{decision_id}",
            "artifact_type": "autonomous_quality_loop",
            "scope": "minecraft_runtime",
            "created_at": created_at,
            "mode": payload["mode"],
            "usefulness": round(max(0.0, min(1.0, aggregate.get("completion_rate", 0.0) - (aggregate.get("avg_pressure", 0.0) * 0.25))), 4),
            "tags": ["autonomy", "quality", "balancing", "governance", "closed_loop"],
            "decision_ref": str(decision_path.relative_to(ROOT)),
            "summary": {
                "blockers": blockers,
                "change_count": len(changes),
                "sample_count": int(aggregate.get("sample_count", 0)),
            },
        }
        write_yaml(self.knowledge_exports_dir / f"{created_at.replace(':', '').replace('-', '')}_{decision_id}_knowledge.yml", knowledge_payload)
        self.append_control_lineage(
            {
                "created_at": created_at,
                "decision_id": decision_id,
                "mode": payload["mode"],
                "regime": payload["regime"],
                "head": signature,
                "previous_head": previous_head,
                "runtime_fingerprint": self.runtime_fingerprint,
                "aggregate_signature": aggregate_signature,
                "change_count": len(changes),
                "blocker_count": len(blockers),
            }
        )
        self.control_state["lineage_head"] = signature
        self.control_state["last_decision_id"] = decision_id
        self.control_state["last_decision_path"] = str(decision_path.relative_to(ROOT))
        self.control_state["last_mode"] = payload["mode"]
        self.control_state["last_regime"] = payload["regime"]
        self.control_state["last_runtime_fingerprint"] = self.runtime_fingerprint
        self.control_state["last_aggregate_signature"] = aggregate_signature
        self.control_state["last_decision_at"] = created_at
        return decision_path

    def backup_and_apply(self, changes: list[Change]) -> None:
        created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        seen_files: set[str] = set()
        for change in changes:
            seen_files.add(change.file_key)
            source = CONFIG / f"{change.file_key}.yml"
            backup = self.backups_dir / created_at / source.name
            if not backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, backup)
            nested_set(self.configs[change.file_key], change.dotted_key, change.next_value)
        for file_key in sorted(seen_files):
            write_yaml(CONFIG / f"{file_key}.yml", self.configs[file_key])

    def update_threshold_state(self, mode: str, blockers: list[str]) -> None:
        policy = self.autonomy.get("final_threshold", {}) or {}
        required_streak = max(1, int(policy.get("required_steady_noop_streak", 12)))
        operational_streak = max(1, int(policy.get("operational_steady_streak", 4)))
        autonomy_streak = max(1, int(policy.get("autonomy_steady_streak", 6)))
        steady_noop = mode == "noop" and self.control_state.get("last_regime") == "steady" and not blockers and not self.control_state.get("active_soak")
        streak = int(self.control_state.get("steady_noop_streak", 0))
        self.control_state["steady_noop_streak"] = streak + 1 if steady_noop else 0
        self.control_state["execution_threshold_ready"] = True
        self.control_state["operational_threshold_ready"] = self.control_state["steady_noop_streak"] >= operational_streak
        self.control_state["autonomy_threshold_ready"] = self.control_state["steady_noop_streak"] >= autonomy_streak
        self.control_state["final_threshold_ready"] = self.control_state["steady_noop_streak"] >= required_streak

    def run(self) -> int:
        if not self.autonomy.get("loop", {}).get("enabled", True):
            print("AUTONOMY_LOOP_DISABLED")
            return 1

        aggregate, blockers = self.summarize()
        mode, changes, extra_blockers = self.decide(aggregate, blockers)
        blockers = list(dict.fromkeys(blockers + extra_blockers))
        decision_path = None if self.dry_run else self.persist_decision(mode, aggregate, blockers, changes)

        if mode in {"apply", "reject"} and not self.dry_run:
            self.backup_and_apply(changes)
        if not self.dry_run:
            created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            soak_state = self.control_state.get("active_soak", {}) or {}
            if self.soak_update is not None:
                soak_state = self.soak_update.copy()
            if mode == "apply":
                self.control_state["active_soak"] = {
                    "decision_id": self.control_state.get("last_decision_id", ""),
                    "decision_path": self.control_state.get("last_decision_path", ""),
                    "created_at": created_at,
                    "baseline": {
                        "completion_rate": aggregate.get("completion_rate", 0.0),
                        "event_join_rate": aggregate.get("event_join_rate", 0.0),
                        "avg_pressure": aggregate.get("avg_pressure", 0.0),
                        "risk_score": aggregate.get("risk_score", 0.0),
                    },
                    "observations": 0,
                    "changes": [change.__dict__ for change in changes],
                    "runtime_fingerprint": self.runtime_fingerprint,
                }
            elif mode == "hold":
                self.control_state["active_soak"] = soak_state
            elif mode in {"promote", "reject"}:
                soak_state = soak_state.copy()
                soak_state["closed_at"] = created_at
                soak_state["resolution"] = mode
                self.control_state["last_soak_resolution"] = soak_state
                self.control_state["active_soak"] = {}
            self.update_threshold_state(mode, blockers)
            self.persist_control_state()

        print("AUTONOMY_LOOP")
        print(f"MODE={'dry_run' if self.dry_run and mode == 'apply' else mode}")
        if decision_path is not None:
            print(f"DECISION={decision_path.relative_to(ROOT)}")
        print(f"REGIME={self.regime_for(aggregate)}")
        if self.control_state.get("active_soak"):
            print(f"ACTIVE_SOAK={self.control_state['active_soak'].get('decision_id', '')}")
        print(f"EXECUTION_THRESHOLD_READY={1 if self.control_state.get('execution_threshold_ready', False) else 0}")
        print(f"OPERATIONAL_THRESHOLD_READY={1 if self.control_state.get('operational_threshold_ready', False) else 0}")
        print(f"AUTONOMY_THRESHOLD_READY={1 if self.control_state.get('autonomy_threshold_ready', False) else 0}")
        print(f"STEADY_NOOP_STREAK={int(self.control_state.get('steady_noop_streak', 0))}")
        print(f"FINAL_THRESHOLD_READY={1 if self.control_state.get('final_threshold_ready', False) else 0}")
        print(f"SAMPLE_COUNT={int(aggregate.get('sample_count', 0))}")
        print(f"COMPLETION_RATE={aggregate.get('completion_rate', 0.0):.3f}")
        print(f"EVENT_JOIN_RATE={aggregate.get('event_join_rate', 0.0):.3f}")
        print(f"AVERAGE_QUEUE={aggregate.get('avg_queue_size', 0.0):.3f}")
        print(f"AVERAGE_PRESSURE={aggregate.get('avg_pressure', 0.0):.3f}")
        if blockers:
            for blocker in blockers:
                print(f"BLOCKER={blocker}")
        for change in changes:
            print(f"CHANGE={change.file_key}.{change.dotted_key}:{change.previous}->{change.next_value}:{change.reason}")

        if self.dry_run:
            return 0
        if mode in {"blocked", "reject"}:
            return 1
        return 0


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    ignore_cooldown = "--ignore-cooldown" in argv
    return AutonomyLoop(dry_run=dry_run, ignore_cooldown=ignore_cooldown).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

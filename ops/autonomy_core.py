#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "runtime_data" / "autonomy" / "core"
CONTROL_STATE_PATH = ROOT / "runtime_data" / "autonomy" / "control" / "state.yml"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def safe_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


@dataclass
class EventRecord:
    event_id: str
    event_type: str
    created_at: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, event_type: str, source: str, payload: dict[str, Any] | None = None) -> "EventRecord":
        return cls(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            created_at=now_iso(),
            source=source,
            payload=payload or {},
        )


class EventLog:
    def __init__(self, root: Path = CORE_DIR):
        self.path = root / "event_log.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: EventRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")


@dataclass
class RuntimeAggregate:
    sample_count: int = 0
    completion_rate: float = 0.0
    event_join_rate: float = 0.0
    average_queue: float = 0.0
    average_pressure: float = 0.0
    economy_inflation_ratio: float = 0.0
    exploit_incidents: float = 0.0


@dataclass
class TypedSnapshot:
    snapshot_id: str
    snapshot_type: str
    created_at: str
    status: str
    aggregate: RuntimeAggregate
    blockers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        snapshot_type: str,
        status: str,
        aggregate: RuntimeAggregate,
        blockers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "TypedSnapshot":
        return cls(
            snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
            snapshot_type=snapshot_type,
            created_at=now_iso(),
            status=status,
            aggregate=aggregate,
            blockers=blockers or [],
            metadata=metadata or {},
        )


class SnapshotStore:
    def __init__(self, root: Path = CORE_DIR):
        self.root = root / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, snapshot: TypedSnapshot) -> Path:
        path = self.root / f"{snapshot.created_at.replace(':', '').replace('-', '')}_{snapshot.snapshot_type}_{snapshot.snapshot_id}.yml"
        payload = asdict(snapshot)
        payload["aggregate"] = asdict(snapshot.aggregate)
        safe_write_yaml(path, payload)
        return path


@dataclass
class Job:
    job_id: str
    job_type: str
    created_at: str
    priority: int
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0

    @classmethod
    def create(cls, job_type: str, priority: int, payload: dict[str, Any] | None = None) -> "Job":
        return cls(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            job_type=job_type,
            created_at=now_iso(),
            priority=priority,
            payload=payload or {},
        )


class JobQueue:
    def __init__(self, root: Path = CORE_DIR):
        self.root = root / "jobs"
        self.pending = self.root / "pending"
        self.running = self.root / "running"
        self.done = self.root / "done"
        self.failed = self.root / "failed"
        for directory in (self.pending, self.running, self.done, self.failed):
            directory.mkdir(parents=True, exist_ok=True)

    def enqueue(self, job: Job) -> Path:
        path = self.pending / f"{job.priority:02d}_{job.created_at.replace(':', '').replace('-', '')}_{job.job_id}.yml"
        safe_write_yaml(path, asdict(job))
        return path

    def has_pending(self) -> bool:
        return any(self.pending.glob("*.yml"))

    def dequeue(self) -> tuple[Job | None, Path | None]:
        candidates = sorted(self.pending.glob("*.yml"))
        if not candidates:
            return None, None
        path = candidates[0]
        payload = safe_load_yaml(path)
        job = Job(**payload)
        running_path = self.running / path.name
        path.rename(running_path)
        return job, running_path

    def complete(self, job: Job, path: Path, status: str, result: dict[str, Any]) -> Path:
        job.attempts += 1
        payload = asdict(job)
        payload["result"] = result
        payload["finished_at"] = now_iso()
        destination_root = self.done if status == "done" else self.failed
        destination = destination_root / path.name
        safe_write_yaml(destination, payload)
        if path.exists():
            path.unlink()
        return destination


class PolicyLayer:
    def __init__(self, config_path: Path = ROOT / "configs" / "autonomy.yml"):
        self.config_path = config_path
        self.config = safe_load_yaml(config_path)

    def supervisor_config(self) -> dict[str, Any]:
        return (self.config.get("supervisor", {}) or {}).copy()

    def control_state(self) -> dict[str, Any]:
        return safe_load_yaml(CONTROL_STATE_PATH)

    def seed_jobs(self, queue: JobQueue, *, loop_count: int) -> list[Job]:
        if queue.has_pending():
            return []
        supervisor = self.supervisor_config()
        control = self.control_state()
        active_soak = (control.get("active_soak", {}) or {}).get("decision_id", "")
        steady_noop_streak = int(control.get("steady_noop_streak", 0))
        final_threshold_ready = bool(control.get("final_threshold_ready", False))
        mode = str(supervisor.get("mode", "hybrid"))
        cycles = max(1, int(supervisor.get("synthetic_cycles", 2)))
        matrix_every = max(0, int(supervisor.get("matrix_every_n_loops", 6)))

        jobs: list[Job] = [
            Job.create("validate_runtime_truth", 10),
            Job.create("runtime_integrity", 20),
            Job.create("reconcile_runtime", 30),
        ]
        if mode in {"hybrid", "synthetic"}:
            jobs.extend(
                [
                    Job.create("rebuild_runtime_status", 40),
                    Job.create("simulate_runtime_feedback", 50, {"cycles": cycles}),
                    Job.create("sanitize_runtime_status", 60),
                    Job.create("runtime_integrity", 70),
                    Job.create("reconcile_runtime", 80),
                ]
            )
        threshold_pursuit = steady_noop_streak > 0 or final_threshold_ready
        if active_soak:
            jobs.append(Job.create("autonomous_quality_loop", 85, {"ignore_cooldown": True, "active_soak": active_soak}))
        elif not threshold_pursuit and (mode == "matrix" or (mode == "hybrid" and matrix_every > 0 and loop_count % matrix_every == 0)):
            jobs.append(Job.create("closed_loop_matrix", 90))
        else:
            jobs.append(Job.create("autonomous_quality_loop", 90, {"ignore_cooldown": True}))
        if final_threshold_ready:
            jobs.append(Job.create("artifact_governor", 95))
            jobs.append(Job.create("metaos_conformance", 96))
        if bool(control.get("execution_threshold_ready", False)):
            jobs.append(Job.create("content_governor", 97))
            jobs.append(Job.create("economy_governor", 98))
            jobs.append(Job.create("anti_cheat_governor", 99))
            jobs.append(Job.create("liveops_governor", 100))
            jobs.append(Job.create("gameplay_progression_governor", 101))
            jobs.append(Job.create("content_volume_governor", 102))
            jobs.append(Job.create("service_responsiveness_governor", 103))
            jobs.append(Job.create("matchmaking_quality_governor", 104))
            jobs.append(Job.create("economy_market_governor", 105))
            jobs.append(Job.create("player_experience_governor", 106))
            jobs.append(Job.create("engagement_fatigue_governor", 107))
            jobs.append(Job.create("material_inventory", 108))
            jobs.append(Job.create("runtime_partition_governor", 109))
            jobs.append(Job.create("content_strategy_governor", 110))
            jobs.append(Job.create("content_soak_governor", 111))
            jobs.append(Job.create("content_bundle_governor", 112))
            jobs.append(Job.create("repo_bundle_governor", 113))
            jobs.append(Job.create("minecraft_bundle_governor", 114))
            jobs.append(Job.create("minecraft_strategy_governor", 115))
            jobs.append(Job.create("player_experience_soak_governor", 116))
            jobs.append(Job.create("minecraft_soak_governor", 117))
        jobs.append(Job.create("runtime_summary", 118))
        jobs.append(Job.create("final_threshold_eval", 119))
        jobs.append(Job.create("final_threshold_repair", 120))
        for job in jobs:
            queue.enqueue(job)
        return jobs

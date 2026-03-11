#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import signal
import subprocess
import sys
import time

from autonomy_core import CORE_DIR, EventLog, EventRecord, JobQueue, PolicyLayer, RuntimeAggregate, SnapshotStore, TypedSnapshot, now_iso, safe_load_yaml, safe_write_yaml


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_DIR = ROOT / "runtime_data" / "autonomy" / "supervisor"
CONTROL_STATE_PATH = ROOT / "runtime_data" / "autonomy" / "control" / "state.yml"
STATE_PATH = SUPERVISOR_DIR / "state.yml"
HEARTBEAT_PATH = SUPERVISOR_DIR / "heartbeat.json"
LOG_PATH = SUPERVISOR_DIR / "supervisor.log"
PID_PATH = SUPERVISOR_DIR / "supervisor.pid"

STOP = False


def append_log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{now_iso()}] {message}\n")


def run_command(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    output = (completed.stdout or "").strip()
    if completed.stderr:
        stderr = completed.stderr.strip()
        output = f"{output}\n{stderr}".strip() if output else stderr
    return completed.returncode, output


def parse_kv(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def signal_stop(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    append_log(f"received_signal={signum}")


class Supervisor:
    def __init__(self) -> None:
        self.policy = PolicyLayer()
        config = self.policy.supervisor_config()
        self.enabled = bool(config.get("enabled", True))
        self.interval_seconds = max(30, int(config.get("interval_seconds", 300)))
        self.queue = JobQueue()
        self.snapshots = SnapshotStore()
        self.events = EventLog()
        self.state: dict[str, Any] = safe_load_yaml(STATE_PATH)
        self.job_handlers = {
            "validate_runtime_truth": ["python3", "ops/validate_runtime_truth.py"],
            "runtime_integrity": ["python3", "ops/runtime_integrity.py"],
            "reconcile_runtime": ["python3", "ops/reconcile_runtime.py"],
            "rebuild_runtime_status": ["python3", "ops/rebuild_runtime_status.py"],
            "simulate_runtime_feedback": ["python3", "ops/simulate_runtime_feedback.py"],
            "sanitize_runtime_status": ["python3", "ops/sanitize_runtime_status.py"],
            "autonomous_quality_loop": ["python3", "ops/autonomous_quality_loop.py"],
            "artifact_governor": ["python3", "ops/artifact_governor.py"],
            "metaos_conformance": ["python3", "ops/metaos_conformance.py"],
            "content_governor": ["python3", "ops/content_governor.py"],
            "economy_governor": ["python3", "ops/economy_governor.py"],
            "anti_cheat_governor": ["python3", "ops/anti_cheat_governor.py"],
            "liveops_governor": ["python3", "ops/liveops_governor.py"],
            "service_responsiveness_governor": ["python3", "ops/service_responsiveness_governor.py"],
            "matchmaking_quality_governor": ["python3", "ops/matchmaking_quality_governor.py"],
            "player_experience_governor": ["python3", "ops/player_experience_governor.py"],
            "gameplay_progression_governor": ["python3", "ops/gameplay_progression_governor.py"],
            "engagement_fatigue_governor": ["python3", "ops/engagement_fatigue_governor.py"],
            "material_inventory": ["python3", "ops/material_inventory.py"],
            "runtime_partition_governor": ["python3", "ops/runtime_partition_governor.py"],
            "content_strategy_governor": ["python3", "ops/content_strategy_governor.py"],
            "content_soak_governor": ["python3", "ops/content_soak_governor.py"],
            "content_bundle_governor": ["python3", "ops/content_bundle_governor.py"],
            "repo_bundle_governor": ["python3", "ops/repo_bundle_governor.py"],
            "minecraft_bundle_governor": ["python3", "ops/minecraft_bundle_governor.py"],
            "minecraft_strategy_governor": ["python3", "ops/minecraft_strategy_governor.py"],
            "player_experience_soak_governor": ["python3", "ops/player_experience_soak_governor.py"],
            "minecraft_soak_governor": ["python3", "ops/minecraft_soak_governor.py"],
            "runtime_summary": ["python3", "ops/runtime_summary.py"],
            "final_threshold_eval": ["python3", "ops/final_threshold_eval.py"],
            "final_threshold_repair": ["python3", "ops/final_threshold_repair.py"],
            "closed_loop_matrix": ["bash", "ops/run_closed_loop_matrix.sh"],
        }

    def persist_state(self, **updates: Any) -> None:
        self.state.update(updates)
        control_state = safe_load_yaml(CONTROL_STATE_PATH)
        if control_state:
            self.state["last_mode"] = control_state.get("last_mode", self.state.get("last_mode", "unknown"))
            self.state["last_regime"] = control_state.get("last_regime", self.state.get("last_regime", "unknown"))
            self.state["active_soak"] = (control_state.get("active_soak", {}) or {}).get("decision_id", "")
            self.state["last_decision"] = control_state.get("last_decision_path", self.state.get("last_decision", ""))
            self.state["steady_noop_streak"] = int(control_state.get("steady_noop_streak", self.state.get("steady_noop_streak", 0)))
            self.state["execution_threshold_ready"] = bool(control_state.get("execution_threshold_ready", self.state.get("execution_threshold_ready", False)))
            self.state["operational_threshold_ready"] = bool(control_state.get("operational_threshold_ready", self.state.get("operational_threshold_ready", False)))
            self.state["autonomy_threshold_ready"] = bool(control_state.get("autonomy_threshold_ready", self.state.get("autonomy_threshold_ready", False)))
            self.state["final_threshold_ready"] = bool(control_state.get("final_threshold_ready", self.state.get("final_threshold_ready", False)))
        safe_write_yaml(STATE_PATH, self.state)
        heartbeat = {
            "pid": PID_PATH.read_text(encoding="utf-8").strip() if PID_PATH.exists() else "",
            "updated_at": now_iso(),
            "loop_count": self.state.get("loop_count", 0),
            "last_mode": self.state.get("last_mode", "unknown"),
            "last_regime": self.state.get("last_regime", "unknown"),
            "last_status": self.state.get("last_status", "unknown"),
            "active_soak": self.state.get("active_soak", ""),
            "steady_noop_streak": int(self.state.get("steady_noop_streak", 0)),
            "execution_threshold_ready": bool(self.state.get("execution_threshold_ready", False)),
            "operational_threshold_ready": bool(self.state.get("operational_threshold_ready", False)),
            "autonomy_threshold_ready": bool(self.state.get("autonomy_threshold_ready", False)),
            "final_threshold_ready": bool(self.state.get("final_threshold_ready", False)),
            "queue_pending": len(list((CORE_DIR / "jobs" / "pending").glob("*.yml"))),
        }
        with HEARTBEAT_PATH.open("w", encoding="utf-8") as handle:
            json.dump(heartbeat, handle, ensure_ascii=True, indent=2)

    def snapshot_from_result(self, job_type: str, status: str, parsed: dict[str, str], blockers: list[str] | None = None) -> Path:
        aggregate = RuntimeAggregate(
            sample_count=int(parsed.get("SAMPLE_COUNT", 0) or 0),
            completion_rate=float(parsed.get("COMPLETION_RATE", 0.0) or 0.0),
            event_join_rate=float(parsed.get("EVENT_JOIN_RATE", 0.0) or 0.0),
            average_queue=float(parsed.get("AVERAGE_QUEUE", 0.0) or 0.0),
            average_pressure=float(parsed.get("AVERAGE_PRESSURE", 0.0) or 0.0),
            economy_inflation_ratio=float(parsed.get("ECONOMY_INFLATION_RATIO", 0.0) or 0.0),
            exploit_incidents=float(parsed.get("EXPLOIT_INCIDENTS", 0.0) or 0.0),
        )
        snapshot = TypedSnapshot.create(
            snapshot_type=job_type,
            status=status,
            aggregate=aggregate,
            blockers=blockers or [],
            metadata=parsed,
        )
        return self.snapshots.write(snapshot)

    def execute_job(self, job_type: str, payload: dict[str, Any]) -> tuple[int, str]:
        args = list(self.job_handlers[job_type])
        if job_type == "simulate_runtime_feedback":
            args.extend(["--cycles", str(payload.get("cycles", 2))])
        if job_type == "autonomous_quality_loop" and payload.get("ignore_cooldown", False):
            args.append("--ignore-cooldown")
        return run_command(args)

    def run_once(self) -> bool:
        loop_count = int(self.state.get("loop_count", 0)) + 1
        seeded = self.policy.seed_jobs(self.queue, loop_count=loop_count)
        self.persist_state(loop_count=loop_count, last_status="running", last_started_at=now_iso())
        if seeded:
            self.events.append(
                EventRecord.create(
                    "queue.seeded",
                    "policy_layer",
                    {
                        "loop_count": loop_count,
                        "job_count": len(seeded),
                        "job_types": [job.job_type for job in seeded],
                    },
                )
            )

        had_error = False
        last_mode = self.state.get("last_mode", "unknown")
        last_regime = self.state.get("last_regime", "unknown")
        last_decision = self.state.get("last_decision", "")
        last_summary = self.state.get("last_summary", "")
        active_soak = self.state.get("active_soak", "")
        previous_soak = active_soak

        while not STOP:
            job, path = self.queue.dequeue()
            if job is None or path is None:
                break
            self.events.append(EventRecord.create("job.started", "supervisor", {"job_id": job.job_id, "job_type": job.job_type}))
            append_log(f"job={job.job_type} id={job.job_id} attempts={job.attempts} started")
            code, output = self.execute_job(job.job_type, job.payload)
            parsed = parse_kv(output)
            blockers = [line.split("=", 1)[1] for line in output.splitlines() if line.startswith("BLOCKER=")]
            status = "done" if code == 0 else "failed"
            self.queue.complete(job, path, status, {"exit_code": code, "parsed": parsed, "output": output})
            self.snapshot_from_result(job.job_type, status, parsed, blockers)
            self.events.append(
                EventRecord.create(
                    f"job.{status}",
                    "supervisor",
                    {"job_id": job.job_id, "job_type": job.job_type, "exit_code": code, "mode": parsed.get("MODE", "")},
                )
            )
            append_log(f"job={job.job_type} id={job.job_id} exit={code}")
            if output:
                append_log(output)

            if job.job_type in {"autonomous_quality_loop", "closed_loop_matrix"}:
                last_mode = parsed.get("MODE", last_mode)
                last_regime = parsed.get("REGIME", last_regime)
                last_decision = parsed.get("DECISION", last_decision)
                active_soak = parsed.get("ACTIVE_SOAK", active_soak)
                if job.job_type == "autonomous_quality_loop":
                    if active_soak != previous_soak:
                        self.events.append(
                            EventRecord.create(
                                "soak.transition",
                                "supervisor",
                                {
                                    "previous_active_soak": previous_soak,
                                    "active_soak": active_soak,
                                    "mode": last_mode,
                                    "regime": last_regime,
                                    "decision": last_decision,
                                },
                            )
                        )
                    elif last_mode in {"hold", "promote", "reject"}:
                        self.events.append(
                            EventRecord.create(
                                "soak.observed",
                                "supervisor",
                                {
                                    "active_soak": active_soak,
                                    "mode": last_mode,
                                    "regime": last_regime,
                                    "decision": last_decision,
                                },
                            )
                        )
                    previous_soak = active_soak
            if job.job_type == "runtime_summary":
                last_summary = output

            if code != 0 and job.job_type not in {"runtime_summary"}:
                had_error = True
                self.persist_state(last_error=output, last_step=job.job_type, last_mode=last_mode, last_regime=last_regime, active_soak=active_soak)
                break

        final_status = "error" if had_error else "ok"
        self.persist_state(
            last_finished_at=now_iso(),
            last_status=final_status,
            last_mode=last_mode,
            last_regime=last_regime,
            last_decision=last_decision,
            last_summary=last_summary,
            active_soak=active_soak,
        )
        self.events.append(EventRecord.create("loop.finished", "supervisor", {"loop_count": loop_count, "status": final_status}))
        return not had_error

    def run_forever(self) -> int:
        if not self.enabled:
            append_log("supervisor_disabled")
            self.persist_state(last_status="disabled", last_mode="disabled")
            return 1

        PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
        append_log(f"supervisor_started interval_seconds={self.interval_seconds}")
        self.events.append(EventRecord.create("supervisor.started", "supervisor", {"interval_seconds": self.interval_seconds}))
        self.persist_state(started_at=now_iso(), last_status="started", interval_seconds=self.interval_seconds)

        while not STOP:
            ok = self.run_once()
            sleep_until = time.time() + self.interval_seconds
            self.persist_state(next_run_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sleep_until)), last_status="ok" if ok else "error")
            while not STOP and time.time() < sleep_until:
                time.sleep(min(5, max(1, int(sleep_until - time.time()))))

        self.events.append(EventRecord.create("supervisor.stopped", "supervisor", {}))
        append_log("supervisor_stopped")
        self.persist_state(last_status="stopped", stopped_at=now_iso())
        if PID_PATH.exists():
            PID_PATH.unlink()
        return 0


def main() -> int:
    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)
    return Supervisor().run_forever()


if __name__ == "__main__":
    raise SystemExit(main())

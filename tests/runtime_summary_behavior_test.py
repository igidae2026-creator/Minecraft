from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from helpers import ROOT, dump_yaml


def _backup_runtime(tmp_path: Path) -> Path:
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    return backup


def _restore_runtime(backup: Path) -> None:
    runtime_data = ROOT / "runtime_data"
    shutil.rmtree(runtime_data)
    shutil.copytree(backup, runtime_data, dirs_exist_ok=True)


def test_runtime_summary_reports_operator_surfaces(tmp_path: Path):
    backup = _backup_runtime(tmp_path)
    try:
        status_dir = ROOT / "runtime_data" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        for path in status_dir.glob("*.yml"):
            path.unlink()
        control_dir = ROOT / "runtime_data" / "autonomy" / "control"
        control_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "session_authority_service": {
                "session_ownership_conflicts": 2,
                "split_brain_detections": 1,
            },
            "deterministic_transfer_service": {
                "lease_verification_failures": 3,
                "quarantines": 1,
            },
            "reconciliation_mismatches": 4,
            "guild_value_drift": 2,
            "item_ownership_conflicts": 1,
            "economy_item_authority_plane": {"quarantined_items": 5},
            "exploit_forensics_plane": {"incident_total": 6},
            "orphan_instances": 2,
            "instance_cleanup_failures": 1,
            "experiment_registry": {"rollbacks": 2},
            "policy_registry": {"rollbacks": 1},
            "runtime_knowledge_index": {"records": 7},
        }
        (status_dir / "summary-test.yml").write_text(dump_yaml(status), encoding="utf-8")
        (control_dir / "state.yml").write_text(
            dump_yaml(
                {
                    "last_mode": "hold",
                    "last_regime": "pressured",
                    "active_soak": {"decision_id": "aql-test"},
                    "last_soak_resolution": {"resolution": "promote"},
                    "steady_noop_streak": 2,
                    "final_threshold_ready": False,
                }
            ),
            encoding="utf-8",
        )
        (ROOT / "runtime_data" / "autonomy" / "final_threshold_eval.json").write_text(
            '{"final_threshold_ready": false, "failed_criteria": ["long_soak_steady_noop"], "quality_lift_if_human_intervenes": 0.28}',
            encoding="utf-8",
        )

        result = subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_summary.py")], cwd=ROOT, capture_output=True, text=True, check=True)

        assert "RUNTIME_SUMMARY" in result.stdout
        assert "AUTONOMY_LAST_MODE=hold" in result.stdout
        assert "AUTONOMY_LAST_REGIME=pressured" in result.stdout
        assert "AUTONOMY_ACTIVE_SOAK=aql-test" in result.stdout
        assert "AUTONOMY_LAST_SOAK_RESOLUTION=promote" in result.stdout
        assert "AUTONOMY_STEADY_NOOP_STREAK=2" in result.stdout
        assert "AUTONOMY_FINAL_THRESHOLD_READY=0" in result.stdout
        assert "SESSION_AUTHORITY_CONFLICTS=2" in result.stdout
        assert "SESSION_SPLIT_BRAIN=1" in result.stdout
        assert "TRANSFER_FAILURES=3" in result.stdout
        assert "TRANSFER_QUARANTINES=1" in result.stdout
        assert "GUILD_DRIFT=2" in result.stdout
        assert "ITEM_QUARANTINE=6" in result.stdout
        assert "EXPLOIT_INCIDENTS=6" in result.stdout
        assert "INSTANCE_LEAKS=3" in result.stdout
        assert "EXPERIMENT_ANOMALIES=3" in result.stdout
        assert "KNOWLEDGE_RECORDS=7" in result.stdout
        assert "FINAL_THRESHOLD_BUNDLE_READY=0" in result.stdout
    finally:
        _restore_runtime(backup)


def test_runtime_summary_refreshes_stale_final_threshold_bundle(tmp_path: Path):
    backup = _backup_runtime(tmp_path)
    try:
        runtime_data = ROOT / "runtime_data"
        control_dir = runtime_data / "autonomy" / "control"
        supervisor_dir = runtime_data / "autonomy" / "supervisor"
        core_dir = runtime_data / "autonomy" / "core"
        audit_dir = runtime_data / "audit"
        autonomy_dir = runtime_data / "autonomy"
        status_dir = runtime_data / "status"
        for directory in (control_dir, supervisor_dir, core_dir, audit_dir, autonomy_dir, status_dir):
            directory.mkdir(parents=True, exist_ok=True)

        (control_dir / "state.yml").write_text(
            dump_yaml(
                {
                    "last_mode": "noop",
                    "last_regime": "steady",
                    "steady_noop_streak": 12,
                    "execution_threshold_ready": True,
                    "operational_threshold_ready": True,
                    "autonomy_threshold_ready": True,
                    "final_threshold_ready": True,
                }
            ),
            encoding="utf-8",
        )
        (supervisor_dir / "heartbeat.json").write_text(
            '{"last_status":"ok","queue_pending":0,"active_soak":"","loop_count":1}',
            encoding="utf-8",
        )
        (core_dir / "event_log.jsonl").write_text(
            '\n'.join(
                [
                    '{"event_type":"queue.seeded","payload":{"job_types":["autonomous_quality_loop","runtime_summary","content_governor","economy_governor","anti_cheat_governor","liveops_governor"]}}',
                    '{"event_type":"job.done","payload":{"job_type":"autonomous_quality_loop"}}',
                    '{"event_type":"job.done","payload":{"job_type":"runtime_summary"}}',
                    '{"event_type":"job.done","payload":{"job_type":"content_governor"}}',
                    '{"event_type":"job.done","payload":{"job_type":"economy_governor"}}',
                    '{"event_type":"job.done","payload":{"job_type":"anti_cheat_governor"}}',
                    '{"event_type":"job.done","payload":{"job_type":"liveops_governor"}}',
                    '{"event_type":"loop.finished","payload":{"status":"ok"}}',
                ]
            ) + '\n',
            encoding="utf-8",
        )
        (autonomy_dir / "final_threshold_eval.json").write_text(
            '{"final_threshold_ready": false, "failed_criteria": ["stale"]}',
            encoding="utf-8",
        )
        (autonomy_dir / "artifact_governor_summary.yml").write_text("canonical_registry:\n- minecraft_runtime:consumer_health_rollup\n", encoding="utf-8")
        (autonomy_dir / "content_governor_summary.yml").write_text("generated: 3\npromoted: 3\nheld: 0\n", encoding="utf-8")
        (autonomy_dir / "economy_governor_summary.yml").write_text("action: observe\ninflation_ratio: 1.1\n", encoding="utf-8")
        (autonomy_dir / "anti_cheat_governor_summary.yml").write_text("sandbox_cases: 1\nmode: observe_and_replay\n", encoding="utf-8")
        (autonomy_dir / "liveops_governor_summary.yml").write_text("promoted_actions: 2\nheld_actions: 0\n", encoding="utf-8")
        (control_dir / "lineage.jsonl").write_text('{"decision_id":"aql-1"}\n', encoding="utf-8")
        (audit_dir / "COVERAGE_AUDIT.yml").write_text("gaps: []\n", encoding="utf-8")
        (audit_dir / "CONFLICT_LOG.jsonl").write_text('{"tension":"tracked"}\n', encoding="utf-8")
        (status_dir / "lobby.yml").write_text(
            dump_yaml(
                {
                    "queue_size": 1,
                    "dungeon_completed": 2,
                    "event_started": 1,
                    "reconciliation_mismatches": 0,
                    "item_ownership_conflicts": 0,
                    "deterministic_transfer_service": {"quarantines": 0},
                    "session_authority_service": {"split_brain_detections": 0},
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_summary.py")], cwd=ROOT, capture_output=True, text=True, check=True)

        assert "AUTONOMY_FINAL_THRESHOLD_READY=1" in result.stdout
        assert "FINAL_THRESHOLD_BUNDLE_READY=1" in result.stdout
    finally:
        _restore_runtime(backup)


def test_reconcile_runtime_fails_closed_on_transfer_quarantine_and_split_brain(tmp_path: Path):
    backup = _backup_runtime(tmp_path)
    try:
        status_dir = ROOT / "runtime_data" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "deterministic_transfer_service": {"quarantines": 1},
            "session_authority_service": {"split_brain_detections": 1},
        }
        (status_dir / "fault-test.yml").write_text(dump_yaml(status), encoding="utf-8")

        result = subprocess.run([sys.executable, str(ROOT / "ops" / "reconcile_runtime.py")], cwd=ROOT, capture_output=True, text=True)

        assert result.returncode == 1
        assert "ERROR: transfer_quarantine:fault-test" in result.stdout
        assert "ERROR: split_brain:fault-test" in result.stdout
    finally:
        _restore_runtime(backup)

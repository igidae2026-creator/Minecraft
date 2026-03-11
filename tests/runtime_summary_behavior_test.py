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

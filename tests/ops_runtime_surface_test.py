from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import shutil
import yaml

from helpers import ROOT, dump_yaml

sys.path.insert(0, str(ROOT / "ops"))
from autonomy_core import JobQueue, PolicyLayer


def test_ops_truth_and_reconciliation_surfaces_execute_cleanly(tmp_path: Path):
    subprocess.run([sys.executable, str(ROOT / "ops" / "validate_runtime_truth.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "reconcile_runtime.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--dry-run"], check=True, cwd=ROOT)

    metrics_path = tmp_path / "metrics.prom"
    subprocess.run(["bash", str(ROOT / "ops" / "metrics_exporter.sh"), str(metrics_path)], check=True, cwd=ROOT)
    text = metrics_path.read_text(encoding="utf-8")
    assert "rpg_network_runtime_experiment_exports" in text
    assert "rpg_network_runtime_incident_exports" in text


def test_runbook_and_cluster_orchestration_surfaces_exist():
    assert (ROOT / "ops" / "RUNBOOK.md").is_file()
    assert (ROOT / "ops" / "orchestrate_cluster.sh").is_file()
    assert (ROOT / "ops" / "close_quality_loop.sh").is_file()
    assert (ROOT / "ops" / "recover_runtime.sh").is_file()


def test_policy_layer_seeds_soak_observation_jobs(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    try:
        control_dir = runtime_data / "autonomy" / "control"
        control_dir.mkdir(parents=True, exist_ok=True)
        (control_dir / "state.yml").write_text(
            dump_yaml({"active_soak": {"decision_id": "aql-soak"}}),
            encoding="utf-8",
        )
        queue = JobQueue()
        seeded = PolicyLayer().seed_jobs(queue, loop_count=6)
        job_types = [job.job_type for job in seeded]
        assert "autonomous_quality_loop" in job_types
        assert "closed_loop_matrix" not in job_types
        assert "runtime_summary" in job_types
        assert job_types[-2:] == ["final_threshold_eval", "final_threshold_repair"]
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)


def test_simulated_feedback_respects_market_tax_control_surface(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    config_dir = ROOT / "configs"
    runtime_backup = tmp_path / "runtime_backup"
    config_backup = tmp_path / "config_backup"
    shutil.copytree(runtime_data, runtime_backup, dirs_exist_ok=True)
    shutil.copytree(config_dir, config_backup, dirs_exist_ok=True)
    try:
        status_dir = runtime_data / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        for path in status_dir.glob("*.yml"):
            path.unlink()
        fixtures = {
            "lobby.yml": {"role": "lobby"},
            "rpg_world.yml": {"role": "progression"},
            "dungeons.yml": {"role": "instance"},
            "boss_world.yml": {"role": "boss"},
            "events.yml": {"role": "event"},
        }
        for name, payload in fixtures.items():
            (status_dir / name).write_text(dump_yaml(payload), encoding="utf-8")

        economy_path = config_dir / "economy.yml"
        economy = yaml.safe_load(economy_path.read_text(encoding="utf-8"))
        economy["market_tax"] = 0.15
        economy_path.write_text(dump_yaml(economy, sort_keys=False), encoding="utf-8")

        subprocess.run(
            [sys.executable, str(ROOT / "ops" / "simulate_runtime_feedback.py"), "--cycles", "1", "--profile", "healthy", "--mode", "replace"],
            check=True,
            cwd=ROOT,
        )

        earn = 0
        spend = 0
        for path in status_dir.glob("*.yml"):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            earn += int(payload.get("economy_earn", 0))
            spend += int(payload.get("economy_spend", 0))
        assert spend > 0
        assert (earn / spend) < 1.2
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(runtime_backup, runtime_data, dirs_exist_ok=True)
        if config_dir.exists():
            shutil.rmtree(config_dir, ignore_errors=True)
        shutil.copytree(config_backup, config_dir, dirs_exist_ok=True)


def test_artifact_governor_creates_canonical_operating_artifacts(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    try:
        control_dir = runtime_data / "autonomy" / "control"
        control_dir.mkdir(parents=True, exist_ok=True)
        (control_dir / "state.yml").write_text(
            dump_yaml(
                {
                    "execution_threshold_ready": True,
                    "operational_threshold_ready": True,
                    "autonomy_threshold_ready": True,
                    "final_threshold_ready": True,
                    "steady_noop_streak": 12,
                    "last_decision_path": "runtime_data/autonomy/decisions/example.yml",
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run([sys.executable, str(ROOT / "ops" / "artifact_governor.py")], check=True, cwd=ROOT, capture_output=True, text=True)
        proposal_dir = runtime_data / "artifact_proposals"
        canonical_dir = runtime_data / "canonical_artifacts"
        summary = yaml.safe_load((runtime_data / "autonomy" / "artifact_governor_summary.yml").read_text(encoding="utf-8"))

        assert "ARTIFACT_GOVERNOR" in result.stdout
        assert summary["proposed"] >= 4
        assert summary["accepted"] >= 4
        assert len(list(proposal_dir.glob("*.yml"))) >= 4
        assert len(list(canonical_dir.glob("*.yml"))) >= 4
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)


def test_specialized_governors_create_operating_artifacts(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    try:
        control_dir = runtime_data / "autonomy" / "control"
        control_dir.mkdir(parents=True, exist_ok=True)
        (control_dir / "state.yml").write_text(
            dump_yaml(
                {
                    "autonomy_threshold_ready": True,
                    "execution_threshold_ready": True,
                    "operational_threshold_ready": True,
                    "steady_noop_streak": 12,
                }
            ),
            encoding="utf-8",
        )
        status_dir = runtime_data / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "lobby.yml").write_text(
            dump_yaml(
                {
                    "economy_earn": 160,
                    "economy_spend": 100,
                    "exploit_flag": 1,
                    "exploit_forensics_plane": {"incident_total": 1.0},
                }
            ),
            encoding="utf-8",
        )

        subprocess.run([sys.executable, str(ROOT / "ops" / "content_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "economy_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "anti_cheat_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "liveops_governor.py")], check=True, cwd=ROOT)

        assert len(list((runtime_data / "content_pipeline").rglob("*.yml"))) >= 1
        assert len(list((runtime_data / "economy_operations").glob("*.yml"))) >= 1
        assert len(list((runtime_data / "anti_cheat").glob("*.yml"))) >= 1
        assert len(list((runtime_data / "live_ops").glob("*.yml"))) >= 1
        content_summary = yaml.safe_load((runtime_data / "autonomy" / "content_governor_summary.yml").read_text(encoding="utf-8"))
        economy_summary = yaml.safe_load((runtime_data / "autonomy" / "economy_governor_summary.yml").read_text(encoding="utf-8"))
        anti_cheat_summary = yaml.safe_load((runtime_data / "autonomy" / "anti_cheat_governor_summary.yml").read_text(encoding="utf-8"))
        liveops_summary = yaml.safe_load((runtime_data / "autonomy" / "liveops_governor_summary.yml").read_text(encoding="utf-8"))

        assert content_summary["generated"] >= 8
        assert content_summary["by_type"]["onboarding"] >= 1
        assert content_summary["by_type"]["social"] >= 1
        assert economy_summary["action"] in {"adjust", "observe"}
        assert anti_cheat_summary["sandbox_cases"] >= 1
        assert liveops_summary["promoted_actions"] >= 1
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)


def test_final_threshold_eval_and_repair_bundle(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    try:
        control_dir = runtime_data / "autonomy" / "control"
        control_dir.mkdir(parents=True, exist_ok=True)
        (control_dir / "state.yml").write_text(
            dump_yaml(
                {
                    "last_mode": "noop",
                    "last_regime": "steady",
                    "steady_noop_streak": 2,
                    "execution_threshold_ready": True,
                    "operational_threshold_ready": False,
                    "autonomy_threshold_ready": False,
                    "final_threshold_ready": False,
                }
            ),
            encoding="utf-8",
        )
        supervisor_dir = runtime_data / "autonomy" / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)
        (supervisor_dir / "heartbeat.json").write_text(
            '{"last_status":"ok","queue_pending":0,"active_soak":"","loop_count":1}',
            encoding="utf-8",
        )
        core_dir = runtime_data / "autonomy" / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
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
        decisions_dir = runtime_data / "autonomy" / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        (decisions_dir / "demo.yml").write_text("mode: noop\n", encoding="utf-8")
        (control_dir / "lineage.jsonl").write_text('{"decision_id":"aql-1"}\n', encoding="utf-8")
        audit_dir = runtime_data / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "COVERAGE_AUDIT.yml").write_text("gaps: []\n", encoding="utf-8")
        (audit_dir / "CONFLICT_LOG.jsonl").write_text('{"tension":"tracked"}\n', encoding="utf-8")
        status_dir = runtime_data / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        for name in ("lobby", "rpg_world", "dungeons", "boss_world", "events"):
            (status_dir / f"{name}.yml").write_text(
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
        autonomy_dir = runtime_data / "autonomy"
        (autonomy_dir / "artifact_governor_summary.yml").write_text("canonical_registry:\n- minecraft_runtime:consumer_health_rollup\n", encoding="utf-8")
        (autonomy_dir / "content_governor_summary.yml").write_text("generated: 3\npromoted: 3\nheld: 0\n", encoding="utf-8")
        (autonomy_dir / "economy_governor_summary.yml").write_text("action: observe\ninflation_ratio: 1.1\n", encoding="utf-8")
        (autonomy_dir / "anti_cheat_governor_summary.yml").write_text("sandbox_cases: 1\nmode: observe_and_replay\n", encoding="utf-8")
        (autonomy_dir / "liveops_governor_summary.yml").write_text("promoted_actions: 2\nheld_actions: 0\n", encoding="utf-8")

        subprocess.run([sys.executable, str(ROOT / "ops" / "final_threshold_eval.py")], check=True, cwd=ROOT)
        result = subprocess.run([sys.executable, str(ROOT / "ops" / "final_threshold_repair.py")], check=True, cwd=ROOT, capture_output=True, text=True)
        payload = json.loads((runtime_data / "autonomy" / "final_threshold_eval.json").read_text(encoding="utf-8"))

        assert payload["final_threshold_ready"] is False
        assert "long_soak_steady_noop" in payload["failed_criteria"]
        assert "autonomous_quality_loop" in payload["next_required_repairs"]
        assert "ENQUEUED=" in result.stdout
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)

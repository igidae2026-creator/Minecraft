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
        jobs_root = runtime_data / "autonomy" / "core" / "jobs"
        if jobs_root.exists():
            shutil.rmtree(jobs_root, ignore_errors=True)
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
        autonomy_dir = runtime_data / "autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)
        (autonomy_dir / "content_governor_summary.yml").write_text(
            "generated: 16\npromoted: 7\nheld: 9\naverage_depth_score: 1.99\naverage_retention_proxy: 1.59\naverage_quality_score: 8.0\nfirst_loop_coverage_score: 2.4\nsocial_loop_density: 1.8\nreplayable_loop_score: 2.1\n",
            encoding="utf-8",
        )
        (autonomy_dir / "content_strategy_summary.yml").write_text(
            "next_focus_csv: social,event,onboarding\nrecommended_repairs_csv: content_governor,liveops_governor,economy_governor,anti_cheat_governor\nrecommended_repairs_count: 4\nruntime_queue_avg: 5.2\nruntime_event_join_avg: 808.4\nruntime_return_player_reward_avg: 47.0\n",
            encoding="utf-8",
        )
        (autonomy_dir / "repo_bundle_summary.yml").write_text(
            "bundle_total: 7\nbundle_completed: 7\nbundle_completion_percent: 100.0\ngovernance_bundle_state: complete\nautonomy_bundle_state: complete\ndocs_information_architecture_bundle_state: complete\n",
            encoding="utf-8",
        )
        (autonomy_dir / "minecraft_bundle_summary.yml").write_text(
            "bundle_total: 5\nbundle_completed: 5\nbundle_completion_percent: 100.0\ngameplay_progression_bundle_state: complete\neconomy_market_bundle_state: complete\nsocial_liveops_bundle_state: complete\nanti_cheat_recovery_bundle_state: complete\ngovernance_autonomy_bundle_state: complete\n",
            encoding="utf-8",
        )
        (autonomy_dir / "minecraft_strategy_summary.yml").write_text(
            "next_focus_csv: anti_cheat_recovery,gameplay_progression,social_liveops\nrecommended_repairs_csv: anti_cheat_governor,content_governor,liveops_governor\nrecommended_repairs_count: 3\ntop_focus_domain: anti_cheat_recovery\ninflation_ratio: 0.94\nsandbox_cases: 1\ncontent_soak_state: tune\n",
            encoding="utf-8",
        )
        (autonomy_dir / "player_experience_summary.yml").write_text(
            "estimated_completeness_percent: 22.4\nexperience_state: early\nonboarding_tempo: 0.41\nreward_tempo: 0.44\nsocial_stickiness: 0.33\nreplay_pull: 0.38\nfriction_penalty: 0.12\n",
            encoding="utf-8",
        )
        (autonomy_dir / "engagement_fatigue_summary.yml").write_text(
            "fatigue_gap_score: 0.31\nfatigue_state: watch\nthinness_score: 0.34\nrepetition_score: 0.29\nnovelty_gap_score: 0.28\n",
            encoding="utf-8",
        )
        (autonomy_dir / "player_experience_soak_summary.yml").write_text(
            "player_experience_soak_state: observe\nestimated_completeness_percent: 22.4\nexperience_state: early\ncombined_recommended_repairs_count: 4\n",
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
        assert "CANONICAL=minecraft_runtime:content_quality_profile" in result.stdout
        assert "CANONICAL=minecraft_runtime:content_portfolio_strategy" in result.stdout
        assert "CANONICAL=minecraft_runtime:repo_bundle_profile" in result.stdout
        assert "CANONICAL=minecraft_runtime:minecraft_domain_bundle_profile" in result.stdout
        assert "CANONICAL=minecraft_runtime:minecraft_domain_strategy" in result.stdout
        assert "CANONICAL=minecraft_runtime:player_experience_profile" in result.stdout
        assert "CANONICAL=minecraft_runtime:engagement_fatigue_profile" in result.stdout
        assert "CANONICAL=minecraft_runtime:player_experience_soak_report" in result.stdout
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
        subprocess.run([sys.executable, str(ROOT / "ops" / "player_experience_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "gameplay_progression_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "engagement_fatigue_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "material_inventory.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_partition_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "content_strategy_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "content_soak_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "content_bundle_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "repo_bundle_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "minecraft_bundle_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "minecraft_strategy_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "player_experience_soak_governor.py")], check=True, cwd=ROOT)
        subprocess.run([sys.executable, str(ROOT / "ops" / "minecraft_soak_governor.py")], check=True, cwd=ROOT)

        assert len(list((runtime_data / "content_pipeline").rglob("*.yml"))) >= 1
        assert len(list((runtime_data / "economy_operations").glob("*.yml"))) >= 1
        assert len(list((runtime_data / "anti_cheat").glob("*.yml"))) >= 1
        assert len(list((runtime_data / "live_ops").glob("*.yml"))) >= 1
        assert (runtime_data / "audit" / "MATERIAL_INVENTORY.yml").is_file()
        content_summary = yaml.safe_load((runtime_data / "autonomy" / "content_governor_summary.yml").read_text(encoding="utf-8"))
        economy_summary = yaml.safe_load((runtime_data / "autonomy" / "economy_governor_summary.yml").read_text(encoding="utf-8"))
        anti_cheat_summary = yaml.safe_load((runtime_data / "autonomy" / "anti_cheat_governor_summary.yml").read_text(encoding="utf-8"))
        liveops_summary = yaml.safe_load((runtime_data / "autonomy" / "liveops_governor_summary.yml").read_text(encoding="utf-8"))
        material_summary = yaml.safe_load((runtime_data / "autonomy" / "material_inventory_summary.yml").read_text(encoding="utf-8"))
        partition_summary = yaml.safe_load((runtime_data / "autonomy" / "runtime_partition_summary.yml").read_text(encoding="utf-8"))
        strategy_summary = yaml.safe_load((runtime_data / "autonomy" / "content_strategy_summary.yml").read_text(encoding="utf-8"))
        soak_summary = yaml.safe_load((runtime_data / "autonomy" / "content_soak_summary.yml").read_text(encoding="utf-8"))
        bundle_summary = yaml.safe_load((runtime_data / "autonomy" / "content_bundle_summary.yml").read_text(encoding="utf-8"))
        repo_bundle_summary = yaml.safe_load((runtime_data / "autonomy" / "repo_bundle_summary.yml").read_text(encoding="utf-8"))
        minecraft_bundle_summary = yaml.safe_load((runtime_data / "autonomy" / "minecraft_bundle_summary.yml").read_text(encoding="utf-8"))
        minecraft_strategy_summary = yaml.safe_load((runtime_data / "autonomy" / "minecraft_strategy_summary.yml").read_text(encoding="utf-8"))
        minecraft_soak_summary = yaml.safe_load((runtime_data / "autonomy" / "minecraft_soak_summary.yml").read_text(encoding="utf-8"))
        player_experience_summary = yaml.safe_load((runtime_data / "autonomy" / "player_experience_summary.yml").read_text(encoding="utf-8"))
        player_experience_soak_summary = yaml.safe_load((runtime_data / "autonomy" / "player_experience_soak_summary.yml").read_text(encoding="utf-8"))
        gameplay_progression_summary = yaml.safe_load((runtime_data / "autonomy" / "gameplay_progression_summary.yml").read_text(encoding="utf-8"))
        engagement_fatigue_summary = yaml.safe_load((runtime_data / "autonomy" / "engagement_fatigue_summary.yml").read_text(encoding="utf-8"))

        assert content_summary["generated"] >= 14
        assert content_summary["by_type"]["onboarding"] >= 1
        assert content_summary["by_type"]["social"] >= 1
        assert content_summary["by_type"]["quest_chain"] >= 1
        assert content_summary["by_type"]["dungeon_variation"] >= 1
        assert content_summary["by_type"]["season"] >= 1
        assert content_summary["average_depth_score"] > 0
        assert content_summary["average_quality_score"] > 0
        assert float(content_summary["first_loop_coverage_score"]) >= 2.0
        assert float(content_summary["social_loop_density"]) >= 1.5
        assert float(content_summary["replayable_loop_score"]) >= 1.5
        assert economy_summary["action"] in {"adjust", "observe"}
        assert anti_cheat_summary["sandbox_cases"] >= 1
        assert float(anti_cheat_summary["progression_protection_score"]) >= 0
        assert liveops_summary["promoted_actions"] >= 1
        assert isinstance(liveops_summary["boost_reentry"], bool)
        assert float(gameplay_progression_summary["progression_total_score"]) >= 0
        assert gameplay_progression_summary["progression_state"] in {"early", "mid", "advanced"}
        assert float(engagement_fatigue_summary["fatigue_gap_score"]) >= 0
        assert engagement_fatigue_summary["fatigue_state"] in {"low", "watch", "high"}
        assert material_summary["canonical_source_files"] > 0
        assert partition_summary["runtime_files"] >= partition_summary["canonical_snapshot_files"]
        assert partition_summary["volatile_runtime_files"] >= 1
        assert len([item for item in strategy_summary["next_focus_csv"].split(",") if item]) == 3
        assert strategy_summary["candidate_count"] >= 8
        assert float(strategy_summary["runtime_event_join_avg"]) >= 0
        assert float(strategy_summary["runtime_queue_avg"]) >= 0
        assert soak_summary["content_soak_state"] in {"active", "observe", "tune", "stable"}
        assert int(bundle_summary["bundle_total"]) == 7
        assert int(bundle_summary["bundle_completed"]) >= 1
        assert bundle_summary["player_facing_depth_state"] in {"partial", "complete"}
        assert int(repo_bundle_summary["bundle_total"]) == 7
        assert int(repo_bundle_summary["bundle_completed"]) >= 1
        assert int(minecraft_bundle_summary["bundle_total"]) == 6
        assert int(minecraft_bundle_summary["bundle_completed"]) >= 1
        assert minecraft_bundle_summary["player_experience_bundle_state"] in {"partial", "complete"}
        assert int(minecraft_strategy_summary["recommended_repairs_count"]) >= 1
        assert len([item for item in minecraft_strategy_summary["next_focus_csv"].split(",") if item]) == 3
        assert float(minecraft_strategy_summary["estimated_completeness_percent"]) >= 0
        assert minecraft_strategy_summary["experience_state"] in {"early", "mid", "advanced"}
        assert minecraft_soak_summary["minecraft_soak_state"] in {"tune", "observe", "stable"}
        assert float(player_experience_summary["estimated_completeness_percent"]) >= 0
        assert player_experience_summary["experience_state"] in {"early", "mid", "advanced"}
        assert float(player_experience_summary["first_session_strength"]) >= 0
        assert float(player_experience_summary["trust_pull"]) >= 0
        assert player_experience_soak_summary["player_experience_soak_state"] in {"tune", "observe", "stable"}
        assert float(player_experience_soak_summary["first_session_strength"]) >= 0
        assert float(player_experience_soak_summary["trust_pull"]) >= 0
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
        (autonomy_dir / "artifact_governor_summary.yml").write_text(
            "canonical_registry:\n"
            "- minecraft_runtime:consumer_health_rollup\n"
            "- minecraft_runtime:content_portfolio_strategy\n"
            "- minecraft_runtime:content_soak_report\n"
            "- minecraft_runtime:minecraft_domain_strategy\n"
            "- minecraft_runtime:minecraft_domain_soak_report\n"
            "- minecraft_runtime:player_experience_profile\n",
            encoding="utf-8",
        )
        (autonomy_dir / "engagement_fatigue_summary.yml").write_text(
            "fatigue_gap_score: 0.25\nfatigue_state: low\nthinness_score: 0.21\nrepetition_score: 0.28\nnovelty_gap_score: 0.26\n",
            encoding="utf-8",
        )
        (autonomy_dir / "content_governor_summary.yml").write_text("generated: 3\npromoted: 3\nheld: 0\n", encoding="utf-8")
        (autonomy_dir / "economy_governor_summary.yml").write_text("action: observe\ninflation_ratio: 1.1\n", encoding="utf-8")
        (autonomy_dir / "anti_cheat_governor_summary.yml").write_text("sandbox_cases: 1\nmode: observe_and_replay\n", encoding="utf-8")
        (autonomy_dir / "liveops_governor_summary.yml").write_text("promoted_actions: 2\nheld_actions: 0\n", encoding="utf-8")
        (autonomy_dir / "content_strategy_summary.yml").write_text(
            "next_focus_csv: social,event,onboarding\nrecommended_repairs_csv: content_governor,liveops_governor\nrecommended_repairs_count: 2\n",
            encoding="utf-8",
        )
        (autonomy_dir / "content_soak_summary.yml").write_text(
            "content_soak_state: stable\nsteady_noop_streak: 12\nrecommended_repairs_count: 0\ncontent_next_focus_csv: social,event,onboarding\n",
            encoding="utf-8",
        )
        (autonomy_dir / "content_bundle_summary.yml").write_text(
            "bundle_total: 6\nbundle_completed: 6\nbundle_completion_percent: 100.0\n",
            encoding="utf-8",
        )
        (autonomy_dir / "repo_bundle_summary.yml").write_text(
            "bundle_total: 7\nbundle_completed: 7\nbundle_completion_percent: 100.0\n",
            encoding="utf-8",
        )
        (autonomy_dir / "minecraft_bundle_summary.yml").write_text(
            "bundle_total: 6\nbundle_completed: 6\nbundle_completion_percent: 100.0\n",
            encoding="utf-8",
        )
        (autonomy_dir / "minecraft_strategy_summary.yml").write_text(
            "next_focus_csv: gameplay_progression,social_liveops,anti_cheat_recovery\nrecommended_repairs_csv: content_governor,player_experience_governor,player_experience_soak_governor\nrecommended_repairs_count: 3\n",
            encoding="utf-8",
        )
        (autonomy_dir / "minecraft_soak_summary.yml").write_text(
            "minecraft_soak_state: observe\nsteady_noop_streak: 12\nrecommended_repairs_count: 1\nminecraft_bundle_completion_percent: 100.0\n",
            encoding="utf-8",
        )
        (autonomy_dir / "player_experience_summary.yml").write_text(
            "estimated_completeness_percent: 37.6\nexperience_state: mid\nfriction_penalty: 0.15\n",
            encoding="utf-8",
        )
        (autonomy_dir / "player_experience_soak_summary.yml").write_text(
            "player_experience_soak_state: observe\nestimated_completeness_percent: 37.6\nexperience_state: mid\ncombined_recommended_repairs_count: 3\n",
            encoding="utf-8",
        )

        subprocess.run([sys.executable, str(ROOT / "ops" / "final_threshold_eval.py")], check=True, cwd=ROOT)
        result = subprocess.run([sys.executable, str(ROOT / "ops" / "final_threshold_repair.py")], check=True, cwd=ROOT, capture_output=True, text=True)
        payload = json.loads((runtime_data / "autonomy" / "final_threshold_eval.json").read_text(encoding="utf-8"))

        assert payload["final_threshold_ready"] is False
        assert "long_soak_steady_noop" in payload["failed_criteria"]
        assert "autonomous_quality_loop" in payload["next_required_repairs"]
        assert "ENQUEUED=" in result.stdout
        assert "REPAIR=content_governor" in result.stdout
        assert "REPAIR=liveops_governor" in result.stdout
        assert "REPAIR=player_experience_soak_governor" in result.stdout
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)

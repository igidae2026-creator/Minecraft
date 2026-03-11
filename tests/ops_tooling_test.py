from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import shutil
import yaml

from helpers import ROOT, dump_yaml


def test_ops_tooling_executes_cleanly(tmp_path: Path):
    for relative in ("runtime_data/live_ops", "runtime_data/anti_cheat", "runtime_data/economy_operations", "runtime_data/content_pipeline", "runtime_data/content_volume"):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "ops" / "render_network.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "validate_rpg.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "rebuild_runtime_status.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_integrity.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_summary.py")], check=True, cwd=ROOT)
    subprocess.run(["bash", str(ROOT / "ops" / "healthcheck.sh")], check=True, cwd=ROOT)

    metrics_path = tmp_path / "metrics.prom"
    subprocess.run(["bash", str(ROOT / "ops" / "metrics_exporter.sh"), str(metrics_path)], check=True, cwd=ROOT)
    assert metrics_path.is_file()
    text = metrics_path.read_text(encoding="utf-8")
    assert "rpg_network_servers_total" in text
    assert "rpg_network_plugins_per_server" in text
    assert "rpg_network_runtime_artifact_exports" in text
    assert "rpg_network_runtime_experiment_exports" in text
    assert "rpg_network_runtime_incident_exports" in text
    assert "rpg_network_runtime_knowledge_exports" in text
    assert "rpg_network_autonomy_decisions_total" in text
    assert "rpg_network_autonomy_active_soak" in text
    assert "rpg_network_autonomy_control_lineage_entries" in text
    assert "rpg_network_content_generated" in text
    assert "rpg_network_content_families" in text
    assert "rpg_network_content_average_depth_score" in text
    assert "rpg_network_content_average_quality_score" in text
    assert "rpg_network_content_first_loop_coverage_score" in text
    assert "rpg_network_content_social_loop_density" in text
    assert "rpg_network_content_advanced_loop_strength" in text
    assert "rpg_network_content_prestige_loop_strength" in text
    assert "rpg_network_content_mastery_arc_strength" in text
    assert "rpg_network_content_prestige_clarity_strength" in text
    assert "rpg_network_content_endgame_breadth_strength" in text
    assert "rpg_network_content_social_persistence_strength" in text
    assert "rpg_network_content_spectacle_variety_strength" in text
    assert "rpg_network_content_returner_retention_strength" in text
    assert "rpg_network_content_starter_reward_strength" in text
    assert "rpg_network_content_rivalry_reward_pull" in text
    assert "rpg_network_content_volume_score" in text
    assert "rpg_network_content_recommended_repairs" in text
    assert "rpg_network_content_focus_families" in text
    assert "rpg_network_content_runtime_queue_avg" in text
    assert "rpg_network_content_runtime_event_join_avg" in text
    assert "rpg_network_gameplay_progression_total_score" in text
    assert "rpg_network_engagement_fatigue_gap_score" in text
    assert "rpg_network_content_soak_recommended_repairs" in text
    assert "rpg_network_content_bundle_completed" in text
    assert "rpg_network_content_bundle_completion_percent" in text
    assert "rpg_network_content_player_facing_depth_complete" in text
    assert "rpg_network_repo_bundle_completed" in text
    assert "rpg_network_repo_bundle_completion_percent" in text
    assert "rpg_network_minecraft_bundle_completed" in text
    assert "rpg_network_minecraft_bundle_completion_percent" in text
    assert "rpg_network_minecraft_recommended_repairs" in text
    assert "rpg_network_minecraft_soak_stable" in text
    assert "rpg_network_minecraft_long_soak_confidence" in text
    assert "rpg_network_player_experience_percent" in text
    assert "rpg_network_player_experience_first_session_strength" in text
    assert "rpg_network_player_experience_trust_pull" in text
    assert "rpg_network_player_experience_exploit_resilience" in text
    assert "rpg_network_player_experience_volume_pull" in text
    assert "rpg_network_player_experience_long_soak_confidence" in text
    assert "rpg_network_player_experience_soak_stable" in text
    assert "rpg_network_economy_inflation_ratio" in text
    assert "rpg_network_anti_cheat_sandbox_cases" in text
    assert "rpg_network_anti_cheat_progression_protection_score" in text
    assert "rpg_network_anti_cheat_exploit_resilience_score" in text
    assert "rpg_network_liveops_promoted_actions" in text
    assert "rpg_network_liveops_boost_reentry" in text
    assert "rpg_network_liveops_sustain_social" in text
    assert "rpg_network_liveops_boost_novelty" in text
    assert "rpg_network_liveops_returner_reactivation_depth" in text
    assert "rpg_network_liveops_depth_strength" in text
    assert "rpg_network_liveops_cadence_diversity_score" in text
    assert "rpg_network_material_total_files" in text
    assert "rpg_network_material_canonical_source_files" in text
    assert "rpg_network_runtime_partition_files" in text
    assert "rpg_network_runtime_partition_canonical_snapshot_files" in text
    assert "rpg_network_final_threshold_bundle_ready" in text
    assert "rpg_network_final_threshold_bundle_failed_criteria" in text

    for script in (ROOT / "ops").glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True, cwd=ROOT)


def test_metrics_exporter_reports_autonomy_control_state(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    try:
        control_dir = runtime_data / "autonomy" / "control"
        decision_dir = runtime_data / "autonomy" / "decisions"
        control_dir.mkdir(parents=True, exist_ok=True)
        decision_dir.mkdir(parents=True, exist_ok=True)
        for path in decision_dir.glob("*.yml"):
            path.unlink()
        (control_dir / "state.yml").write_text(
            dump_yaml({"active_soak": {"decision_id": "aql-observe"}}),
            encoding="utf-8",
        )
        (control_dir / "lineage.jsonl").write_text('{"decision_id":"aql-1"}\n{"decision_id":"aql-2"}\n', encoding="utf-8")
        (decision_dir / "20260311T000000Z_aql-demo.yml").write_text("decision_id: aql-demo\n", encoding="utf-8")

        metrics_path = tmp_path / "metrics.prom"
        subprocess.run(["bash", str(ROOT / "ops" / "metrics_exporter.sh"), str(metrics_path)], check=True, cwd=ROOT)
        text = metrics_path.read_text(encoding="utf-8")
        assert "rpg_network_autonomy_decisions_total 1" in text
        assert "rpg_network_autonomy_active_soak 1" in text
        assert "rpg_network_autonomy_control_lineage_entries 2" in text
    finally:
        if runtime_data.exists():
            shutil.rmtree(runtime_data, ignore_errors=True)
        shutil.copytree(backup, runtime_data, dirs_exist_ok=True)

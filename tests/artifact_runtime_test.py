from pathlib import Path

from helpers import ROOT, load_yaml


def test_runtime_artifact_and_item_authority_surfaces_exist():
    network = load_yaml("network.yml")
    persistence = load_yaml("persistence.yml")

    assert network["data_flow"]["gameplay_artifacts"] == "runtime_data/artifacts"
    assert network["data_flow"]["rare_item_authority"] == "local_manifest_plus_ledger_lineage"
    assert persistence["redis"]["required_for_session_authority"] is True

    assert (ROOT / "runtime_data" / "artifacts").is_dir()
    assert (ROOT / "runtime_data" / "policies").is_dir()
    assert (ROOT / "runtime_data" / "item_authority" / "owners").is_dir()
    assert (ROOT / "runtime_data" / "status").is_dir()


def test_metrics_and_health_surfaces_cover_new_failure_modes():
    metrics_source = (ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java").read_text(encoding="utf-8")
    core_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "rpg_runtime_item_ownership_conflicts_total" in metrics_source
    assert "rpg_runtime_instance_cleanup_failures_total" in metrics_source
    assert "rpg_runtime_policy_rollbacks_total" in metrics_source
    assert "ALERT guild_drift" in metrics_source
    assert "ALERT replay_divergence" in metrics_source
    assert "ALERT experiment_anomaly" in metrics_source
    assert 'yaml.set("instance_cleanup_latency_ms_avg"' in core_source
    assert 'yaml.set("item_ownership_conflicts"' in core_source
    assert 'yaml.set("artifact_exports"' in core_source

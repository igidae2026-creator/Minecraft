from helpers import ROOT, load_yaml


def test_control_planes_and_config_truth_alignment_present():
    core_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")
    metrics_source = (ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java").read_text(encoding="utf-8")
    network = load_yaml("configs/network.yml")
    scaling = load_yaml("configs/scaling.yml")

    assert "authorityPlane" in core_source
    assert "economyItemPlane" in core_source
    assert "instanceExperimentPlane" in core_source
    assert "exploitForensicsPlane" in core_source
    assert "sessionAuthorityService" in core_source
    assert "deterministicTransferService" in core_source
    assert "gameplayArtifactRegistry" in core_source
    assert "governancePolicyRegistry" in core_source
    assert "initializeControlPlanes" in core_source
    assert 'yaml.set("authority_plane", authority.getValues(true));' in core_source
    assert 'yaml.set("session_authority_service", sessionAuthority.getValues(true));' in core_source
    assert 'yaml.set("deterministic_transfer_service", transferAuthority.getValues(true));' in core_source
    assert 'yaml.set("economy_item_authority_plane", economyAuthority.getValues(true));' in core_source
    assert 'yaml.set("instance_experiment_control_plane", instanceControl.getValues(true));' in core_source
    assert 'yaml.set("exploit_forensics_plane", exploitForensics.getValues(true));' in core_source
    assert 'yaml.set("gameplay_artifact_registry", artifactRegistry.getValues(true));' in core_source
    assert 'yaml.set("governance_policy_registry", governanceRegistry.getValues(true));' in core_source

    assert "rpg_runtime_split_brain_detections_total" in metrics_source
    assert "rpg_runtime_item_quarantined_total" in metrics_source
    assert "ALERT split_brain" in metrics_source
    assert "ALERT anti_duplication_alarm" in metrics_source

    assert network["data_flow"]["live_session_state"] == "local_authoritative_lease_registry"
    assert scaling["mitigations"]["instance_world_reuse_pool"] is False
    assert scaling["operational"]["alert_split_brain"] >= 1
    assert scaling["operational"]["alert_item_duplication"] >= 1

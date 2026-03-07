from helpers import ROOT, load_yaml


def test_session_authority_runtime_is_truthful_and_not_redis_authoritative():
    network = load_yaml("network.yml")
    persistence = load_yaml("persistence.yml")
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "SessionAuthorityService.java").read_text(encoding="utf-8")

    assert network["data_flow"]["live_session_state"] == "local_authoritative_lease_registry"
    assert network["data_flow"]["live_session_coordination"] == "in_repo_deterministic_session_authority"
    assert persistence["redis"]["required_for_session_authority"] is False
    for marker in ("REGISTERED", "LEASED", "RECONNECT_HELD", "TRANSFERRING", "ACTIVE", "INVALIDATED", "EXPIRED"):
        assert marker in source


def test_deterministic_transfer_state_machine_is_explicit():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "DeterministicTransferService.java").read_text(encoding="utf-8")
    core = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    for marker in ("INITIATED", "PERSISTING", "LEASED", "ACTIVATING", "ACTIVE", "FAILED", "EXPIRED"):
        assert marker in source
    assert "deterministicTransferService.begin(" in core
    assert "deterministicTransferService.refuseStaleLoad(" in core
    assert "deterministicTransferService.transition(ticket.transferId(), DeterministicTransferService.TransferState.ACTIVE" in core


def test_artifact_governance_and_detector_registries_exist():
    artifact_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "GameplayArtifactRegistry.java").read_text(encoding="utf-8")
    governance_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "GovernancePolicyRegistry.java").read_text(encoding="utf-8")
    detector_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "ExploitDetectorRegistry.java").read_text(encoding="utf-8")

    assert "EXPLOIT_SIGNATURE" in artifact_source
    assert "RECOVERY_ACTION" in artifact_source
    assert "spawn_regulation" in governance_source
    assert "experiment_admission" in governance_source
    assert "quarantine_item" in detector_source
    assert "freeze_account" in detector_source

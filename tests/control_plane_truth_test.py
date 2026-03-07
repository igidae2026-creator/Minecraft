from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"


def _read(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_pressure_experiment_governance_and_knowledge_surfaces_are_truthful():
    network = load_yaml("network.yml")
    pressure = load_yaml("pressure.yml")
    experiments = load_yaml("experiments.yml")
    governance = load_yaml("governance.yml")
    service = _read("RpgNetworkService.java")

    assert network["data_flow"]["knowledge_index"] == "runtime_data/knowledge"
    assert network["data_flow"]["pressure_control"] == "runtime_data/status"
    assert pressure["controls"]["noncritical_spawn_suppression"] is True
    assert experiments["operations"]["attach_experiment_ids_to_mutations"] is True
    assert governance["operations"]["rollback_enabled"] is True
    for marker in ("experimentRegistry", "policyRegistry", "pressureControlPlane", "runtimeKnowledgeIndex"):
        assert marker in service


def test_transfer_and_instance_state_machines_cover_fail_closed_runtime_states():
    transfer = _read("DeterministicTransferService.java")
    instance_plane = _read("InstanceExperimentControlPlane.java")
    core = _read("RpgNetworkService.java")

    for marker in ("FREEZING", "ROLLED_BACK", "quarantine(", "ambiguity_failures"):
        assert marker in transfer
    for marker in ("DEGRADED", "REWARD_COMMIT", "ORPHANED"):
        assert marker in instance_plane
        assert marker in core


def test_artifact_registry_supports_experiment_governance_and_compensation_exports():
    artifacts = _read("GameplayArtifactRegistry.java")
    service = _read("RpgNetworkService.java")

    for marker in ("EXPERIMENT_DEFINITION", "EXPERIMENT_RESULT", "GOVERNANCE_DECISION", "COMPENSATION_ACTION", "usefulnessScore"):
        assert marker in artifacts
    for marker in ("exportArtifact(\"experiment_result\"", "exportArtifact(\"governance_decision\"", "writeYaml(knowledgeDir.resolve(", "runtimeKnowledgeIndex.remember("):
        assert marker in service

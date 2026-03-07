from helpers import ROOT


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
SESSION = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "SessionAuthorityService.java"
TRANSFER = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "DeterministicTransferService.java"
GOVERNANCE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "GovernancePolicyRegistry.java"


def _read(path):
    return path.read_text(encoding="utf-8")


def test_stale_transfer_load_duplicate_login_and_session_expiry_paths_exist():
    core = _read(CORE)
    session = _read(SESSION)
    transfer = _read(TRANSFER)

    assert "Travel version barrier profile mismatch" in core
    assert "Duplicate login rejected while existing authority session is live." in core
    assert "holdReconnect" in session
    assert "sweep(long now)" in session
    assert "stale_load_refusal" in transfer


def test_replay_divergence_ledger_mismatch_and_item_duplication_paths_exist():
    core = _read(CORE)

    assert "reconcileSnapshotsAgainstLedger()" in core
    assert "Replay divergence profile=" in core
    assert "Ledger duplicate payload mismatch" in core
    assert "duplicate_manifest_owner" in core


def test_orphan_recovery_experiment_rollback_and_policy_rollback_paths_exist():
    core = _read(CORE)
    governance = _read(GOVERNANCE)

    assert "instanceExperimentPlane.recoverOrphans(now);" in core
    assert "instanceExperimentPlane.registerExperiment" in core
    assert "policyRollbackCount()" in core
    assert "rollback(" in governance

from helpers import ROOT, load_yaml

CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
METRICS = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def _core() -> str:
    return CORE.read_text(encoding="utf-8")


def test_duplicate_login_conflict_is_fail_closed_and_counted():
    source = _core()
    assert "duplicateLoginRejects.incrementAndGet()" in source
    assert "Duplicate login rejected while existing authority session is live." in source
    assert 'writeAudit("duplicate_login_reject"' in source


def test_transfer_lease_expiry_is_observable_and_audited():
    source = _core()
    assert "transferLeaseExpiryCount.incrementAndGet()" in source
    assert 'writeAudit("transfer_lease_expired"' in source


def test_startup_reconciliation_quarantines_on_mismatch():
    source = _core()
    assert "runStartupConsistencyChecks()" in source
    assert "reconcileSnapshotsAgainstLedger()" in source
    assert "Startup reconciliation mismatch detected" in source
    assert "startupQuarantineCount.incrementAndGet()" in source


def test_config_declares_redis_authoritative_live_session_coordination():
    network = load_yaml("network.yml")
    assert network["data_flow"]["live_session_state"] == "redis_authoritative"
    assert network["data_flow"]["live_session_mirror"] == "redis"


def test_metrics_expose_new_authority_failure_modes():
    source = METRICS.read_text(encoding="utf-8")
    assert "rpg_runtime_duplicate_login_rejects_total" in source
    assert "rpg_runtime_transfer_lease_expiry_total" in source
    assert "rpg_runtime_startup_quarantine_total" in source
    assert "rpg_runtime_reconciliation_mismatches_total" in source
    assert "rpg_runtime_guild_value_drift_total" in source
    assert "rpg_runtime_replay_divergence_total" in source
    assert "ALERT duplicate_login_rejects" in source
    assert "ALERT transfer_lease_expiry" in source
    assert "ALERT startup_quarantine" in source

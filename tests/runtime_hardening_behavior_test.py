from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
METRICS = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ledger_payload_hash_generation_order_is_deterministic():
    source = _source(CORE)
    assert "String operationId = Long.toUnsignedString(operationNumericId);" in source
    assert "String payloadWithoutHash = ledgerPayload(new LedgerPayloadSnapshot(operationId, sequence, now, serverName, playerUuid, category, normalizedReference, goldDelta, copy, previousHash, hash, \"\"));" in source
    assert "String payloadHash = sha256(payloadWithoutHash);" in source


def test_high_value_ledger_mutations_are_flushed_immediately():
    source = _source(CORE)
    assert "requiresImmediateLedgerDurability(category) || ledgerQueue.size() >= immediateFlushThreshold" in source
    assert "flushLedger();" in source
    assert "ledger_immediate_flush_categories" in source


def test_runtime_exposes_conflict_and_transfer_and_dedupe_counters():
    source = _source(CORE)
    assert "transferBarrierRejects" in source
    assert "casConflictCount" in source
    assert "rewardDuplicateSuppressed" in source
    assert 'yaml.set("transfer_fence_rejects", transferBarrierRejectCount())' in source
    assert 'yaml.set("cas_conflicts", casConflictCount())' in source
    assert 'yaml.set("reward_duplicate_suppressed", rewardDuplicateSuppressionCount())' in source


def test_metrics_exports_new_runtime_failure_modes_and_alerts():
    source = _source(METRICS)
    assert "rpg_runtime_transfer_fence_rejects_total" in source
    assert "rpg_runtime_cas_conflicts_total" in source
    assert "rpg_runtime_reward_duplicate_suppressed_total" in source
    assert "ALERT transfer_fence_rejects" in source
    assert "ALERT cas_conflicts" in source

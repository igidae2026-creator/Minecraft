from helpers import ROOT, load_yaml


def _source() -> str:
    return (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")


def test_ledger_identity_is_globally_unique_snowflake_style():
    source = _source()

    assert "private final int ledgerServerId;" in source
    assert "private final AtomicInteger ledgerCounter = new AtomicInteger();" in source
    assert "private long nextLedgerOperationNumericId(long nowMillis)" in source
    assert "long serverPart = ((long) ledgerServerId & 0x3FFL) << 12;" in source
    assert "String operationId = Long.toUnsignedString(operationNumericId);" in source


def test_multi_server_ledger_collision_protection_present_in_schema():
    source = _source()

    assert "operation_id VARCHAR(64) PRIMARY KEY" in source
    assert "UNIQUE KEY uq_server_sequence (server, sequence_id)" in source


def test_duplicate_key_path_requires_exact_payload_hash_match():
    source = _source()

    assert "SELECT operation_id, server, sequence_id, payload_hash FROM rpg_ledger" in source
    assert "if (existingHash == null || !existingHash.equalsIgnoreCase(entry.payloadHash()))" in source
    assert "Ledger duplicate payload mismatch" in source


def test_pending_recovery_preserves_original_identity_and_hash_chain():
    source = _source()

    assert 'String entryServer = yaml.getString("server", "");' in source
    assert "Pending ledger operation id missing" in source
    assert "Pending ledger hash mismatch" in source
    assert "Pending ledger payload hash mismatch" in source
    assert "ledgerPayload(operationId, sequence, createdAt, entryServer" in source


def test_replay_reconstruction_and_flush_decoupling_controls_exist():
    source = _source()
    persistence = load_yaml("persistence.yml")

    assert "recovered.sort(Comparator.comparingLong(LedgerEntry::sequence));" in source
    assert persistence["write_policy"]["profile_save_interval_seconds"] == 60
    assert persistence["write_policy"]["ledger_flush_interval_seconds"] == 1
    assert persistence["write_policy"]["ledger_max_entries_per_flush"] == 4000
    assert 'ledger_immediate_flush_queue_threshold' in source


def test_required_value_moving_paths_are_ledgered():
    source = _source()

    assert 'appendLedgerMutation(profile.getUuid(), "dungeon_entry_cost"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "boss_summon_personal"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "boss_summon_guild"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "boss_summon_personal_refund"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "guild_bank_refund_failed_summon"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "admin_reward_grant"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "event_bonus_reward"' in source

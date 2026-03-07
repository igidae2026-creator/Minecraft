from helpers import ROOT, load_yaml


def test_ledger_identity_is_server_scoped_and_deterministic():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert 'UUID.nameUUIDFromBytes((serverName + "|" + sequence + "|" + hash)' in source
    assert 'UNIQUE KEY uq_server_sequence (server, sequence_id)' in source
    assert 'UNIQUE KEY uq_payload_identity (server, sequence_id, payload_hash)' in source


def test_duplicate_key_path_requires_payload_identity_match():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "SELECT operation_id, server, sequence_id, payload_hash FROM rpg_ledger" in source
    assert "Ledger duplicate payload mismatch" in source
    assert "Ledger duplicate identity collision" in source
    assert "Ledger duplicate unknown identity" in source


def test_pending_recovery_preserves_hash_semantics():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "Pending ledger hash mismatch" in source
    assert "Pending ledger payload hash mismatch" in source
    assert "ledgerPayload(operationId, sequence, createdAt, entryServer" in source


def test_value_moving_event_bonus_is_ledgered():
    event_source = (ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java").read_text(encoding="utf-8")

    assert 'appendLedgerMutation(profile.getUuid(), "event_bonus_reward"' in event_source


def test_ledger_durability_cadence_decoupled_and_observable():
    persistence = load_yaml("persistence.yml")
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert persistence["write_policy"]["profile_save_interval_seconds"] == 60
    assert persistence["write_policy"]["ledger_flush_interval_seconds"] == 1
    assert persistence["write_policy"]["ledger_max_entries_per_flush"] == 4000
    assert 'ledger_immediate_flush_queue_threshold' in source
    assert 'yaml.set("ledger_last_flush_at", ledgerLastFlushAt.get());' in source

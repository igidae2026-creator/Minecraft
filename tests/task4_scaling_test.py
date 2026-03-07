from helpers import ROOT


def test_task4_entity_counter_and_cleanup_paths_present():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "managedEntityIds" in source
    assert "for (UUID entityId : new ArrayList<>(managedEntityIds))" in source
    assert "markManagedEntityRemoved(entity);" in source
    assert "trimManagedEntityCounters(byCategory);" in source


def test_task4_atomic_write_and_event_state_persistence():
    core_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")
    event_source = (ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java").read_text(encoding="utf-8")

    assert "Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);" in core_source
    assert "Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING);" in core_source
    assert "public void writeAtomicFile(Path path, String contents)" in core_source
    assert "service.writeAtomicFile(path, yaml.saveToString());" in event_source


def test_task4_metrics_include_db_ledger_instance_entity_signals():
    metrics_source = (ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java").read_text(encoding="utf-8")
    core_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "rpg_runtime_ledger_queue_depth" in metrics_source
    assert "rpg_runtime_ledger_pending_files" in metrics_source
    assert "rpg_runtime_db_latency_ms_avg" in metrics_source
    assert "rpg_runtime_db_latency_ms_max" in metrics_source
    assert "rpg_runtime_active_instances" in metrics_source
    assert "rpg_runtime_managed_entities" in metrics_source

    assert "dbOperationCount" in core_source
    assert "recordDbLatency" in core_source
    assert "pendingLedgerFileCount" in core_source
    assert "managedEntityTotalCount" in core_source

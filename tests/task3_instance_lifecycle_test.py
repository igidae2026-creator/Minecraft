from helpers import ROOT


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"


def test_instance_orchestrator_lifecycle_states_and_core_methods_exist():
    source = CORE.read_text(encoding="utf-8")

    assert "class InstanceOrchestrator" in source
    for state in [
        "REQUESTED",
        "ALLOCATING",
        "BOOTING",
        "READY",
        "ACTIVE",
        "RESOLVING",
        "REWARD_COMMIT",
        "EGRESS",
        "CLEANUP",
        "TERMINATED",
    ]:
        assert state in source
    assert "allocateDungeonInstance" in source
    assert "allocateBossEncounter" in source
    assert "bootInstanceWorld" in source


def test_dungeon_and_boss_instances_are_isolated():
    source = CORE.read_text(encoding="utf-8")

    assert "createDungeonInstance(player.getUniqueId(), dungeonId, Set.of(player.getUniqueId()))" in source
    assert "instance.isPartyMember" in source
    assert "InstanceType.BOSS_ENCOUNTER" in source
    assert "spawnConfiguredBoss(spawnOrigin, bossId, player, dungeonIdForBoss, encounterInstanceId)" in source


def test_cleanup_daemon_and_instance_metrics_are_exported():
    source = CORE.read_text(encoding="utf-8")

    assert "cleanupOrphanWorlds" in source
    assert "orphanInstancesCleaned" in source
    assert "orphanInstanceCount()" in source
    assert "allocationLatencyMsAvg()" in source
    assert "allocationLatencyMsMax()" in source
    assert 'yaml.set("active_instances", activeInstanceCount())' in source
    assert 'yaml.set("orphan_instances", orphanInstanceCount())' in source
    assert 'yaml.set("instance_allocation_latency_ms_avg", allocationLatencyMsAvg())' in source

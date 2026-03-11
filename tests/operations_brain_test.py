from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
MAIN = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "Main.java"
EVENT_PLUGIN = ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java"
METRICS = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def test_runtime_monitor_config_is_present_and_thresholded():
    monitor = load_yaml("runtime_monitor.yml")

    assert monitor["health_thresholds"]["tps_warning"] > monitor["health_thresholds"]["tps_critical"]
    assert monitor["health_thresholds"]["player_density_limit"] >= monitor["scaling"]["density_scale_trigger"]
    assert monitor["queue"]["enabled"] is True
    assert monitor["exploit_detection"]["duplicate_reward_spike"] >= 1


def test_operations_brain_is_wired_into_runtime_and_admin_surface():
    source = CORE.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    event_source = EVENT_PLUGIN.read_text(encoding="utf-8")
    metrics_source = METRICS.read_text(encoding="utf-8")

    assert "runtimeMonitorConfig" in source
    assert "runOperationsBrain" in source
    assert "shouldQueueJoin" in source
    assert "enqueueJoin" in source
    assert "quarantineInstance" in source
    assert "operationsStatus" in source
    assert "forceEventStart" in source
    assert 'yaml.set("queue_size"' in source
    assert 'yaml.set("player_density"' in source
    assert 'yaml.set("instance_spawn"' in source

    assert 'args[0].equalsIgnoreCase("ops")' in main_source
    assert 'args[0].equalsIgnoreCase("forceevent")' in main_source
    assert 'args[0].equalsIgnoreCase("resetinstance")' in main_source

    assert "processForcedEventRequest" in event_source
    assert 'runtime_tps ' in metrics_source
    assert 'instance_spawn ' in metrics_source
    assert 'instance_shutdown ' in metrics_source
    assert 'exploit_flag ' in metrics_source
    assert 'queue_size ' in metrics_source
    assert 'player_density ' in metrics_source


def test_queue_and_quarantine_paths_are_behaviorally_guarded():
    source = CORE.read_text(encoding="utf-8")

    assert "player.kickPlayer(queueKickMessage(player))" in source
    assert 'player.sendMessage(color("&cInstance quarantined:' in source
    assert 'cleanupDungeonInstance(instance, "quarantine:' in source
    assert "detectRuntimeExploitAnomalies" in source

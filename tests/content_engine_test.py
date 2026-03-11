from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"
EVENT_PLUGIN = ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java"
METRICS_PLUGIN = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def test_content_engine_configs_are_runtime_complete():
    dungeon_templates = load_yaml("dungeon_templates.yml")
    boss_behaviors = load_yaml("boss_behaviors.yml")
    scheduler = load_yaml("event_scheduler.yml")
    reward_pools = load_yaml("reward_pools.yml")

    assert dungeon_templates["templates"]
    assert boss_behaviors["behaviors"]
    assert scheduler["events"]
    assert reward_pools["pools"]


def test_content_engine_is_wired_into_runtime_paths():
    content_source = (CORE / "ContentEngine.java").read_text(encoding="utf-8")
    service_source = (CORE / "RpgNetworkService.java").read_text(encoding="utf-8")
    event_source = EVENT_PLUGIN.read_text(encoding="utf-8")
    metrics_source = METRICS_PLUGIN.read_text(encoding="utf-8")

    assert "class ContentEngine" in content_source
    assert "DungeonTemplate" in content_source
    assert "BossBehavior" in content_source
    assert "RewardPool" in content_source

    assert "resolveDungeonTemplate" in service_source
    assert "composeRewardPool" in service_source
    assert "pollLobbyContentBroadcasts" in service_source
    assert 'yaml.set("content_engine"' in service_source
    assert 'yaml.set("dungeon_started"' in service_source
    assert 'yaml.set("reward_distributed"' in service_source

    assert "service.nextScheduledEvent" in event_source
    assert "service.recordEventStarted" in event_source
    assert 'args[0].equalsIgnoreCase("join")' in event_source

    assert "rpg_runtime_dungeon_started_total" in metrics_source
    assert "rpg_runtime_event_started_total" in metrics_source
    assert "rpg_runtime_reward_distributed_total" in metrics_source

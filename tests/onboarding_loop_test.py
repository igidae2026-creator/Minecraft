from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"


def _read(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_first_join_wiring_and_lobby_routes_exist():
    lobby = load_yaml("lobby.yml")
    core = _read("RpgNetworkService.java")
    main = _read("Main.java")

    assert "start_adventure" in lobby["routes"]
    assert "quick_match" in lobby["routes"]
    assert "rotating_event" in lobby["routes"]
    assert "explore_hub" in lobby["routes"]
    assert "maybeStartOnboarding(player);" in core
    assert "openLobbyRouter(player);" in core
    assert 'case "play"' in main


def test_returning_player_does_not_repeat_onboarding_and_reward_is_idempotent():
    profile = _read("RpgProfile.java")
    core = _read("RpgNetworkService.java")

    assert "onboardingCompletedAt" in profile
    assert "isOnboardingComplete()" in profile
    assert "shouldRunOnboarding" in core
    assert 'String rewardKey = "onboarding-reward:v1";' in core
    assert "profile.hasClaimedOperation(rewardKey)" in core


def test_branch_selection_reward_and_metrics_are_persisted():
    profile = _read("RpgProfile.java")
    core = _read("RpgNetworkService.java")
    metrics = (ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java").read_text(encoding="utf-8")

    for marker in ("onboarding.branch", "onboarding.destination", "onboarding.first_reward_at", "onboarding.first_interaction_at"):
        assert marker in profile
    for marker in ("appendLedgerMutation(profile.getUuid(), \"onboarding_reward\"", "first_branch_selected", "onboarding_started", "first_reward_granted", "first_interaction"):
        assert marker in core
    for marker in ("rpg_runtime_onboarding_started_total", "rpg_runtime_first_reward_granted_total", "rpg_runtime_time_to_first_reward_seconds_avg"):
        assert marker in metrics


def test_lobby_router_targets_adventure_quickplay_and_event_servers():
    lobby = load_yaml("lobby.yml")
    network = load_yaml("network.yml")
    core = _read("RpgNetworkService.java")

    assert lobby["routes"]["start_adventure"]["target_server"] == "rpg_world"
    assert lobby["routes"]["quick_match"]["target_server"] == "boss_world"
    assert lobby["routes"]["rotating_event"]["target_server"] == "events"
    assert set(network["servers"]).issuperset({"lobby", "rpg_world", "boss_world", "events"})
    assert 'case "lobby" -> Set.of("progression", "boss", "event").contains(targetRole.toLowerCase(Locale.ROOT));' in core

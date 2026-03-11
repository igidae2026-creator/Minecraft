from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"
MAIN = CORE / "Main.java"
SERVICE = CORE / "RpgNetworkService.java"
ENGINE = CORE / "TelemetryAdaptiveEngine.java"
METRICS = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def test_adaptive_rules_config_is_runtime_complete():
    rules = load_yaml("adaptive_rules.yml")

    for section in ("telemetry", "difficulty", "rewards", "events", "matchmaking", "churn", "safety"):
        assert section in rules

    assert rules["difficulty"]["min_multiplier"] < rules["difficulty"]["max_multiplier"]
    assert rules["rewards"]["min_multiplier"] < rules["rewards"]["max_multiplier"]
    assert rules["events"]["min_frequency_multiplier"] < rules["events"]["max_frequency_multiplier"]
    assert rules["matchmaking"]["min_range_multiplier"] < rules["matchmaking"]["max_range_multiplier"]


def test_adaptive_engine_tracks_behavioral_signals_and_bounds():
    source = ENGINE.read_text(encoding="utf-8")

    for marker in (
        "DUNGEON_COMPLETION_TIME",
        "PLAYER_DEATH_RATE",
        "EVENT_JOIN_RATE",
        "PLAYER_SESSION_LENGTH",
        "QUEUE_TIME",
        "PLAYER_CHURN_SIGNAL",
        "AdaptiveState",
        "recompute",
        "difficultyDelta",
        "rewardDelta",
        "eventDelta",
        "matchmakingDelta",
        "clamp",
    ):
        assert marker in source


def test_runtime_wires_ingestion_feedback_and_exports():
    source = SERVICE.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")

    assert "recomputeAdaptiveGameplay(snapshot)" in source
    assert "ingestTelemetry(TelemetryAdaptiveEngine.SignalType.EVENT_JOIN_RATE" in source
    assert "ingestTelemetry(TelemetryAdaptiveEngine.SignalType.QUEUE_TIME" in source
    assert "ingestTelemetry(TelemetryAdaptiveEngine.SignalType.PLAYER_SESSION_LENGTH" in source
    assert "ingestTelemetry(TelemetryAdaptiveEngine.SignalType.PLAYER_DEATH_RATE" in source
    assert "ingestTelemetry(TelemetryAdaptiveEngine.SignalType.DUNGEON_COMPLETION_TIME" in source
    assert "adaptiveDifficultyMultiplier" in source
    assert "adaptiveRewardWeightMultiplier" in source
    assert "adaptiveEventFrequencyMultiplier" in source
    assert "adaptiveMatchmakingRangeMultiplier" in source
    assert 'yaml.set("adaptive_adjustment"' in source
    assert 'yaml.set("adaptive_engine"' in source
    assert "contentRotationTickSeconds" in source
    assert "handlePlayerDeath" in source
    assert "PlayerDeathEvent" in main_source


def test_metrics_export_adaptive_adjustments():
    source = METRICS.read_text(encoding="utf-8")

    for marker in (
        "adaptive_adjustment ",
        "difficulty_change ",
        "reward_adjustment ",
        "event_frequency_change ",
        "matchmaking_adjustment ",
        "rpg_runtime_adaptive_adjustment_total",
        "rpg_runtime_difficulty_change_total",
        "rpg_runtime_reward_adjustment_total",
        "rpg_runtime_event_frequency_change_total",
        "rpg_runtime_matchmaking_adjustment_total",
    ):
        assert marker in source

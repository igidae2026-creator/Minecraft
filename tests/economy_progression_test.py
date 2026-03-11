from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
PROFILE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgProfile.java"
ECONOMY_PLUGIN = ROOT / "plugins" / "economy_engine" / "src" / "main" / "java" / "com" / "rpg" / "economy" / "Main.java"
METRICS_PLUGIN = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def test_economy_model_and_gear_tiers_are_configured():
    economy = load_yaml("economy.yml")
    gear_tiers = load_yaml("gear_tiers.yml")

    assert economy["economy_model"]["global_currency"]["id"] == "credits"
    assert economy["economy_model"]["progression_currency"]["id"] == "mastery_points"
    for genre_id in ("rpg", "minigame", "event"):
        assert genre_id in economy["economy_model"]["genre_currency"]
    assert economy["economy_model"]["sinks_runtime"]["cosmetics"]
    assert economy["economy_model"]["sinks_runtime"]["temporary_buffs"]
    assert gear_tiers["tiers"]
    assert gear_tiers["genre_reward_mapping"]["minigame"]["max_drop_tier"] == "tier2"


def test_progression_and_sink_paths_are_wired_into_runtime():
    source = CORE.read_text(encoding="utf-8")
    profile_source = PROFILE.read_text(encoding="utf-8")
    economy_source = ECONOMY_PLUGIN.read_text(encoding="utf-8")
    metrics_source = METRICS_PLUGIN.read_text(encoding="utf-8")

    assert "progressionSummary" in source
    assert "awardProgressionTrack" in source
    assert "craftGear" in source
    assert "repairGear" in source
    assert "unlockCosmetic" in source
    assert "buyTemporaryBuff" in source
    assert "normalizedTier" in source
    assert "isTradeRestrictedMaterial" in source
    assert "economyEarnCount" in source
    assert "progressionLevelUpCount" in source

    assert "masteryExperience" in profile_source
    assert "activityExperience" in profile_source
    assert "ownedCosmetics" in profile_source
    assert "activeBuffs" in profile_source
    assert "gearCondition" in profile_source

    assert 'case "progression"' in economy_source
    assert 'case "rpgcraft"' in economy_source
    assert 'case "rpgrepair"' in economy_source
    assert 'case "rpgcosmetic"' in economy_source
    assert 'case "rpgbuff"' in economy_source

    assert "rpg_runtime_economy_earn_total" in metrics_source
    assert "rpg_runtime_economy_spend_total" in metrics_source
    assert "rpg_runtime_gear_upgrade_total" in metrics_source
    assert "rpg_runtime_progression_level_up_total" in metrics_source


def test_reward_duplication_and_trade_safety_still_flow_through_ledger():
    source = CORE.read_text(encoding="utf-8")

    assert 'appendLedgerMutation(profile.getUuid(), "event_bonus_reward"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "gear_upgrade"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "crafting"' in source
    assert 'appendLedgerMutation(profile.getUuid(), "gear_repair"' in source
    assert 'profile.hasClaimedOperation(opKey)' in source

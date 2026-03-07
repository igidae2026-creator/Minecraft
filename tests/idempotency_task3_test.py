from pathlib import Path

from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java"
PROFILE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgProfile.java"
EVENT_PLUGIN = ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java"


def test_duplicate_event_reward_suppression_is_durable():
    source = CORE.read_text(encoding="utf-8")
    event_source = EVENT_PLUGIN.read_text(encoding="utf-8")

    assert "grantEventBonusReward" in source
    assert "event-bonus:" in source
    assert "profile.hasClaimedOperation(opKey)" in source
    assert "appendLedgerMutation(profile.getUuid(), \"event_bonus_reward\"" in source
    assert "service.grantEventBonusReward" in event_source


def test_duplicate_dungeon_completion_suppression_is_durable():
    source = CORE.read_text(encoding="utf-8")

    assert "dungeon-complete:" in source
    assert "profile.hasClaimedOperation(completionClaimKey)" in source
    assert "profile.markClaimedOperation(completionClaimKey)" in source
    assert "profile.clearClaimedOperation(completionClaimKey)" in source


def test_failed_summon_refund_integrity_has_auditable_operation_key():
    source = CORE.read_text(encoding="utf-8")

    assert "buildSummonOperationKey" in source
    assert "boss_summon_personal_refund" in source
    assert "guild_bank_refund_failed_summon" in source
    assert "refundReference" in source
    assert "refund commit delayed" in source


def test_time_bound_reward_boundary_is_configured_zone_not_host_default():
    source = CORE.read_text(encoding="utf-8")
    network = load_yaml("network.yml")

    assert "rewardBoundaryZone" in source
    assert "LocalDate.ofInstant" in source
    assert "ZoneOffset.UTC" in source
    assert network["operational"]["reward_boundary_timezone"] == "UTC"


def test_profile_persists_claimed_operations_for_restart_dedupe():
    source = PROFILE.read_text(encoding="utf-8")

    assert "claimedOperations" in source
    assert 'yaml.set("claims", new LinkedHashMap<>(claimedOperations));' in source
    assert 'loadLongMap(yaml.getConfigurationSection("claims"), profile.claimedOperations);' in source

from helpers import ROOT


def test_final_targeted_production_patch_markers_present():
    build_gradle = (ROOT / "build.gradle").read_text(encoding="utf-8")
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")
    event_source = (ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java").read_text(encoding="utf-8")

    assert "mysql-connector-j" in build_gradle
    assert "mysqlDriverAvailable" in source
    assert "persistProfileAuthoritatively" in source
    assert "canAccessWorld" in source
    assert "canClaimReservedEntityKill" in source
    assert "isTravelAllowed" in source
    assert "This event mob is reserved for another player." in event_source

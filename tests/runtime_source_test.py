from pathlib import Path

from helpers import ROOT


def test_core_runtime_contains_persistence_and_gameplay_wiring():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS rpg_profiles" in source
    assert "SETEX" in source
    assert "spawnConfiguredBoss" in source
    assert "startDungeon" in source
    assert "upgradeGear" in source
    assert "writeSession" in source

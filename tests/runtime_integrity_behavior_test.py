from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from helpers import ROOT


def test_runtime_integrity_detects_duplicate_item_instance(tmp_path: Path):
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)

    owners = runtime_data / "item_authority" / "owners"
    owners.mkdir(parents=True, exist_ok=True)
    (owners / "owner_a.yml").write_text("owner_ref: player:a\nitems:\n  itm_dup: guardian_core\n", encoding="utf-8")
    (owners / "owner_b.yml").write_text("owner_ref: player:b\nitems:\n  itm_dup: guardian_core\n", encoding="utf-8")

    result = subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_integrity.py")], cwd=ROOT, capture_output=True, text=True)

    shutil.rmtree(runtime_data)
    shutil.copytree(backup, runtime_data, dirs_exist_ok=True)

    assert result.returncode == 1
    assert "duplicate_item_instance:itm_dup:player:a:player:b" in result.stdout


def test_event_runtime_no_longer_applies_duplicate_bonus_mutation():
    event_source = (ROOT / "plugins" / "event_scheduler" / "src" / "main" / "java" / "com" / "rpg" / "event" / "Main.java").read_text(encoding="utf-8")
    assert "service.grantEventBonusReward" in event_source
    assert 'service.appendLedgerMutation(profile.getUuid(), "event_bonus_reward"' not in event_source


def test_instance_boot_uses_world_allocator_not_recursive_call():
    core_source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")
    assert "World world = ensureDungeonWorld(instance);" in core_source
    assert "World world = instanceOrchestrator.bootInstanceWorld(instance);" not in core_source

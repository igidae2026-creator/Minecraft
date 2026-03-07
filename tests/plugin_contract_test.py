from pathlib import Path

import yaml

from helpers import ROOT

PLUGIN_COMMANDS = {
    "rpg_core": {"rpgprofile", "rpgtravel", "rpgadmin"},
    "economy_engine": {"wallet", "rpgvendor", "rpgupgrade"},
    "quest_system": {"quest"},
    "boss_ai": {"boss"},
    "dungeon_system": {"dungeon"},
    "guild_system": {"guild"},
    "skill_system": {"skill"},
    "event_scheduler": {"rpgevent"},
    "metrics_monitor": {"rpgmetrics"},
}


def test_plugins_expose_runtime_commands():
    for plugin_name, required_commands in PLUGIN_COMMANDS.items():
        plugin_yml = ROOT / "plugins" / plugin_name / "plugin.yml"
        with plugin_yml.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        assert payload["version"] == "1.2.0"
        assert required_commands <= set((payload.get("commands") or {}).keys())

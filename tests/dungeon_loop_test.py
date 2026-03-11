from helpers import load_yaml

def test_dungeon_entry_is_gate_not_bypass():
    dungeons = load_yaml("dungeons.yml")
    dungeon_templates = load_yaml("dungeon_templates.yml")
    economy = load_yaml("economy.yml")

    goblin_cave = dungeons["goblin_cave"]
    assert goblin_cave["recommended_level"] >= 5
    assert goblin_cave["entry_requirements"]["cave_map_scrap"] >= 5
    assert goblin_cave["entry_fee_gold"] == economy["sinks"]["dungeon_entry"]["goblin_cave"]
    assert goblin_cave["active_template"] in dungeon_templates["templates"]
    assert set(goblin_cave["template_pool"]).issubset(dungeon_templates["templates"])

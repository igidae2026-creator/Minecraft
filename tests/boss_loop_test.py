from helpers import load_yaml

def test_boss_chain_requires_progression_materials():
    bosses = load_yaml("bosses.yml")
    dungeons = load_yaml("dungeons.yml")

    goblin_cave = dungeons["goblin_cave"]
    forest_guardian = bosses["forest_guardian"]

    assert goblin_cave["boss"] == "goblin_king"
    assert goblin_cave["progression_gate"]["next_boss"] == "forest_guardian"
    assert forest_guardian["summon"]["required_items"]["guardian_seed"] == 1
    assert forest_guardian["summon"]["required_items"]["dungeon_shard"] >= 25

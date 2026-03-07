from helpers import load_yaml

def test_progression_loop_is_closed():
    mobs = load_yaml("mobs.yml")
    dungeons = load_yaml("dungeons.yml")
    bosses = load_yaml("bosses.yml")
    items = load_yaml("items.yml")

    mob_drops = set()
    for mob_data in mobs.values():
        mob_drops.update(mob_data["drops"].keys())

    dungeon_requirements = set()
    dungeon_rewards = set()
    for dungeon_data in dungeons.values():
        dungeon_requirements.update(dungeon_data.get("entry_requirements", {}).keys())
        dungeon_rewards.update(dungeon_data.get("completion_rewards", {}).keys())

    boss_summons = set()
    boss_drops = set()
    for boss_data in bosses.values():
        boss_summons.update(boss_data["summon"]["required_items"].keys())
        boss_drops.update(boss_data["drops"]["guaranteed"].keys())

    upgrade_materials = set()
    for tier_data in items["tiers"].values():
        upgrade_materials.update(tier_data.get("required_materials", {}).keys())
    for craft_data in items["crafting"].values():
        upgrade_materials.update(craft_data.get("required_materials", {}).keys())

    assert "cave_map_scrap" in mob_drops
    assert dungeon_requirements <= mob_drops | set(items["materials"].keys())
    assert boss_summons & (dungeon_rewards | mob_drops | boss_drops)
    assert boss_drops & upgrade_materials

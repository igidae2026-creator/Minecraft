from helpers import load_yaml

def test_economy_has_sinks_and_no_free_progression_bypass():
    economy = load_yaml("economy.yml")
    items = load_yaml("items.yml")

    faucets = sum(economy["faucets"]["quests"].values()) + sum(economy["faucets"]["mobs"].values()) + sum(economy["faucets"]["dungeons"].values()) + sum(economy["faucets"]["bosses"].values())
    sinks = economy["sinks"]["dungeon_entry"]["goblin_cave"] + economy["sinks"]["boss_summon"]["goblin_king"] + economy["sinks"]["boss_summon"]["forest_guardian"] + sum(economy["sinks"]["crafting_upgrade"].values()) + economy["sinks"]["travel"]["local_transfer_fee"]

    assert economy["market_tax"] > 0
    assert economy["starting_balance"] < economy["sinks"]["crafting_upgrade"]["rare_to_epic"]
    assert sinks > faucets / 2
    assert items["tiers"]["legendary"]["tradable"] is False

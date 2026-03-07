from helpers import load_yaml

def test_guild_layer_has_persistence_backing():
    network = load_yaml("network.yml")
    persistence = load_yaml("persistence.yml")

    assert network["data_flow"]["guild_state"] == "mysql"
    assert persistence["mysql"]["enabled"] is True

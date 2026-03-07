from helpers import load_yaml

def test_scaling_caps_are_conservative():
    network = load_yaml("network.yml")
    scaling = load_yaml("scaling.yml")

    ports = set()
    for server_name, server_data in network["servers"].items():
        role = server_data["role"]
        host, port = server_data["address"].split(":")
        assert host == "127.0.0.1"
        assert port not in ports
        ports.add(port)
        assert server_data["view_distance"] <= scaling["limits"]["max_view_distance_by_role"][role]
        assert server_data["simulation_distance"] <= scaling["limits"]["max_simulation_distance_by_role"][role]
        assert server_data["simulation_distance"] <= server_data["view_distance"]

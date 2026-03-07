from pathlib import Path

import yaml

from helpers import load_yaml, ROOT

def test_rendered_network_files_match_security_baseline():
    network = load_yaml("network.yml")
    exploit = load_yaml("exploit_guards.yml")

    velocity_toml = (ROOT / "proxy" / "velocity.toml").read_text(encoding="utf-8")
    assert 'player-info-forwarding-mode = "MODERN"' in velocity_toml
    assert 'prevent-client-proxy-connections = true' in velocity_toml
    assert exploit["network"]["direct_backend_join_block"] is True

    for server_name in network["servers"]:
        server_props = (ROOT / server_name / "server.properties").read_text(encoding="utf-8")
        assert "server-ip=127.0.0.1" in server_props
        assert "online-mode=false" in server_props

        with (ROOT / server_name / "config" / "paper-global.yml").open("r", encoding="utf-8") as handle:
            paper_global = yaml.safe_load(handle)
        assert paper_global["proxies"]["velocity"]["enabled"] is True
        assert paper_global["proxies"]["velocity"]["online-mode"] is True
        assert paper_global["proxies"]["velocity"]["secret"]

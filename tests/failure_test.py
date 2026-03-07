from helpers import load_yaml

def test_failure_policy_is_fail_safe():
    network = load_yaml("network.yml")
    persistence = load_yaml("persistence.yml")

    assert network["operational"]["proxy_failover_server"] == "lobby"
    assert persistence["recovery"]["read_only_mode_on_db_failure"] is True
    assert persistence["recovery"]["inventory_backup_slots"] >= 1
    assert persistence["recovery"]["fail_closed_on_economy_ledger_loss"] is True

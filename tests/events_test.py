from helpers import load_yaml


def test_events_are_connected_to_live_loop():
    events = load_yaml("events.yml")
    mobs = load_yaml("mobs.yml")
    items = load_yaml("items.yml")

    assert events["events"]
    for event_id, event_data in events["events"].items():
        assert event_data["mob"] in mobs
        assert event_data["bonus_item"] in items["materials"]
        assert event_data["bonus_gold"] > 0
        assert event_data["spawn_count"] >= 1

from pathlib import Path

from helpers import ROOT, load_yaml


def test_persistence_has_runtime_fallback_and_session_mirroring():
    persistence = load_yaml("persistence.yml")

    assert persistence["mysql"]["enabled"] is True
    assert persistence["redis"]["enabled"] is True
    assert persistence["local_fallback"]["enabled"] is True
    assert persistence["local_fallback"]["path"] == "runtime_data"
    assert persistence["redis"]["mirror_live_sessions"] is True

    assert (ROOT / "runtime_data").exists()
    assert (ROOT / "metrics").exists()

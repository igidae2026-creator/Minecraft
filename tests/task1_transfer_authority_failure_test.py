from helpers import ROOT


def test_mysql_latency_and_conflict_and_stale_load_guards_present():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    # MySQL latency instrumentation is required for latency-failure simulation paths.
    assert "dbLatencyTotalNanos" in source
    assert "dbLatencyMaxNanos" in source

    # stale load prevention on target activation
    assert "readProfileDurableVersion" in source
    assert "Travel version barrier profile mismatch" in source

    # write conflicts must be explicit CAS failures
    assert "CAS profile write rejected" in source
    assert "CAS guild write rejected" in source
    assert "PersistOutcome.CONFLICT" in source

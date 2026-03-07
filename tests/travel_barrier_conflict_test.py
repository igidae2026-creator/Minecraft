from helpers import ROOT


def test_transfer_barrier_and_authority_fencing_markers_present():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "transfer_id" in source
    assert "issued_at" in source
    assert "consumeTravelTicket(UUID uuid, String expectedTarget, LiveSession previousSession)" in source
    assert "travel_fence_reject" in source
    assert "Travel barrier transfer id missing" in source


def test_profile_and_guild_writes_use_cas_not_replace_into():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "REPLACE INTO rpg_profiles" not in source
    assert "REPLACE INTO rpg_guilds" not in source
    assert "WHERE uuid = ? AND updated_at = ?" in source
    assert "WHERE name = ? AND updated_at = ?" in source
    assert "expectedStoredVersion" in source
    assert "PersistOutcome.CONFLICT" in source
    assert "profile_conflict" in source
    assert "guild_conflict" in source


def test_fault_injection_paths_for_delayed_flush_and_stale_load_markers_present():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "Travel version barrier profile mismatch" in source
    assert "Travel version barrier guild mismatch" in source
    assert "Travel blocked until profile persistence catches up." in source
    assert "Unable to authorize the server switch." in source


def test_transfer_lease_version_claim_and_profile_freeze_markers_present():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "transfer_lease" in source
    assert "version_claim" in source
    assert "freezeMutationAuthority" in source
    assert "unfreezeMutationAuthority" in source
    assert "Travel version claim mismatch" in source


def test_durable_barrier_reads_guard_against_stale_target_loads():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "readProfileDurableVersion" in source
    assert "readGuildDurableVersion" in source
    assert "SELECT updated_at FROM rpg_profiles" in source
    assert "SELECT updated_at FROM rpg_guilds" in source


def test_transfer_ticket_lifecycle_states_are_explicit_and_fail_closed():
    source = (ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core" / "RpgNetworkService.java").read_text(encoding="utf-8")

    assert "enum TransferTicketState" in source
    assert "PENDING" in source
    assert "ACTIVATED" in source
    assert "CONSUMED" in source
    assert "FAILED" in source
    assert "EXPIRED" in source
    assert "persistTravelTicket(uuid, failTravelTicket(ticket, \"invalid_lease\"))" in source

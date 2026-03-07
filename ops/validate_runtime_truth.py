#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"
CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    network = load(CONFIG / "network.yml")
    persistence = load(CONFIG / "persistence.yml")
    service_source = (CORE / "RpgNetworkService.java").read_text(encoding="utf-8")
    session_source = (CORE / "SessionAuthorityService.java").read_text(encoding="utf-8")
    transfer_source = (CORE / "DeterministicTransferService.java").read_text(encoding="utf-8")
    artifact_source = (CORE / "GameplayArtifactRegistry.java").read_text(encoding="utf-8")
    governance_source = (CORE / "GovernancePolicyRegistry.java").read_text(encoding="utf-8")

    errors: list[str] = []

    if network["data_flow"]["live_session_state"] != "local_authoritative_lease_registry":
        errors.append("session_authority_claim_mismatch")
    if persistence["redis"]["required_for_session_authority"] is not False:
        errors.append("redis_authority_fiction_present")

    combined = "\n".join((session_source, transfer_source, artifact_source, governance_source))
    for marker in (
        "REGISTERED", "LEASED", "RECONNECT_HELD", "TRANSFERRING", "ACTIVE", "INVALIDATED", "EXPIRED",
        "INITIATED", "PERSISTING", "ACTIVATING", "FAILED",
        "LOOT_TABLE_VARIANT", "EXPLOIT_SIGNATURE", "RECOVERY_ACTION",
        "spawn_regulation", "reward_idempotency", "experiment_admission",
    ):
        if marker not in combined:
            errors.append(f"missing_marker:{marker}")

    for marker in ("session_authority_service", "deterministic_transfer_service", "gameplay_artifact_registry", "governance_policy_registry"):
        if marker not in service_source:
            errors.append(f"status_export_missing:{marker}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("RUNTIME_TRUTH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

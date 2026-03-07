# Minecraft MMORPG Runtime Runbook

This repository runs authoritative gameplay state through MySQL-backed profiles, guilds, and ledger state, with in-repo lease coordination under `runtime_data/coordination`. Redis is an optional session mirror, not the source of truth.

Startup validation:
- `python3 ops/render_network.py`
- `python3 ops/validate_rpg.py`
- `python3 ops/validate_runtime_truth.py`
- `python3 ops/runtime_integrity.py`
- `python3 ops/reconcile_runtime.py`

Cluster operations:
- `bash ops/orchestrate_cluster.sh start`
- `bash ops/orchestrate_cluster.sh validate`
- `bash ops/orchestrate_cluster.sh status`
- `bash ops/orchestrate_cluster.sh stop`

Recovery:
- `bash ops/recover_runtime.sh`
- Keep the runtime fail-closed if any `runtime_data/status/*.yml` file reports `reconciliation_mismatches`, `guild_value_drift`, `replay_divergence`, `item_ownership_conflicts`, or transfer ambiguity signals.

Guaranteed by this repo:
- Append-only ledger truth for value mutations.
- Deterministic transfer state export with stale-load refusal and refund markers.
- File-backed session authority and reconnect hold surfaces.
- Item ownership manifest reconciliation and quarantine detection.
- Artifact, policy, experiment, and incident export surfaces under `runtime_data`.

Not guaranteed without external infrastructure:
- Multi-host consensus beyond the in-repo coordination substrate.
- Cross-host fencing stronger than the authoritative node executing this runtime.
- Managed Prometheus or Alertmanager retention and external paging.

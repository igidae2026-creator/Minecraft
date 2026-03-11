# Minecraft MMORPG Runtime Runbook

This repository runs authoritative gameplay state through MySQL-backed profiles, guilds, and ledger state, with in-repo lease coordination under `runtime_data/coordination`. Redis is an optional session mirror, not the source of truth. Pressure, experiment, governance, artifact, incident, and knowledge surfaces are exported under `runtime_data` and are expected to match the runtime classes in `plugins/rpg_core`.

Autonomy target:
- The operating goal is 24-hour unattended, high-quality automation where human intervention yields little or no meaningful quality gain.
- Repository-internal closed loops are necessary but insufficient; the outer automation layer must also classify newly arriving material, decide whether it belongs in scope, and automatically reject, sandbox, defer, or promote it.
- If routine scope selection or promotion still requires a person, the autonomy target has not been met.

Autonomy core:
- Core runtime automation is organized around four durable substrates: append-only event log, typed snapshots, file-backed job queue, and resident supervisor.
- Policy sits above that core and decides which jobs to enqueue, when to simulate, when to sweep matrix scenarios, and later which external inputs to reject, defer, sandbox, or promote.
- Core autonomy state lives under `runtime_data/autonomy/core`.

Startup validation:
- `python3 ops/render_network.py`
- `python3 ops/validate_rpg.py`
- `python3 ops/validate_runtime_truth.py`
- `python3 ops/runtime_integrity.py`
- `python3 ops/runtime_summary.py`
- `python3 ops/reconcile_runtime.py`
- `python3 ops/autonomous_quality_loop.py --dry-run`

Cluster operations:
- `bash ops/orchestrate_cluster.sh start`
- `bash ops/orchestrate_cluster.sh validate`
- `bash ops/orchestrate_cluster.sh status`
- `bash ops/orchestrate_cluster.sh autotune`
- `bash ops/orchestrate_cluster.sh daemon-start` to keep the outer autonomy loop running without chat-driven retriggers
- `bash ops/orchestrate_cluster.sh daemon-status` to inspect the last autonomous pass heartbeat
- `bash ops/orchestrate_cluster.sh daemon-stop` to halt the background autonomy supervisor
- `bash ops/orchestrate_cluster.sh stop`
- `bash ops/prewarm_paper_worlds.sh` to complete first-run Paper downloads/remapping before background cluster boot
- `bash ops/run_closed_loop_cycle.sh 3` to inject synthetic telemetry, force one bounded autonomy pass, and print the updated runtime summary
- `bash ops/run_closed_loop_matrix.sh` to sweep overloaded/completion/engagement/healthy scenarios and verify the loop chooses different bounded reactions

Recovery:
- `bash ops/recover_runtime.sh`
- Keep the runtime fail-closed if any `runtime_data/status/*.yml` file reports `reconciliation_mismatches`, `guild_value_drift`, `replay_divergence`, `item_ownership_conflicts`, or transfer ambiguity signals.
- Use `python3 ops/runtime_summary.py` for the operator rollup of session authority, transfer failures/quarantines, reconciliation mismatches, guild drift, item quarantine, exploit incidents, instance leaks, experiment anomalies, and knowledge records.
- Treat `runtime_data/knowledge/*.yml` as the balancing and exploit memory surface; future tuning and rollback decisions should consult it before changing pressure, economy, or experiment policy.
- Run `bash ops/close_quality_loop.sh` to validate, tune bounded config surfaces, append an autonomy decision artifact, and re-read runtime summary in one pass.
- The unattended supervisor writes its PID, heartbeat, state, and append-only logs under `runtime_data/autonomy/supervisor`.
- Autonomy decisions are append-only under `runtime_data/autonomy/decisions`, with pre-mutation backups under `runtime_data/autonomy/backups`.
- Active soak state and append-only control lineage live under `runtime_data/autonomy/control`; promote/reject decisions should be understood as lineage transitions, not ephemeral tuning attempts.
- While a soak is active, the policy layer prioritizes fresh observation and bounded autonomy evaluation over matrix sweeps so that promotion or deterministic revert happens before new exploration branches are opened.
- MetaOS skeleton governance surfaces live under `docs/governance`, and automatic repo mapping / conflict tracking are exported under `runtime_data/audit`.
- `python3 ops/metaos_conformance.py` refreshes coverage and conflict traces for L0/L1/L4/A1/A2 style checks.

Guaranteed by this repo:
- Append-only ledger truth for value mutations.
- Deterministic transfer state export with stale-load refusal and refund markers.
- Explicit transfer quarantine and rollback markers for ambiguous authority outcomes.
- File-backed session authority and reconnect hold surfaces.
- Item ownership manifest reconciliation and quarantine detection.
- Artifact, policy, experiment, incident, pressure, and knowledge export surfaces under `runtime_data`.

Not guaranteed without external infrastructure:
- Multi-host consensus beyond the in-repo coordination substrate.
- Cross-host fencing stronger than the authoritative node executing this runtime.
- Managed Prometheus or Alertmanager retention and external paging.

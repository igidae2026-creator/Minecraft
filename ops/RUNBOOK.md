# Minecraft MMORPG Runtime Runbook

This repository runs authoritative gameplay state through MySQL-backed profiles, guilds, and ledger state, with in-repo lease coordination under `runtime_data/coordination`. Redis is an optional session mirror, not the source of truth. Pressure, experiment, governance, artifact, incident, and knowledge surfaces are exported under `runtime_data` and are expected to match the runtime classes in `plugins/rpg_core`.

This file is the top-level operating index.
Detailed command and recovery material now lives in:

- [OPS_COMMANDS.md](/home/meta_os/Minecraft/ops/OPS_COMMANDS.md)
- [AUTONOMY_SURFACES.md](/home/meta_os/Minecraft/ops/AUTONOMY_SURFACES.md)
- [RECOVERY_PLAYBOOK.md](/home/meta_os/Minecraft/ops/RECOVERY_PLAYBOOK.md)

Parallel command surface:
- `python3 ops/parallel_workstream_governor.py`
- `bash ops/parallel_command_center.sh plan`
- `bash ops/parallel_command_center.sh status`
- `bash ops/parallel_command_center.sh launch`
- `bash ops/parallel_command_center.sh stop`
- Workstream packets are emitted under `runtime_data/autonomy/parallel/packets`.
- Parallel expansion is constrained to the active Minecraft target boundary only; out-of-scope expansion must be deferred or rejected, not executed.

Autonomy target:
- The operating goal is 24-hour unattended, high-quality automation where human intervention yields little or no meaningful quality gain.
- Repository-internal closed loops are necessary but insufficient; the outer automation layer must also classify newly arriving material, decide whether it belongs in scope, and automatically reject, sandbox, defer, or promote it.
- If routine scope selection or promotion still requires a person, the autonomy target has not been met.

Autonomy core:
- Core runtime automation is organized around four durable substrates: append-only event log, typed snapshots, file-backed job queue, and resident supervisor.
- Policy sits above that core and decides which jobs to enqueue, when to simulate, when to sweep matrix scenarios, and later which external inputs to reject, defer, sandbox, or promote.
- Core autonomy state lives under `runtime_data/autonomy/core`.

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

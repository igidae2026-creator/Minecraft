# RPG Network Release Manifest

- Hard authority coordination plane added with lease-based session ownership, split-brain detection, duplicate-login rejection counters, and transfer-fence ticket lifecycle states.
- Economy/item authority plane added with append-only hash-verifiable mutation model, duplicate payload mismatch fail-closed behavior, and item quarantine accounting.
- Instance/experiment control plane added with explicit runtime instance classes (dungeon/boss/event/exploration), deterministic lifecycle state taxonomy, orphan recovery, cleanup sweeps, and policy/experiment registries.
- Exploit forensics plane added with immutable incident records and explicit response classes (flag, restrictions, quarantine, reward delay, admin review).
- `rpg_core` health snapshots now export control-plane telemetry (`authority_plane`, `economy_item_authority_plane`, `instance_experiment_control_plane`, `exploit_forensics_plane`).
- Metrics monitor expanded with split-brain, item-quarantine, exploit incident, and authority-conflict Prometheus counters plus alert paths.
- Runtime truth alignment updated: `network.yml` now marks live sessions as `redis_authoritative`, and scaling config removed false promise of world reuse pooling.
- Added focused config/runtime alignment test covering new control planes and observability wiring.
- Authority coordination now tracks pending/consumed/failed/expired ticket counts and performs deterministic expiry sweeps during runtime cleanup cycles.
- Session authority is now explicitly fenced around Redis-backed session/ticket coordination, duplicate-login fail-close behavior, transfer lease expiry accounting, and authority conflict telemetry.
- Transfer activation now depends on durable source versions, explicit ticket lifecycle states, mutation freeze, and fail-closed rollback/refund handling.
- Ledger truth now remains append-only and payload-verifiable, with repaired pending-entry recovery, startup preload/reconciliation, and fail-closed divergence/quarantine behavior.
- High-value item authority now has first-class owner manifests plus item-lineage mint/transfer/consume tracking tied to exploit forensics and quarantine counters.
- Instance runtime now fixes recursive world boot failure, exports cleanup latency/failure telemetry, and preserves explicit deterministic lifecycle states through cleanup.
- Gameplay artifacts are now exported to `runtime_data/artifacts`, active governance state is exported to `runtime_data/policies`, and runtime integrity tooling validates these surfaces.
- Metrics and alerts now cover guild drift, replay divergence, item ownership conflicts, cleanup failures, and experiment/policy rollback anomalies in addition to prior authority and ledger signals.
- Ops now include `runtime_integrity.py`, stronger health validation, and repo-truth config updates for artifact exports, rare-item authority, and session authority requirements.

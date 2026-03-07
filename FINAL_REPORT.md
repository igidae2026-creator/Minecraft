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

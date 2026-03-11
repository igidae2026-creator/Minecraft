# Recovery Playbook

## Fail-Closed Conditions

Keep the runtime fail-closed if any `runtime_data/status/*.yml` reports:

- `reconciliation_mismatches`
- `guild_value_drift`
- `replay_divergence`
- `item_ownership_conflicts`
- transfer ambiguity signals

## Primary Recovery Reads

- `python3 ops/runtime_summary.py`
- `runtime_data/knowledge/*.yml`
- `runtime_data/autonomy/final_threshold_eval.json`
- `runtime_data/autonomy/control/state.yml`

## Primary Recovery Actions

- `bash ops/recover_runtime.sh`
- `bash ops/close_quality_loop.sh`
- `python3 ops/reconcile_runtime.py`
- `python3 ops/runtime_integrity.py`
- `python3 ops/metaos_conformance.py`

## Recovery Intent

- prefer deterministic repair over convenience
- preserve append-only truth and lineage during repair
- treat soak promote/reject as governed lineage transitions
- keep recovery evidence replayable and auditable

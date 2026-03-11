# Ops Commands

## Startup Validation

- `python3 ops/render_network.py`
- `python3 ops/validate_rpg.py`
- `python3 ops/validate_runtime_truth.py`
- `python3 ops/runtime_integrity.py`
- `python3 ops/runtime_summary.py`
- `python3 ops/reconcile_runtime.py`
- `python3 ops/autonomous_quality_loop.py --dry-run`

## Cluster Operations

- `bash ops/orchestrate_cluster.sh start`
- `bash ops/orchestrate_cluster.sh validate`
- `bash ops/orchestrate_cluster.sh status`
- `bash ops/orchestrate_cluster.sh autotune`
- `bash ops/orchestrate_cluster.sh daemon-start`
- `bash ops/orchestrate_cluster.sh daemon-status`
- `bash ops/orchestrate_cluster.sh daemon-stop`
- `bash ops/orchestrate_cluster.sh stop`
- `bash ops/prewarm_paper_worlds.sh`
- `bash ops/run_closed_loop_cycle.sh 3`
- `bash ops/run_closed_loop_matrix.sh`

## Repair / Recovery Commands

- `bash ops/recover_runtime.sh`
- `bash ops/close_quality_loop.sh`
- `python3 ops/metaos_conformance.py`

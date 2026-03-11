#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CYCLES="${1:-1}"

python3 "$ROOT_DIR/ops/rebuild_runtime_status.py"
python3 "$ROOT_DIR/ops/simulate_runtime_feedback.py" --cycles "$CYCLES"
python3 "$ROOT_DIR/ops/sanitize_runtime_status.py"
python3 "$ROOT_DIR/ops/runtime_integrity.py"
python3 "$ROOT_DIR/ops/reconcile_runtime.py"
python3 "$ROOT_DIR/ops/autonomous_quality_loop.py" --ignore-cooldown
python3 "$ROOT_DIR/ops/runtime_summary.py"

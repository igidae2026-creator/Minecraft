#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for profile in overloaded low_completion low_engagement inflation exploit mixed healthy; do
  echo "=== PROFILE=$profile ==="
  python3 "$ROOT_DIR/ops/reset_autonomy_controls.py"
  python3 "$ROOT_DIR/ops/rebuild_runtime_status.py"
  python3 "$ROOT_DIR/ops/simulate_runtime_feedback.py" --cycles 1 --profile "$profile" --mode replace
  python3 "$ROOT_DIR/ops/sanitize_runtime_status.py"
  python3 "$ROOT_DIR/ops/runtime_integrity.py"
  python3 "$ROOT_DIR/ops/reconcile_runtime.py"
  python3 "$ROOT_DIR/ops/autonomous_quality_loop.py" --ignore-cooldown
done

python3 "$ROOT_DIR/ops/runtime_summary.py"

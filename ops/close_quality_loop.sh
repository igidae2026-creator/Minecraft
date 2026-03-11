#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/ops/validate_runtime_truth.py"
python3 "$ROOT_DIR/ops/runtime_integrity.py"
python3 "$ROOT_DIR/ops/reconcile_runtime.py"
python3 "$ROOT_DIR/ops/autonomous_quality_loop.py"
python3 "$ROOT_DIR/ops/runtime_summary.py"

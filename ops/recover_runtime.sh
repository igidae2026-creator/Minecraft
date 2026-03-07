#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/ops/reconcile_runtime.py"
python3 "$ROOT_DIR/ops/runtime_integrity.py"
echo "RECOVERY_VALIDATED"

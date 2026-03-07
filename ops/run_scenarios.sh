#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/ops/render_network.py" >/dev/null
python3 "$ROOT_DIR/ops/validate_rpg.py"
python3 "$ROOT_DIR/ops/validate_runtime_truth.py"
python3 "$ROOT_DIR/ops/runtime_integrity.py"
pytest -q "$ROOT_DIR/tests"

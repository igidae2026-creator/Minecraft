#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-status}"

case "$ACTION" in
  start)
    bash "$ROOT_DIR/ops/start_network.sh"
    ;;
  stop)
    bash "$ROOT_DIR/ops/stop_network.sh"
    ;;
  validate)
    bash "$ROOT_DIR/ops/healthcheck.sh"
    python3 "$ROOT_DIR/ops/reconcile_runtime.py"
    ;;
  status)
    python3 "$ROOT_DIR/ops/runtime_integrity.py"
    ;;
  *)
    echo "usage: $0 <start|stop|validate|status>" >&2
    exit 1
    ;;
esac

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
  autotune)
    bash "$ROOT_DIR/ops/close_quality_loop.sh"
    ;;
  daemon-start)
    bash "$ROOT_DIR/ops/autonomy_daemon.sh" start
    ;;
  daemon-stop)
    bash "$ROOT_DIR/ops/autonomy_daemon.sh" stop
    ;;
  daemon-status)
    bash "$ROOT_DIR/ops/autonomy_daemon.sh" status
    ;;
  status)
    python3 "$ROOT_DIR/ops/runtime_integrity.py"
    ;;
  *)
    echo "usage: $0 <start|stop|validate|autotune|daemon-start|daemon-stop|daemon-status|status>" >&2
    exit 1
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="${PARALLEL_SESSION_NAME:-minecraft-parallel}"
ACTION="${1:-plan}"
WORKER_CMD="${PARALLEL_WORKER_CMD:-}"

plan() {
  python3 "$ROOT_DIR/ops/parallel_workstream_governor.py"
}

status() {
  plan >/dev/null
  cat "$ROOT_DIR/runtime_data/autonomy/parallel/parallel_assignments.yml"
}

launch() {
  local assignments_file="$ROOT_DIR/runtime_data/autonomy/parallel/parallel_assignments.yml"
  local assignments_json="$ROOT_DIR/runtime_data/autonomy/parallel/parallel_assignments.json"
  plan >/dev/null
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "PARALLEL_COMMAND_CENTER_ALREADY_RUNNING"
    tmux list-windows -t "$SESSION_NAME" -F 'WINDOW=#{window_index}:#{window_name}'
    return 0
  fi

  tmux new-session -d -s "$SESSION_NAME" -n commander "cd '$ROOT_DIR' && printf 'Commander session\\nAssignments: runtime_data/autonomy/parallel/parallel_assignments.yml\\n' && bash"

  python3 - "$ROOT_DIR" "$assignments_json" "$SESSION_NAME" "$WORKER_CMD" <<'PY'
from pathlib import Path
import json
import subprocess
import sys

root = Path(sys.argv[1])
assignments_file = Path(sys.argv[2])
session = sys.argv[3]
worker_cmd = sys.argv[4]

payload = json.loads(assignments_file.read_text(encoding="utf-8"))
for workstream in payload.get("workstreams", []):
    lane = workstream["lane"]
    packet_path = root / workstream["packet_path"]
    if worker_cmd:
        command = f"cd '{root}' && printf 'Packet: {packet_path}\\n' && {worker_cmd} '{packet_path}' || bash"
    else:
        command = f\"cd '{root}' && printf 'Packet: {packet_path}\\nBoundary: minecraft target only; out-of-scope expansion is forbidden.\\nSet PARALLEL_WORKER_CMD to auto-run a worker.\\n' && cat '{packet_path}' && bash\"
    subprocess.run(
        ["tmux", "new-window", "-t", session, "-n", lane, command],
        check=True,
    )
PY
  echo "PARALLEL_COMMAND_CENTER_STARTED"
  tmux list-windows -t "$SESSION_NAME" -F 'WINDOW=#{window_index}:#{window_name}'
}

stop() {
  if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "PARALLEL_COMMAND_CENTER_NOT_RUNNING"
    return 0
  fi
  tmux kill-session -t "$SESSION_NAME"
  echo "PARALLEL_COMMAND_CENTER_STOPPED"
}

case "$ACTION" in
  plan)
    plan
    ;;
  status)
    status
    ;;
  launch)
    launch
    ;;
  stop)
    stop
    ;;
  *)
    echo "usage: $0 <plan|status|launch|stop>" >&2
    exit 1
    ;;
esac

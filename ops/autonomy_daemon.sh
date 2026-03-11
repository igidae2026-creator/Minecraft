#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPERVISOR_DIR="$ROOT_DIR/runtime_data/autonomy/supervisor"
PID_FILE="$SUPERVISOR_DIR/supervisor.pid"
LOG_FILE="$SUPERVISOR_DIR/supervisor.log"
HEARTBEAT_FILE="$SUPERVISOR_DIR/heartbeat.json"
SESSION_NAME="minecraft-autonomy"
ACTION="${1:-status}"

mkdir -p "$SUPERVISOR_DIR"

is_running() {
  tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

case "$ACTION" in
  start)
    if is_running; then
      echo "AUTONOMY_DAEMON_ALREADY_RUNNING"
      tmux list-panes -t "$SESSION_NAME" -F 'SESSION=#{session_name} PID=#{pane_pid}'
      exit 0
    fi
    rm -f "$PID_FILE"
    tmux new-session -d -s "$SESSION_NAME" "cd '$ROOT_DIR' && exec python3 ops/autonomy_supervisor.py >>'$LOG_FILE' 2>&1"
    sleep 1
    if is_running; then
      echo "AUTONOMY_DAEMON_STARTED"
      tmux list-panes -t "$SESSION_NAME" -F 'SESSION=#{session_name} PID=#{pane_pid}'
    else
      echo "AUTONOMY_DAEMON_FAILED"
      exit 1
    fi
    ;;
  stop)
    if ! is_running; then
      echo "AUTONOMY_DAEMON_NOT_RUNNING"
      rm -f "$PID_FILE"
      exit 0
    fi
    tmux send-keys -t "$SESSION_NAME" C-c
    sleep 1
    if is_running; then
      tmux kill-session -t "$SESSION_NAME"
    fi
    rm -f "$PID_FILE"
    echo "AUTONOMY_DAEMON_STOPPED"
    ;;
  status)
    if is_running; then
      echo "AUTONOMY_DAEMON=running"
      tmux list-panes -t "$SESSION_NAME" -F 'SESSION=#{session_name} PID=#{pane_pid}'
    else
      echo "AUTONOMY_DAEMON=stopped"
    fi
    if [[ -f "$HEARTBEAT_FILE" ]]; then
      cat "$HEARTBEAT_FILE"
    fi
    ;;
  *)
    echo "usage: $0 <start|stop|status>" >&2
    exit 1
    ;;
esac

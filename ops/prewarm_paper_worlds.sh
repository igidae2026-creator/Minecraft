#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAVA_BIN="${JAVA_BIN:-$ROOT_DIR/.tooling/jdk/bin/java}"
PAPER_JAR_NAME="${PAPER_JAR_NAME:-paperclip.jar}"
WORLD_LIST=("${@:-lobby rpg_world dungeons boss_world events}")

if [[ ! -x "$JAVA_BIN" ]]; then
  echo "Missing Java binary: $JAVA_BIN" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/logs"

for server in "${WORLD_LIST[@]}"; do
  log_path="$ROOT_DIR/logs/${server}.prewarm.log"
  rm -f "$log_path"
  (
    cd "$ROOT_DIR/$server"
    timeout -k 10s 180s "$JAVA_BIN" -jar "$PAPER_JAR_NAME" nogui > "$log_path" 2>&1 || true
  )
  if ! rg -q "Done \\(" "$log_path"; then
    echo "PREWARM_FAILED:$server" >&2
    tail -n 80 "$log_path" >&2 || true
    exit 1
  fi
  echo "PREWARM_OK:$server"
done

echo "PREWARM_COMPLETE"

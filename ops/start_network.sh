#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VELOCITY_JAR="${VELOCITY_JAR:-$ROOT_DIR/proxy/velocity.jar}"
PAPER_JAR_NAME="${PAPER_JAR_NAME:-paperclip.jar}"
AUTO_DEPLOY_PLUGINS="${AUTO_DEPLOY_PLUGINS:-0}"
BACKEND_JAVA_OPTS="${BACKEND_JAVA_OPTS:--Xms1G -Xmx2G}"
PROXY_JAVA_OPTS="${PROXY_JAVA_OPTS:--Xms512M -Xmx1G}"

python3 "$ROOT_DIR/ops/render_network.py"
bash "$ROOT_DIR/ops/healthcheck.sh"

if [[ "$AUTO_DEPLOY_PLUGINS" == "1" ]]; then
  bash "$ROOT_DIR/ops/deploy_plugins.sh"
fi

if [[ ! -f "$VELOCITY_JAR" ]]; then
  echo "Missing Velocity jar: $VELOCITY_JAR" >&2
  exit 1
fi

for server in lobby rpg_world dungeons boss_world events; do
  if [[ ! -f "$ROOT_DIR/$server/$PAPER_JAR_NAME" ]]; then
    echo "Missing Paper jar for $server: $ROOT_DIR/$server/$PAPER_JAR_NAME" >&2
    exit 1
  fi
done

mkdir -p "$ROOT_DIR/run" "$ROOT_DIR/logs"

for server in lobby rpg_world dungeons boss_world events; do
  (
    cd "$ROOT_DIR/$server"
    nohup java $BACKEND_JAVA_OPTS -jar "$PAPER_JAR_NAME" nogui > "$ROOT_DIR/logs/${server}.log" 2>&1 &
    echo $! > "$ROOT_DIR/run/${server}.pid"
  )
done

(
  cd "$ROOT_DIR/proxy"
  nohup java $PROXY_JAVA_OPTS -jar "$VELOCITY_JAR" > "$ROOT_DIR/logs/velocity.log" 2>&1 &
  echo $! > "$ROOT_DIR/run/velocity.pid"
)

echo "NETWORK_START_OK"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/ops/render_network.py" >/dev/null
python3 "$ROOT_DIR/ops/validate_rpg.py" >/dev/null

required_files=(
  "$ROOT_DIR/proxy/velocity.toml"
  "$ROOT_DIR/proxy/forwarding.secret"
  "$ROOT_DIR/configs/network.yml"
  "$ROOT_DIR/configs/persistence.yml"
  "$ROOT_DIR/configs/exploit_guards.yml"
  "$ROOT_DIR/configs/scaling.yml"
  "$ROOT_DIR/configs/events.yml"
  "$ROOT_DIR/ops/plugin_matrix.yml"
)

for server in lobby rpg_world dungeons boss_world events; do
  required_files+=(
    "$ROOT_DIR/$server/server.properties"
    "$ROOT_DIR/$server/config/paper-global.yml"
  )
done

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "MISSING: $path" >&2
    exit 1
  fi
done

for script in "$ROOT_DIR"/ops/*.sh; do
  bash -n "$script"
done

echo "HEALTHCHECK_OK"

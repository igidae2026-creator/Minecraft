#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/ops/render_network.py" >/dev/null
python3 "$ROOT_DIR/ops/validate_rpg.py" >/dev/null
python3 "$ROOT_DIR/ops/runtime_integrity.py" >/dev/null
python3 "$ROOT_DIR/ops/validate_runtime_truth.py" >/dev/null
python3 "$ROOT_DIR/ops/runtime_summary.py" >/dev/null
python3 "$ROOT_DIR/ops/autonomous_quality_loop.py" --dry-run >/dev/null

required_files=(
  "$ROOT_DIR/proxy/velocity.toml"
  "$ROOT_DIR/proxy/forwarding.secret"
  "$ROOT_DIR/configs/network.yml"
  "$ROOT_DIR/configs/persistence.yml"
  "$ROOT_DIR/configs/exploit_guards.yml"
  "$ROOT_DIR/configs/scaling.yml"
  "$ROOT_DIR/configs/events.yml"
  "$ROOT_DIR/configs/dungeon_templates.yml"
  "$ROOT_DIR/configs/boss_behaviors.yml"
  "$ROOT_DIR/configs/event_scheduler.yml"
  "$ROOT_DIR/configs/reward_pools.yml"
  "$ROOT_DIR/configs/gear_tiers.yml"
  "$ROOT_DIR/configs/runtime_monitor.yml"
  "$ROOT_DIR/configs/adaptive_rules.yml"
  "$ROOT_DIR/configs/autonomy.yml"
  "$ROOT_DIR/configs/guilds.yml"
  "$ROOT_DIR/configs/prestige.yml"
  "$ROOT_DIR/configs/streaks.yml"
  "$ROOT_DIR/configs/lobby.yml"
  "$ROOT_DIR/configs/genres.yml"
  "$ROOT_DIR/ops/plugin_matrix.yml"
  "$ROOT_DIR/ops/runtime_integrity.py"
  "$ROOT_DIR/ops/runtime_summary.py"
  "$ROOT_DIR/ops/validate_runtime_truth.py"
  "$ROOT_DIR/ops/reconcile_runtime.py"
  "$ROOT_DIR/ops/autonomous_quality_loop.py"
  "$ROOT_DIR/ops/close_quality_loop.sh"
  "$ROOT_DIR/ops/recover_runtime.sh"
  "$ROOT_DIR/ops/orchestrate_cluster.sh"
  "$ROOT_DIR/ops/RUNBOOK.md"
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

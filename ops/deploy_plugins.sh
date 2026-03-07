#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MATRIX_PATH="$ROOT_DIR/ops/plugin_matrix.yml"
BUILD_DIR_GLOB="$ROOT_DIR/plugins/*/build/libs"

python3 - "$ROOT_DIR" "$MATRIX_PATH" <<'PY'
from __future__ import annotations
import shutil
import sys
from pathlib import Path
import yaml

root = Path(sys.argv[1])
matrix_path = Path(sys.argv[2])
matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))

jar_index: dict[str, Path] = {}
for plugin_dir in (root / "plugins").iterdir():
    libs = plugin_dir / "build" / "libs"
    if not libs.is_dir():
        continue
    jars = sorted([path for path in libs.iterdir() if path.suffix == ".jar" and "plain" not in path.name])
    if jars:
        jar_index[plugin_dir.name] = jars[-1]

missing = []
for server, plugins in matrix.items():
    plugins_dir = root / server / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    for existing in plugins_dir.glob("*.jar"):
        if existing.name.startswith(("rpg_", "economy_", "quest_", "boss_", "dungeon_", "guild_", "skill_", "event_", "metrics_")):
            existing.unlink()
    for plugin_name in plugins:
        jar = jar_index.get(plugin_name)
        if jar is None:
            missing.append(plugin_name)
            continue
        shutil.copy2(jar, plugins_dir / jar.name)

if missing:
    print("MISSING_JARS=" + ",".join(sorted(set(missing))))
    raise SystemExit(1)

print("DEPLOY_OK")
PY

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRADLE_BIN="${GRADLE_BIN:-gradle}"

if [[ -x "$ROOT_DIR/gradlew" ]]; then
  GRADLE_BIN="$ROOT_DIR/gradlew"
fi

if ! command -v "$GRADLE_BIN" >/dev/null 2>&1 && [[ ! -x "$GRADLE_BIN" ]]; then
  echo "Gradle executable not found: $GRADLE_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
"$GRADLE_BIN" clean build

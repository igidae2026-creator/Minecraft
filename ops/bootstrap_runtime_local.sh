#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tooling"
JDK_DIR="$TOOLS_DIR/jdk"
GRADLE_DIR="$TOOLS_DIR/gradle"
DOWNLOAD_DIR="$TOOLS_DIR/downloads"
PAPER_VERSION="${PAPER_VERSION:-1.20.6}"

mkdir -p "$TOOLS_DIR" "$DOWNLOAD_DIR"

download() {
  local url="$1"
  local output="$2"
  curl -fsSL "$url" -o "$output"
}

if [[ ! -x "$JDK_DIR/bin/java" ]]; then
  mkdir -p "$JDK_DIR"
  JDK_TARBALL="$DOWNLOAD_DIR/jdk21.tar.gz"
  download "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse" "$JDK_TARBALL"
  rm -rf "$JDK_DIR"
  mkdir -p "$JDK_DIR"
  tar -xzf "$JDK_TARBALL" -C "$JDK_DIR" --strip-components=1
fi

if [[ ! -x "$GRADLE_DIR/bin/gradle" ]]; then
  GRADLE_ZIP="$DOWNLOAD_DIR/gradle.zip"
  download "https://services.gradle.org/distributions/gradle-8.10.2-bin.zip" "$GRADLE_ZIP"
  rm -rf "$GRADLE_DIR"
  mkdir -p "$GRADLE_DIR"
  unzip -q "$GRADLE_ZIP" -d "$TOOLS_DIR"
  mv "$TOOLS_DIR"/gradle-8.10.2/* "$GRADLE_DIR"/
  rmdir "$TOOLS_DIR"/gradle-8.10.2
fi

if [[ ! -f "$ROOT_DIR/proxy/velocity.jar" ]]; then
  VELOCITY_META="$DOWNLOAD_DIR/velocity-meta.json"
  download "https://fill.papermc.io/v3/projects/velocity" "$VELOCITY_META"
  VELOCITY_VERSION="$(python3 - <<'PY' "$VELOCITY_META"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
versions = data.get("versions") or {}
candidates = []
for branch_versions in versions.values():
    for version in branch_versions:
        if "SNAPSHOT" not in version:
            candidates.append(version)
if not candidates:
    for branch_versions in versions.values():
        candidates.extend(branch_versions)
print(sorted(candidates)[-1] if candidates else "")
PY
)"
  if [[ -z "$VELOCITY_VERSION" ]]; then
    echo "Unable to resolve Velocity version" >&2
    exit 1
  fi
  VELOCITY_BUILD_META="$DOWNLOAD_DIR/velocity-builds.json"
  download "https://fill.papermc.io/v3/projects/velocity/versions/$VELOCITY_VERSION/builds" "$VELOCITY_BUILD_META"
  VELOCITY_DOWNLOAD_URL="$(python3 - <<'PY' "$VELOCITY_BUILD_META"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if isinstance(data, dict):
    builds = data.get("builds") or []
else:
    builds = data
entry = builds[0] if builds and isinstance(builds[0], dict) else {}
download = ((entry.get("downloads") or {}).get("server:default") or {})
print(download.get("url", ""))
PY
)"
  if [[ -z "$VELOCITY_DOWNLOAD_URL" ]]; then
    echo "Unable to resolve Velocity download URL" >&2
    exit 1
  fi
  download "$VELOCITY_DOWNLOAD_URL" "$ROOT_DIR/proxy/velocity.jar"
fi

PAPER_META="$DOWNLOAD_DIR/paper-builds.json"
download "https://fill.papermc.io/v3/projects/paper/versions/$PAPER_VERSION/builds" "$PAPER_META"
PAPER_DOWNLOAD_URL="$(python3 - <<'PY' "$PAPER_META"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if isinstance(data, dict):
    builds = data.get("builds") or []
else:
    builds = data
entry = builds[0] if builds and isinstance(builds[0], dict) else {}
download = ((entry.get("downloads") or {}).get("server:default") or {})
print(download.get("url", ""))
PY
)"
if [[ -z "$PAPER_DOWNLOAD_URL" ]]; then
  echo "Unable to resolve Paper download URL for $PAPER_VERSION" >&2
  exit 1
fi

for server in lobby rpg_world dungeons boss_world events; do
  if [[ ! -f "$ROOT_DIR/$server/paperclip.jar" ]]; then
    download "$PAPER_DOWNLOAD_URL" "$ROOT_DIR/$server/paperclip.jar"
  fi
  echo "eula=true" > "$ROOT_DIR/$server/eula.txt"
done

echo "BOOTSTRAP_RUNTIME_LOCAL_OK"
echo "JAVA_HOME=$JDK_DIR"
echo "GRADLE_BIN=$GRADLE_DIR/bin/gradle"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="${1:-$ROOT_DIR/metrics.prom}"

python3 - "$ROOT_DIR" "$OUTPUT_PATH" <<'PY'
from pathlib import Path
import sys
import yaml

root = Path(sys.argv[1])
out = Path(sys.argv[2])
configs = root / "configs"
ops = root / "ops"

with (configs / "network.yml").open("r", encoding="utf-8") as handle:
    network = yaml.safe_load(handle)
with (configs / "economy.yml").open("r", encoding="utf-8") as handle:
    economy = yaml.safe_load(handle)
with (configs / "scaling.yml").open("r", encoding="utf-8") as handle:
    scaling = yaml.safe_load(handle)
with (configs / "persistence.yml").open("r", encoding="utf-8") as handle:
    persistence = yaml.safe_load(handle)
with (ops / "plugin_matrix.yml").open("r", encoding="utf-8") as handle:
    matrix = yaml.safe_load(handle)

servers = network["servers"]
metrics = []
metrics.append(f"rpg_network_servers_total {len(servers)}")
metrics.append(f"rpg_network_proxy_try_order {len(network['proxy']['try'])}")
metrics.append(f"rpg_network_total_capacity {sum(server['max_players'] for server in servers.values())}")
metrics.append(f"rpg_network_average_view_distance {sum(server['view_distance'] for server in servers.values()) / len(servers):.2f}")
metrics.append(f"rpg_network_market_tax {economy['market_tax']}")
metrics.append(f"rpg_network_peak_players_target {scaling['targets']['peak_players']}")
metrics.append(f"rpg_network_local_fallback_enabled {1 if persistence['local_fallback']['enabled'] else 0}")
metrics.append(f"rpg_network_runtime_artifact_exports {len(list((root / 'runtime_data' / 'artifacts').glob('*.yml')))}")
metrics.append(f"rpg_network_runtime_policy_exports {len(list((root / 'runtime_data' / 'policies').glob('*.yml')))}")
for server_name, plugins in matrix.items():
    metrics.append(f"rpg_network_plugins_per_server{{server=\"{server_name}\"}} {len(plugins)}")

out.write_text("\n".join(metrics) + "\n", encoding="utf-8")
print(out)
PY

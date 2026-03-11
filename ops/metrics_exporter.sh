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
control_state_path = root / "runtime_data" / "autonomy" / "control" / "state.yml"
active_soak = False
steady_noop_streak = 0
execution_threshold_ready = False
operational_threshold_ready = False
autonomy_threshold_ready = False
final_threshold_ready = False
if control_state_path.exists():
    active_block = False
    for raw in control_state_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("execution_threshold_ready:"):
            execution_threshold_ready = stripped.split(":", 1)[1].strip().lower() == "true"
        if stripped.startswith("operational_threshold_ready:"):
            operational_threshold_ready = stripped.split(":", 1)[1].strip().lower() == "true"
        if stripped.startswith("autonomy_threshold_ready:"):
            autonomy_threshold_ready = stripped.split(":", 1)[1].strip().lower() == "true"
        if stripped.startswith("steady_noop_streak:"):
            steady_noop_streak = int(stripped.split(":", 1)[1].strip() or "0")
        if stripped.startswith("final_threshold_ready:"):
            final_threshold_ready = stripped.split(":", 1)[1].strip().lower() == "true"
        if raw.startswith("active_soak:"):
            active_block = True
            continue
        if active_block:
            if raw.startswith(" ") and raw.strip().startswith("decision_id:"):
                active_soak = bool(raw.split(":", 1)[1].strip())
                active_block = False
                continue
            if raw and not raw.startswith(" "):
                active_block = False
lineage_path = root / "runtime_data" / "autonomy" / "control" / "lineage.jsonl"
lineage_entries = 0
if lineage_path.exists():
    lineage_entries = sum(1 for _ in lineage_path.open("r", encoding="utf-8"))
artifact_governor_summary = {}
artifact_governor_summary_path = root / "runtime_data" / "autonomy" / "artifact_governor_summary.yml"
if artifact_governor_summary_path.exists():
    with artifact_governor_summary_path.open("r", encoding="utf-8") as handle:
        artifact_governor_summary = yaml.safe_load(handle) or {}
content_governor_summary = {}
content_governor_summary_path = root / "runtime_data" / "autonomy" / "content_governor_summary.yml"
if content_governor_summary_path.exists():
    with content_governor_summary_path.open("r", encoding="utf-8") as handle:
        content_governor_summary = yaml.safe_load(handle) or {}
economy_governor_summary = {}
economy_governor_summary_path = root / "runtime_data" / "autonomy" / "economy_governor_summary.yml"
if economy_governor_summary_path.exists():
    with economy_governor_summary_path.open("r", encoding="utf-8") as handle:
        economy_governor_summary = yaml.safe_load(handle) or {}
anti_cheat_governor_summary = {}
anti_cheat_governor_summary_path = root / "runtime_data" / "autonomy" / "anti_cheat_governor_summary.yml"
if anti_cheat_governor_summary_path.exists():
    with anti_cheat_governor_summary_path.open("r", encoding="utf-8") as handle:
        anti_cheat_governor_summary = yaml.safe_load(handle) or {}
liveops_governor_summary = {}
liveops_governor_summary_path = root / "runtime_data" / "autonomy" / "liveops_governor_summary.yml"
if liveops_governor_summary_path.exists():
    with liveops_governor_summary_path.open("r", encoding="utf-8") as handle:
        liveops_governor_summary = yaml.safe_load(handle) or {}
final_threshold_eval = {}
final_threshold_eval_path = root / "runtime_data" / "autonomy" / "final_threshold_eval.json"
if final_threshold_eval_path.exists():
    import json
    final_threshold_eval = json.loads(final_threshold_eval_path.read_text(encoding="utf-8"))

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
metrics.append(f"rpg_network_runtime_experiment_exports {len(list((root / 'runtime_data' / 'experiments').glob('*.yml')))}")
metrics.append(f"rpg_network_runtime_incident_exports {len(list((root / 'runtime_data' / 'incidents').glob('*.yml')))}")
metrics.append(f"rpg_network_runtime_knowledge_exports {len(list((root / 'runtime_data' / 'knowledge').glob('*.yml')))}")
metrics.append(f"rpg_network_autonomy_decisions_total {len(list((root / 'runtime_data' / 'autonomy' / 'decisions').glob('*.yml')))}")
metrics.append(f"rpg_network_autonomy_active_soak {1 if active_soak else 0}")
metrics.append(f"rpg_network_autonomy_control_lineage_entries {lineage_entries}")
metrics.append(f"rpg_network_autonomy_execution_threshold_ready {1 if execution_threshold_ready else 0}")
metrics.append(f"rpg_network_autonomy_operational_threshold_ready {1 if operational_threshold_ready else 0}")
metrics.append(f"rpg_network_autonomy_autonomy_threshold_ready {1 if autonomy_threshold_ready else 0}")
metrics.append(f"rpg_network_autonomy_steady_noop_streak {steady_noop_streak}")
metrics.append(f"rpg_network_autonomy_final_threshold_ready {1 if final_threshold_ready else 0}")
metrics.append(f"rpg_network_artifact_governor_proposed {int(artifact_governor_summary.get('proposed', 0))}")
metrics.append(f"rpg_network_artifact_governor_accepted {int(artifact_governor_summary.get('accepted', 0))}")
metrics.append(f"rpg_network_artifact_governor_canonical_classes {len(artifact_governor_summary.get('canonical_registry', []))}")
metrics.append(f"rpg_network_content_generated {int(content_governor_summary.get('generated', 0))}")
metrics.append(f"rpg_network_content_promoted {int(content_governor_summary.get('promoted', 0))}")
metrics.append(f"rpg_network_content_held {int(content_governor_summary.get('held', 0))}")
metrics.append(f"rpg_network_content_families {len((content_governor_summary.get('by_type', {}) or {}))}")
metrics.append(f"rpg_network_economy_action_adjust {1 if economy_governor_summary.get('action', '') == 'adjust' else 0}")
metrics.append(f"rpg_network_economy_inflation_ratio {economy_governor_summary.get('inflation_ratio', 0)}")
metrics.append(f"rpg_network_anti_cheat_sandbox_cases {int(anti_cheat_governor_summary.get('sandbox_cases', 0))}")
metrics.append(f"rpg_network_liveops_promoted_actions {int(liveops_governor_summary.get('promoted_actions', 0))}")
metrics.append(f"rpg_network_liveops_held_actions {int(liveops_governor_summary.get('held_actions', 0))}")
metrics.append(f"rpg_network_final_threshold_bundle_ready {1 if final_threshold_eval.get('final_threshold_ready', False) else 0}")
metrics.append(f"rpg_network_final_threshold_bundle_failed_criteria {len(final_threshold_eval.get('failed_criteria', []))}")
metrics.append(f"rpg_network_final_threshold_bundle_human_lift {final_threshold_eval.get('quality_lift_if_human_intervenes', 0)}")
for server_name, plugins in matrix.items():
    metrics.append(f"rpg_network_plugins_per_server{{server=\"{server_name}\"}} {len(plugins)}")

out.write_text("\n".join(metrics) + "\n", encoding="utf-8")
print(out)
PY

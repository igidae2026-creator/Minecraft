#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="${1:-$ROOT_DIR/metrics.prom}"

python3 - "$ROOT_DIR" "$OUTPUT_PATH" <<'PY'
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str((Path(sys.argv[1]) / "ops").resolve()))
from final_threshold_eval import load_eval_bundle

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


def load_scalar_summary(path: Path) -> dict:
    payload = {}
    if not path.exists():
        return payload
    current_map_key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if raw.startswith("  ") and current_map_key:
            child = raw.strip()
            if ":" not in child:
                continue
            key, value = child.split(":", 1)
            payload.setdefault(current_map_key, {})[key.strip()] = _parse_scalar(value.strip())
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            payload[key] = {}
            current_map_key = key
            continue
        payload[key] = _parse_scalar(value)
        current_map_key = None
    return payload


def _parse_scalar(value: str):
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
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
    artifact_governor_summary = load_scalar_summary(artifact_governor_summary_path)
content_governor_summary = {}
content_governor_summary_path = root / "runtime_data" / "autonomy" / "content_governor_summary.yml"
if content_governor_summary_path.exists():
    content_governor_summary = load_scalar_summary(content_governor_summary_path)
content_strategy_summary = {}
content_strategy_summary_path = root / "runtime_data" / "autonomy" / "content_strategy_summary.yml"
if content_strategy_summary_path.exists():
    content_strategy_summary = load_scalar_summary(content_strategy_summary_path)
content_soak_summary = {}
content_soak_summary_path = root / "runtime_data" / "autonomy" / "content_soak_summary.yml"
if content_soak_summary_path.exists():
    content_soak_summary = load_scalar_summary(content_soak_summary_path)
content_bundle_summary = {}
content_bundle_summary_path = root / "runtime_data" / "autonomy" / "content_bundle_summary.yml"
if content_bundle_summary_path.exists():
    content_bundle_summary = load_scalar_summary(content_bundle_summary_path)
repo_bundle_summary = {}
repo_bundle_summary_path = root / "runtime_data" / "autonomy" / "repo_bundle_summary.yml"
if repo_bundle_summary_path.exists():
    repo_bundle_summary = load_scalar_summary(repo_bundle_summary_path)
minecraft_bundle_summary = {}
minecraft_bundle_summary_path = root / "runtime_data" / "autonomy" / "minecraft_bundle_summary.yml"
if minecraft_bundle_summary_path.exists():
    minecraft_bundle_summary = load_scalar_summary(minecraft_bundle_summary_path)
minecraft_strategy_summary = {}
minecraft_strategy_summary_path = root / "runtime_data" / "autonomy" / "minecraft_strategy_summary.yml"
if minecraft_strategy_summary_path.exists():
    minecraft_strategy_summary = load_scalar_summary(minecraft_strategy_summary_path)
minecraft_soak_summary = {}
minecraft_soak_summary_path = root / "runtime_data" / "autonomy" / "minecraft_soak_summary.yml"
if minecraft_soak_summary_path.exists():
    minecraft_soak_summary = load_scalar_summary(minecraft_soak_summary_path)
player_experience_summary = {}
player_experience_summary_path = root / "runtime_data" / "autonomy" / "player_experience_summary.yml"
if player_experience_summary_path.exists():
    player_experience_summary = load_scalar_summary(player_experience_summary_path)
player_experience_soak_summary = {}
player_experience_soak_summary_path = root / "runtime_data" / "autonomy" / "player_experience_soak_summary.yml"
if player_experience_soak_summary_path.exists():
    player_experience_soak_summary = load_scalar_summary(player_experience_soak_summary_path)
gameplay_progression_summary = {}
gameplay_progression_summary_path = root / "runtime_data" / "autonomy" / "gameplay_progression_summary.yml"
if gameplay_progression_summary_path.exists():
    gameplay_progression_summary = load_scalar_summary(gameplay_progression_summary_path)
engagement_fatigue_summary = {}
engagement_fatigue_summary_path = root / "runtime_data" / "autonomy" / "engagement_fatigue_summary.yml"
if engagement_fatigue_summary_path.exists():
    engagement_fatigue_summary = load_scalar_summary(engagement_fatigue_summary_path)
economy_governor_summary = {}
economy_governor_summary_path = root / "runtime_data" / "autonomy" / "economy_governor_summary.yml"
if economy_governor_summary_path.exists():
    economy_governor_summary = load_scalar_summary(economy_governor_summary_path)
anti_cheat_governor_summary = {}
anti_cheat_governor_summary_path = root / "runtime_data" / "autonomy" / "anti_cheat_governor_summary.yml"
if anti_cheat_governor_summary_path.exists():
    anti_cheat_governor_summary = load_scalar_summary(anti_cheat_governor_summary_path)
liveops_governor_summary = {}
liveops_governor_summary_path = root / "runtime_data" / "autonomy" / "liveops_governor_summary.yml"
if liveops_governor_summary_path.exists():
    liveops_governor_summary = load_scalar_summary(liveops_governor_summary_path)
material_inventory_summary = {}
material_inventory_summary_path = root / "runtime_data" / "autonomy" / "material_inventory_summary.yml"
if material_inventory_summary_path.exists():
    material_inventory_summary = load_scalar_summary(material_inventory_summary_path)
runtime_partition_summary = {}
runtime_partition_summary_path = root / "runtime_data" / "autonomy" / "runtime_partition_summary.yml"
if runtime_partition_summary_path.exists():
    runtime_partition_summary = load_scalar_summary(runtime_partition_summary_path)
final_threshold_eval = load_eval_bundle(refresh_if_stale=True)

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
canonical_classes = artifact_governor_summary.get("canonical_classes")
if canonical_classes is None:
    canonical_classes = len(artifact_governor_summary.get("canonical_registry", []))
metrics.append(f"rpg_network_artifact_governor_canonical_classes {canonical_classes}")
metrics.append(f"rpg_network_content_generated {int(content_governor_summary.get('generated', 0))}")
metrics.append(f"rpg_network_content_promoted {int(content_governor_summary.get('promoted', 0))}")
metrics.append(f"rpg_network_content_held {int(content_governor_summary.get('held', 0))}")
metrics.append(f"rpg_network_content_families {len((content_governor_summary.get('by_type', {}) or {}))}")
metrics.append(f"rpg_network_content_average_depth_score {content_governor_summary.get('average_depth_score', 0)}")
metrics.append(f"rpg_network_content_average_retention_proxy {content_governor_summary.get('average_retention_proxy', 0)}")
metrics.append(f"rpg_network_content_average_quality_score {content_governor_summary.get('average_quality_score', 0)}")
metrics.append(f"rpg_network_content_first_loop_coverage_score {content_governor_summary.get('first_loop_coverage_score', 0)}")
metrics.append(f"rpg_network_content_social_loop_density {content_governor_summary.get('social_loop_density', 0)}")
metrics.append(f"rpg_network_content_replayable_loop_score {content_governor_summary.get('replayable_loop_score', 0)}")
focus_csv = str(content_strategy_summary.get("next_focus_csv", ""))
repair_csv = str(content_strategy_summary.get("recommended_repairs_csv", ""))
focus_count = len([item for item in focus_csv.split(",") if item])
repair_count = int(content_strategy_summary.get("recommended_repairs_count", len([item for item in repair_csv.split(",") if item])))
metrics.append(f"rpg_network_content_recommended_repairs {repair_count}")
metrics.append(f"rpg_network_content_focus_families {focus_count}")
metrics.append(f"rpg_network_content_runtime_queue_avg {content_strategy_summary.get('runtime_queue_avg', 0)}")
metrics.append(f"rpg_network_content_runtime_event_join_avg {content_strategy_summary.get('runtime_event_join_avg', 0)}")
metrics.append(f"rpg_network_content_runtime_return_player_reward_avg {content_strategy_summary.get('runtime_return_player_reward_avg', 0)}")
metrics.append(f"rpg_network_gameplay_progression_total_score {gameplay_progression_summary.get('progression_total_score', 0)}")
metrics.append(f"rpg_network_engagement_fatigue_gap_score {engagement_fatigue_summary.get('fatigue_gap_score', 0)}")
metrics.append(f"rpg_network_engagement_fatigue_high {1 if engagement_fatigue_summary.get('fatigue_state', '') == 'high' else 0}")
metrics.append(f"rpg_network_content_soak_recommended_repairs {content_soak_summary.get('recommended_repairs_count', 0)}")
metrics.append(f"rpg_network_content_soak_stable {1 if content_soak_summary.get('content_soak_state', '') == 'stable' else 0}")
metrics.append(f"rpg_network_content_bundle_completed {content_bundle_summary.get('bundle_completed', 0)}")
metrics.append(f"rpg_network_content_bundle_total {content_bundle_summary.get('bundle_total', 0)}")
metrics.append(f"rpg_network_content_bundle_completion_percent {content_bundle_summary.get('bundle_completion_percent', 0)}")
metrics.append(f"rpg_network_content_player_facing_depth_complete {1 if content_bundle_summary.get('player_facing_depth_state', '') == 'complete' else 0}")
metrics.append(f"rpg_network_repo_bundle_completed {repo_bundle_summary.get('bundle_completed', 0)}")
metrics.append(f"rpg_network_repo_bundle_total {repo_bundle_summary.get('bundle_total', 0)}")
metrics.append(f"rpg_network_repo_bundle_completion_percent {repo_bundle_summary.get('bundle_completion_percent', 0)}")
metrics.append(f"rpg_network_minecraft_bundle_completed {minecraft_bundle_summary.get('bundle_completed', 0)}")
metrics.append(f"rpg_network_minecraft_bundle_total {minecraft_bundle_summary.get('bundle_total', 0)}")
metrics.append(f"rpg_network_minecraft_bundle_completion_percent {minecraft_bundle_summary.get('bundle_completion_percent', 0)}")
metrics.append(f"rpg_network_minecraft_recommended_repairs {minecraft_strategy_summary.get('recommended_repairs_count', 0)}")
metrics.append(f"rpg_network_minecraft_soak_stable {1 if minecraft_soak_summary.get('minecraft_soak_state', '') == 'stable' else 0}")
metrics.append(f"rpg_network_player_experience_percent {player_experience_summary.get('estimated_completeness_percent', 0)}")
metrics.append(f"rpg_network_player_experience_first_session_strength {player_experience_summary.get('first_session_strength', 0)}")
metrics.append(f"rpg_network_player_experience_trust_pull {player_experience_summary.get('trust_pull', 0)}")
metrics.append(f"rpg_network_player_experience_soak_stable {1 if player_experience_soak_summary.get('player_experience_soak_state', '') == 'stable' else 0}")
metrics.append(f"rpg_network_economy_action_adjust {1 if economy_governor_summary.get('action', '') == 'adjust' else 0}")
metrics.append(f"rpg_network_economy_inflation_ratio {economy_governor_summary.get('inflation_ratio', 0)}")
metrics.append(f"rpg_network_anti_cheat_sandbox_cases {int(anti_cheat_governor_summary.get('sandbox_cases', 0))}")
metrics.append(f"rpg_network_anti_cheat_progression_protection_score {anti_cheat_governor_summary.get('progression_protection_score', 0)}")
metrics.append(f"rpg_network_liveops_promoted_actions {int(liveops_governor_summary.get('promoted_actions', 0))}")
metrics.append(f"rpg_network_liveops_held_actions {int(liveops_governor_summary.get('held_actions', 0))}")
metrics.append(f"rpg_network_liveops_boost_reentry {1 if liveops_governor_summary.get('boost_reentry', False) else 0}")
metrics.append(f"rpg_network_material_total_files {int(material_inventory_summary.get('total_files', 0))}")
metrics.append(f"rpg_network_material_canonical_source_files {int(material_inventory_summary.get('canonical_source_files', 0))}")
metrics.append(f"rpg_network_material_append_only_runtime_truth_files {int(material_inventory_summary.get('append_only_runtime_truth_files', 0))}")
metrics.append(f"rpg_network_runtime_partition_files {int(runtime_partition_summary.get('runtime_files', 0))}")
metrics.append(f"rpg_network_runtime_partition_volatile_files {int(runtime_partition_summary.get('volatile_runtime_files', 0))}")
metrics.append(f"rpg_network_runtime_partition_canonical_snapshot_files {int(runtime_partition_summary.get('canonical_snapshot_files', 0))}")
metrics.append(f"rpg_network_runtime_partition_archive_candidate_files {int(runtime_partition_summary.get('archive_candidate_files', 0))}")
metrics.append(f"rpg_network_final_threshold_bundle_ready {1 if final_threshold_eval.get('final_threshold_ready', False) else 0}")
metrics.append(f"rpg_network_final_threshold_bundle_failed_criteria {len(final_threshold_eval.get('failed_criteria', []))}")
metrics.append(f"rpg_network_final_threshold_bundle_human_lift {final_threshold_eval.get('quality_lift_if_human_intervenes', 0)}")
for server_name, plugins in matrix.items():
    metrics.append(f"rpg_network_plugins_per_server{{server=\"{server_name}\"}} {len(plugins)}")

out.write_text("\n".join(metrics) + "\n", encoding="utf-8")
print(out)
PY

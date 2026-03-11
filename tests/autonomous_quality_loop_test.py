from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from helpers import ROOT, dump_yaml, load_yaml


def _backup_runtime(tmp_path: Path) -> Path:
    runtime_data = ROOT / "runtime_data"
    backup = tmp_path / "runtime_backup"
    shutil.copytree(runtime_data, backup, dirs_exist_ok=True)
    return backup


def _backup_configs(tmp_path: Path) -> Path:
    config_dir = ROOT / "configs"
    backup = tmp_path / "config_backup"
    shutil.copytree(config_dir, backup, dirs_exist_ok=True)
    return backup


def _restore_runtime(backup: Path) -> None:
    runtime_data = ROOT / "runtime_data"
    if runtime_data.exists():
        shutil.rmtree(runtime_data, ignore_errors=True)
    shutil.copytree(backup, runtime_data, dirs_exist_ok=True)


def _restore_configs(backup: Path) -> None:
    config_dir = ROOT / "configs"
    if config_dir.exists():
        shutil.rmtree(config_dir, ignore_errors=True)
    shutil.copytree(backup, config_dir, dirs_exist_ok=True)


def _reset_status_dir() -> Path:
    status_dir = ROOT / "runtime_data" / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    for path in status_dir.glob("*.yml"):
        path.unlink()
    return status_dir


def _reset_autonomy_surface() -> None:
    autonomy_dir = ROOT / "runtime_data" / "autonomy"
    for relative in ("control", "decisions", "backups"):
        target = autonomy_dir / relative
        if target.exists():
            shutil.rmtree(target)


def test_autonomous_quality_loop_blocks_on_authority_faults(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        status = {
            "deterministic_transfer_service": {"quarantines": 1},
            "session_authority_service": {"split_brain_detections": 1},
            "runtime_knowledge_index": {"records": 3},
        }
        (status_dir / "fault.yml").write_text(dump_yaml(status), encoding="utf-8")

        before = load_yaml("configs/adaptive_rules.yml")
        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        after = load_yaml("configs/adaptive_rules.yml")
        assert result.returncode == 1
        assert "MODE=blocked" in result.stdout
        assert "BLOCKER=transfer_quarantine:fault" in result.stdout
        assert "BLOCKER=split_brain:fault" in result.stdout
        assert before == after
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_applies_bounded_tuning_and_records_decision(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        status = {
            "dungeon_started": 20,
            "dungeon_completed": 6,
            "event_started": 4,
            "event_join_count": 3,
            "queue_size": 42,
            "player_density": 78,
            "network_routing_latency_ms": 110,
            "runtime_composite_pressure": 0.81,
            "progression_level_up": 3,
            "return_player_reward": 1,
            "streak_progress": 2,
            "rivalry_match": 1,
            "runtime_knowledge_index": {"records": 9},
            "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
            "session_authority_service": {"split_brain_detections": 0},
            "exploit_forensics_plane": {"incident_total": 0},
            "experiment_registry": {"rollbacks": 0},
            "policy_registry": {"rollbacks": 0},
            "economy_item_authority_plane": {"quarantined_items": 0},
        }
        (status_dir / "healthy-but-pressured.yml").write_text(dump_yaml(status), encoding="utf-8")

        before_rules = load_yaml("configs/adaptive_rules.yml")
        before_monitor = load_yaml("configs/runtime_monitor.yml")
        before_pressure = load_yaml("configs/pressure.yml")
        before_rules["matchmaking"]["high_queue_seconds"] = 60
        before_rules["events"]["low_join_rate"] = 0.25
        before_rules["rewards"]["low_completion_rate"] = 0.45
        before_monitor["scaling"]["density_scale_trigger"] = 65
        before_pressure["controls"]["noncritical_spawn_suppression_threshold"] = 0.85
        before_pressure["controls"]["queue_admission_threshold"] = 0.9
        (ROOT / "configs" / "adaptive_rules.yml").write_text(dump_yaml(before_rules, sort_keys=False), encoding="utf-8")
        (ROOT / "configs" / "runtime_monitor.yml").write_text(dump_yaml(before_monitor, sort_keys=False), encoding="utf-8")
        (ROOT / "configs" / "pressure.yml").write_text(dump_yaml(before_pressure, sort_keys=False), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        after_rules = load_yaml("configs/adaptive_rules.yml")
        after_monitor = load_yaml("configs/runtime_monitor.yml")
        after_pressure = load_yaml("configs/pressure.yml")

        assert "MODE=apply" in result.stdout
        assert after_rules["matchmaking"]["high_queue_seconds"] < before_rules["matchmaking"]["high_queue_seconds"]
        assert after_rules["events"]["low_join_rate"] > before_rules["events"]["low_join_rate"]
        assert after_rules["rewards"]["low_completion_rate"] > before_rules["rewards"]["low_completion_rate"]
        assert after_monitor["scaling"]["density_scale_trigger"] < before_monitor["scaling"]["density_scale_trigger"]
        assert after_pressure["controls"]["noncritical_spawn_suppression_threshold"] < before_pressure["controls"]["noncritical_spawn_suppression_threshold"]
        assert after_pressure["controls"]["queue_admission_threshold"] < before_pressure["controls"]["queue_admission_threshold"]

        decision_files = list((ROOT / "runtime_data" / "autonomy" / "decisions").glob("*.yml"))
        backup_dirs = list((ROOT / "runtime_data" / "autonomy" / "backups").glob("*"))
        control_state_text = (ROOT / "runtime_data" / "autonomy" / "control" / "state.yml").read_text(encoding="utf-8")
        lineage_log = ROOT / "runtime_data" / "autonomy" / "control" / "lineage.jsonl"
        assert decision_files
        assert backup_dirs
        assert "active_soak:" in control_state_text
        assert "last_mode: apply" in control_state_text
        assert lineage_log.is_file()

        latest_decision = decision_files[-1].read_text(encoding="utf-8")
        assert "runtime_fingerprint:" in latest_decision
        assert "signature:" in latest_decision
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_healthy_profile_can_noop(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        fixtures = {
            "lobby.yml": {"role": "lobby", "event_started": 3, "event_join_count": 12, "queue_size": 4, "player_density": 14, "network_routing_latency_ms": 10, "runtime_composite_pressure": 0.22},
            "rpg_world.yml": {"role": "progression", "dungeon_started": 20, "dungeon_completed": 15, "queue_size": 6, "player_density": 20, "network_routing_latency_ms": 12, "runtime_composite_pressure": 0.30},
            "dungeons.yml": {"role": "instance", "dungeon_started": 24, "dungeon_completed": 18, "event_started": 0, "event_join_count": 0, "queue_size": 3, "player_density": 18, "network_routing_latency_ms": 11, "runtime_composite_pressure": 0.28},
            "events.yml": {"role": "event", "event_started": 4, "event_join_count": 22, "queue_size": 4, "player_density": 16, "network_routing_latency_ms": 12, "runtime_composite_pressure": 0.24},
        }
        for name, payload in fixtures.items():
            payload.update(
                {
                    "runtime_knowledge_index": {"records": 5},
                    "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
                    "session_authority_service": {"split_brain_detections": 0},
                    "exploit_forensics_plane": {"incident_total": 0},
                    "experiment_registry": {"rollbacks": 0},
                    "policy_registry": {"rollbacks": 0},
                    "economy_item_authority_plane": {"quarantined_items": 0},
                }
            )
            (status_dir / name).write_text(dump_yaml(payload), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        assert "MODE=noop" in result.stdout
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_marks_final_threshold_ready_after_steady_noop_streak(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        fixtures = {
            "lobby.yml": {"role": "lobby", "event_started": 3, "event_join_count": 12, "queue_size": 4, "player_density": 14, "network_routing_latency_ms": 10, "runtime_composite_pressure": 0.22},
            "rpg_world.yml": {"role": "progression", "dungeon_started": 20, "dungeon_completed": 15, "queue_size": 6, "player_density": 20, "network_routing_latency_ms": 12, "runtime_composite_pressure": 0.30},
            "dungeons.yml": {"role": "instance", "dungeon_started": 24, "dungeon_completed": 18, "event_started": 0, "event_join_count": 0, "queue_size": 3, "player_density": 18, "network_routing_latency_ms": 11, "runtime_composite_pressure": 0.28},
            "events.yml": {"role": "event", "event_started": 4, "event_join_count": 22, "queue_size": 4, "player_density": 16, "network_routing_latency_ms": 12, "runtime_composite_pressure": 0.24},
        }
        for name, payload in fixtures.items():
            payload.update(
                {
                    "runtime_knowledge_index": {"records": 5},
                    "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
                    "session_authority_service": {"split_brain_detections": 0},
                    "exploit_forensics_plane": {"incident_total": 0},
                    "experiment_registry": {"rollbacks": 0},
                    "policy_registry": {"rollbacks": 0},
                    "economy_item_authority_plane": {"quarantined_items": 0},
                }
            )
            (status_dir / name).write_text(dump_yaml(payload), encoding="utf-8")
        autonomy = load_yaml("configs/autonomy.yml")
        autonomy["final_threshold"]["required_steady_noop_streak"] = 3
        autonomy["final_threshold"]["operational_steady_streak"] = 2
        autonomy["final_threshold"]["autonomy_steady_streak"] = 3
        (ROOT / "configs" / "autonomy.yml").write_text(dump_yaml(autonomy, sort_keys=False), encoding="utf-8")

        for _ in range(3):
            result = subprocess.run(
                [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            assert "MODE=noop" in result.stdout
            assert "REGIME=steady" in result.stdout

        control_state = yaml.safe_load((ROOT / "runtime_data" / "autonomy" / "control" / "state.yml").read_text(encoding="utf-8"))
        assert control_state["steady_noop_streak"] >= 3
        assert control_state["final_threshold_ready"] is True
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_tightens_economy_controls_on_inflation(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        fixtures = {
            "lobby.yml": {"role": "lobby", "economy_earn": 1200, "economy_spend": 300, "event_started": 2, "event_join_count": 8, "queue_size": 8, "player_density": 24, "network_routing_latency_ms": 18, "runtime_composite_pressure": 0.42},
            "rpg_world.yml": {"role": "progression", "economy_earn": 5400, "economy_spend": 1200, "dungeon_started": 18, "dungeon_completed": 12, "queue_size": 8, "player_density": 28, "network_routing_latency_ms": 20, "runtime_composite_pressure": 0.46},
            "dungeons.yml": {"role": "instance", "economy_earn": 6200, "economy_spend": 1400, "dungeon_started": 22, "dungeon_completed": 14, "queue_size": 0, "player_density": 24, "network_routing_latency_ms": 18, "runtime_composite_pressure": 0.48},
            "boss_world.yml": {"role": "boss", "economy_earn": 2400, "economy_spend": 500, "boss_killed": 3, "queue_size": 4, "player_density": 14, "network_routing_latency_ms": 12, "runtime_composite_pressure": 0.31},
            "events.yml": {"role": "event", "economy_earn": 3600, "economy_spend": 800, "event_started": 4, "event_join_count": 28, "queue_size": 6, "player_density": 26, "network_routing_latency_ms": 15, "runtime_composite_pressure": 0.39},
        }
        for name, payload in fixtures.items():
            payload.update(
                {
                    "runtime_knowledge_index": {"records": 5},
                    "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
                    "session_authority_service": {"split_brain_detections": 0},
                    "exploit_forensics_plane": {"incident_total": 0},
                    "experiment_registry": {"rollbacks": 0},
                    "policy_registry": {"rollbacks": 0},
                    "economy_item_authority_plane": {"quarantined_items": 0},
                }
            )
            (status_dir / name).write_text(dump_yaml(payload), encoding="utf-8")

        before_economy = load_yaml("configs/economy.yml")
        before_monitor = load_yaml("configs/runtime_monitor.yml")
        before_economy["market_tax"] = 0.1
        before_monitor["exploit_detection"]["abnormal_currency_gain"] = 2000
        (ROOT / "configs" / "economy.yml").write_text(dump_yaml(before_economy, sort_keys=False), encoding="utf-8")
        (ROOT / "configs" / "runtime_monitor.yml").write_text(dump_yaml(before_monitor, sort_keys=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        after_economy = load_yaml("configs/economy.yml")
        after_monitor = load_yaml("configs/runtime_monitor.yml")

        assert "MODE=apply" in result.stdout
        assert after_economy["market_tax"] > before_economy["market_tax"]
        assert after_monitor["exploit_detection"]["abnormal_currency_gain"] < before_monitor["exploit_detection"]["abnormal_currency_gain"]
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_holds_then_promotes_active_soak(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        status = {
            "dungeon_started": 20,
            "dungeon_completed": 6,
            "event_started": 4,
            "event_join_count": 8,
            "queue_size": 42,
            "player_density": 78,
            "network_routing_latency_ms": 110,
            "runtime_composite_pressure": 0.81,
            "runtime_knowledge_index": {"records": 9},
            "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
            "session_authority_service": {"split_brain_detections": 0},
            "exploit_forensics_plane": {"incident_total": 0},
            "experiment_registry": {"rollbacks": 0},
            "policy_registry": {"rollbacks": 0},
            "economy_item_authority_plane": {"quarantined_items": 0},
        }
        (status_dir / "soak.yml").write_text(dump_yaml(status), encoding="utf-8")

        subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        hold = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        promote = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        control_state_text = (ROOT / "runtime_data" / "autonomy" / "control" / "state.yml").read_text(encoding="utf-8")
        assert "MODE=hold" in hold.stdout
        assert "MODE=promote" in promote.stdout
        assert "active_soak: {}" in control_state_text
        assert "resolution: promote" in control_state_text
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_rejects_regressed_soak_and_reverts_thresholds(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        _reset_autonomy_surface()
        status_dir = _reset_status_dir()
        applied_status = {
            "dungeon_started": 20,
            "dungeon_completed": 6,
            "event_started": 4,
            "event_join_count": 8,
            "queue_size": 42,
            "player_density": 78,
            "network_routing_latency_ms": 110,
            "runtime_composite_pressure": 0.81,
            "runtime_knowledge_index": {"records": 9},
            "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
            "session_authority_service": {"split_brain_detections": 0},
            "exploit_forensics_plane": {"incident_total": 0},
            "experiment_registry": {"rollbacks": 0},
            "policy_registry": {"rollbacks": 0},
            "economy_item_authority_plane": {"quarantined_items": 0},
        }
        target = status_dir / "reject.yml"
        target.write_text(dump_yaml(applied_status), encoding="utf-8")

        before_pressure = load_yaml("configs/pressure.yml")
        subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        regressed = dict(applied_status)
        regressed["runtime_composite_pressure"] = 0.97
        regressed["dungeon_completed"] = 2
        regressed["event_join_count"] = 2
        regressed["queue_size"] = 58
        target.write_text(dump_yaml(regressed), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        after_pressure = load_yaml("configs/pressure.yml")
        control_state_text = (ROOT / "runtime_data" / "autonomy" / "control" / "state.yml").read_text(encoding="utf-8")
        assert result.returncode == 1
        assert "MODE=reject" in result.stdout
        assert after_pressure["controls"]["queue_admission_threshold"] == before_pressure["controls"]["queue_admission_threshold"]
        assert after_pressure["controls"]["noncritical_spawn_suppression_threshold"] == before_pressure["controls"]["noncritical_spawn_suppression_threshold"]
        assert "active_soak: {}" in control_state_text
        assert "resolution: reject" in control_state_text
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)


def test_autonomous_quality_loop_tightens_exploit_controls(tmp_path: Path):
    runtime_backup = _backup_runtime(tmp_path)
    config_backup = _backup_configs(tmp_path)
    try:
        status_dir = ROOT / "runtime_data" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        fixtures = {
            "lobby.yml": {"role": "lobby", "event_started": 1, "event_join_count": 4, "queue_size": 12, "player_density": 30, "network_routing_latency_ms": 32, "runtime_composite_pressure": 0.52, "exploit_flag": 2},
            "rpg_world.yml": {"role": "progression", "dungeon_started": 12, "dungeon_completed": 8, "economy_earn": 2800, "economy_spend": 1000, "queue_size": 14, "player_density": 34, "network_routing_latency_ms": 40, "runtime_composite_pressure": 0.57, "exploit_flag": 3},
            "dungeons.yml": {"role": "instance", "dungeon_started": 16, "dungeon_completed": 9, "economy_earn": 2600, "economy_spend": 1200, "queue_size": 0, "player_density": 28, "network_routing_latency_ms": 38, "runtime_composite_pressure": 0.62, "exploit_flag": 4},
            "boss_world.yml": {"role": "boss", "boss_killed": 1, "economy_earn": 1200, "economy_spend": 400, "queue_size": 6, "player_density": 18, "network_routing_latency_ms": 25, "runtime_composite_pressure": 0.41, "exploit_flag": 2},
            "events.yml": {"role": "event", "event_started": 3, "event_join_count": 10, "economy_earn": 2200, "economy_spend": 700, "queue_size": 10, "player_density": 24, "network_routing_latency_ms": 28, "runtime_composite_pressure": 0.49, "exploit_flag": 3},
        }
        for name, payload in fixtures.items():
            payload.update(
                {
                    "runtime_knowledge_index": {"records": 5},
                    "deterministic_transfer_service": {"lease_verification_failures": 0, "quarantines": 0},
                    "session_authority_service": {"split_brain_detections": 0},
                    "exploit_forensics_plane": {"incident_total": payload.get("exploit_flag", 0)},
                    "experiment_registry": {"rollbacks": 0},
                    "policy_registry": {"rollbacks": 0},
                    "economy_item_authority_plane": {"quarantined_items": 0},
                }
            )
            (status_dir / name).write_text(dump_yaml(payload), encoding="utf-8")

        before_monitor = load_yaml("configs/runtime_monitor.yml")
        before_monitor["exploit_detection"]["duplicate_reward_spike"] = 4
        before_monitor["exploit_detection"]["abnormal_currency_gain"] = 2000
        (ROOT / "configs" / "runtime_monitor.yml").write_text(dump_yaml(before_monitor, sort_keys=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "autonomous_quality_loop.py"), "--ignore-cooldown"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        after_monitor = load_yaml("configs/runtime_monitor.yml")

        assert "MODE=apply" in result.stdout
        assert after_monitor["exploit_detection"]["duplicate_reward_spike"] < before_monitor["exploit_detection"]["duplicate_reward_spike"]
        assert after_monitor["exploit_detection"]["abnormal_currency_gain"] < before_monitor["exploit_detection"]["abnormal_currency_gain"]
    finally:
        _restore_runtime(runtime_backup)
        _restore_configs(config_backup)

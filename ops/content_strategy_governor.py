#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
CONTENT_DIR = RUNTIME / "content_pipeline"
SUMMARY_PATH = AUTONOMY / "content_governor_summary.yml"
STRATEGY_PATH = AUTONOMY / "content_strategy_summary.yml"
ECONOMY_SUMMARY_PATH = AUTONOMY / "economy_governor_summary.yml"
ANTI_CHEAT_SUMMARY_PATH = AUTONOMY / "anti_cheat_governor_summary.yml"
LIVEOPS_SUMMARY_PATH = AUTONOMY / "liveops_governor_summary.yml"
PLAYER_EXPERIENCE_SUMMARY_PATH = AUTONOMY / "player_experience_summary.yml"
FATIGUE_SUMMARY_PATH = AUTONOMY / "engagement_fatigue_summary.yml"
CONTENT_VOLUME_SUMMARY_PATH = AUTONOMY / "content_volume_summary.yml"
PLAN_DIR = RUNTIME / "content_strategy"
LEDGER_PATH = CONTENT_DIR / "ledger.jsonl"
STATUS_DIR = RUNTIME / "status"

TARGET_FAMILIES = [
    "onboarding",
    "quest",
    "quest_chain",
    "dungeon",
    "dungeon_variation",
    "event",
    "season",
    "social",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def load_ledger() -> list[dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with LEDGER_PATH.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return rows


def summarize_runtime_feedback() -> dict[str, float]:
    queue_total = 0
    player_density_total = 0
    event_join_total = 0
    return_player_reward_total = 0
    exploit_flag_total = 0
    server_count = 0
    for status_path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(status_path)
        server_count += 1
        queue_total += int(payload.get("queue_size", 0))
        player_density_total += int(payload.get("player_density", 0))
        event_join_total += int(payload.get("event_join_count", 0))
        return_player_reward_total += int(payload.get("return_player_reward", 0))
        exploit_flag_total += int(payload.get("exploit_flag", 0))
    divisor = max(1, server_count)
    return {
        "queue_avg": round(queue_total / divisor, 2),
        "player_density_avg": round(player_density_total / divisor, 2),
        "event_join_avg": round(event_join_total / divisor, 2),
        "return_player_reward_avg": round(return_player_reward_total / divisor, 2),
        "exploit_flag_total": float(exploit_flag_total),
    }


def main() -> int:
    created_at = now_iso()
    summary = load_yaml(SUMMARY_PATH)
    economy = load_yaml(ECONOMY_SUMMARY_PATH)
    anti_cheat = load_yaml(ANTI_CHEAT_SUMMARY_PATH)
    liveops = load_yaml(LIVEOPS_SUMMARY_PATH)
    player_experience = load_yaml(PLAYER_EXPERIENCE_SUMMARY_PATH)
    fatigue = load_yaml(FATIGUE_SUMMARY_PATH)
    content_volume = load_yaml(CONTENT_VOLUME_SUMMARY_PATH)
    runtime_feedback = summarize_runtime_feedback()
    ledger = load_ledger()
    by_type = summary.get("by_type", {}) or {}
    promoted_by_type: dict[str, int] = {}
    held_by_type: dict[str, int] = {}
    for row in ledger[-128:]:
        artifact_type = str(row.get("artifact_type", ""))
        verdict = str(row.get("verdict", ""))
        if verdict == "promote":
            promoted_by_type[artifact_type] = promoted_by_type.get(artifact_type, 0) + 1
        elif verdict == "hold":
            held_by_type[artifact_type] = held_by_type.get(artifact_type, 0) + 1

    expansion_candidates: list[dict[str, Any]] = []
    avg_depth = float(summary.get("average_depth_score", 0.0))
    avg_retention = float(summary.get("average_retention_proxy", 0.0))
    avg_quality = float(summary.get("average_quality_score", 0.0))
    first_loop_coverage = float(summary.get("first_loop_coverage_score", 0.0))
    social_loop_density = float(summary.get("social_loop_density", 0.0))
    event_join_avg = float(runtime_feedback["event_join_avg"])
    return_player_reward_avg = float(runtime_feedback["return_player_reward_avg"])
    queue_avg = float(runtime_feedback["queue_avg"])
    exploit_flag_total = float(runtime_feedback["exploit_flag_total"])
    inflation_ratio = float(economy.get("inflation_ratio", 1.0))
    held_liveops = int(liveops.get("held_actions", 0))
    sandbox_cases = int(anti_cheat.get("sandbox_cases", 0))
    anti_cheat_mode = str(anti_cheat.get("mode", ""))
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_state = str(player_experience.get("experience_state", ""))
    trust_pull = float(player_experience.get("trust_pull", 0.0))
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 0.0))
    thinness_score = float(fatigue.get("thinness_score", 0.0))
    repetition_score = float(fatigue.get("repetition_score", 0.0))
    novelty_gap_score = float(fatigue.get("novelty_gap_score", 0.0))
    content_volume_score = float(content_volume.get("content_volume_score", 0.0))
    content_volume_state = str(content_volume.get("content_volume_state", ""))
    for family in TARGET_FAMILIES:
        generated = int(by_type.get(family, 0))
        promoted = int(promoted_by_type.get(family, 0))
        held = int(held_by_type.get(family, 0))
        hold_pressure = round(held / max(1, generated), 2)
        coverage_gap = 1 if generated == 0 else 0
        leverage = (1.8 if coverage_gap else 0.7) + hold_pressure + (0.5 if family in {"quest_chain", "dungeon_variation", "season", "social"} else 0.0)
        if family == "social":
            leverage += 0.5 if return_player_reward_avg < 80 else 0.1
            leverage += 0.6 if experience_percent < 40 else 0.1
            leverage += 0.4 if social_loop_density < 2.0 else 0.1
            leverage += 0.5 if novelty_gap_score > 0.35 else 0.0
        if family == "event":
            leverage += 0.5 if event_join_avg < 900 else 0.1
            leverage += 0.6 if experience_percent < 40 else 0.1
            leverage += 0.4 if repetition_score > 0.4 else 0.0
        if family == "onboarding":
            leverage += 0.4 if queue_avg > 4.5 else 0.1
            leverage += 0.8 if experience_state in {"early", "mid"} else 0.1
            leverage += 0.5 if first_loop_coverage < 2.2 else 0.1
            leverage += 0.4 if thinness_score > 0.35 else 0.0
        if family == "season":
            leverage += 0.4 if held_liveops > 0 else 0.1
            leverage += 0.5 if novelty_gap_score > 0.35 else 0.0
        if family in {"quest", "quest_chain"}:
            leverage += 0.4 if inflation_ratio < 1.0 else 0.1
        if family in {"dungeon", "dungeon_variation"}:
            leverage += 0.4 if sandbox_cases == 0 else 0.1
            leverage += 0.4 if trust_pull < 0.7 else 0.1
        if exploit_flag_total > 0 and family in {"social", "event"}:
            leverage -= 0.3
        leverage = round(leverage, 2)
        if coverage_gap:
            reason = "missing family coverage"
        elif family == "social" and return_player_reward_avg < 80:
            reason = "return-player engagement is weak"
        elif family == "event" and event_join_avg < 900:
            reason = "event join average is below replay target"
        elif family == "onboarding" and queue_avg > 4.5:
            reason = "queue pressure suggests onboarding friction"
        elif family == "season" and held_liveops > 0:
            reason = "live-ops hold pressure needs season framing"
        else:
            reason = "high hold pressure or high replay leverage"
        expansion_candidates.append(
            {
                "family": family,
                "generated": generated,
                "promoted": promoted,
                "held": held,
                "hold_pressure": hold_pressure,
                "coverage_gap": coverage_gap,
                "leverage_score": leverage,
                "reason": reason,
            }
        )

    ranked = sorted(expansion_candidates, key=lambda item: (-item["leverage_score"], -item["coverage_gap"], -item["held"], item["family"]))
    next_focus = [item["family"] for item in ranked[:3]]
    repair_jobs = []
    if avg_depth < 2.1:
        repair_jobs.append("content_governor")
    if first_loop_coverage < 2.2 and "content_governor" not in repair_jobs:
        repair_jobs.append("content_governor")
    if avg_retention < 1.7:
        repair_jobs.append("liveops_governor")
    if avg_quality < 8.2:
        repair_jobs.append("economy_governor")
    if event_join_avg < 900 and "liveops_governor" not in repair_jobs:
        repair_jobs.append("liveops_governor")
    if sandbox_cases > 0 and anti_cheat_mode != "observe_and_replay" and "anti_cheat_governor" not in repair_jobs:
        repair_jobs.append("anti_cheat_governor")
    if trust_pull < 0.7 and "anti_cheat_governor" not in repair_jobs:
        repair_jobs.append("anti_cheat_governor")
    if experience_percent < 47 and experience_state != "advanced" and "player_experience_governor" not in repair_jobs:
        repair_jobs.append("player_experience_governor")
    if fatigue_gap_score >= 0.35 and "content_governor" not in repair_jobs:
        repair_jobs.append("content_governor")
    if content_volume_score < 7.5 and "content_governor" not in repair_jobs:
        repair_jobs.append("content_governor")
    if fatigue_gap_score >= 0.38 and "player_experience_governor" not in repair_jobs:
        repair_jobs.append("player_experience_governor")

    detailed_payload = {
        "created_at": created_at,
        "next_focus_families": next_focus,
        "average_depth_score": avg_depth,
        "average_retention_proxy": avg_retention,
        "average_quality_score": avg_quality,
        "first_loop_coverage_score": first_loop_coverage,
        "social_loop_density": social_loop_density,
        "runtime_feedback": runtime_feedback,
        "economy_inflation_ratio": inflation_ratio,
        "anti_cheat_sandbox_cases": sandbox_cases,
        "liveops_held_actions": held_liveops,
        "estimated_completeness_percent": experience_percent,
        "experience_state": experience_state,
        "trust_pull": trust_pull,
        "thinness_score": thinness_score,
        "repetition_score": repetition_score,
        "novelty_gap_score": novelty_gap_score,
        "fatigue_gap_score": fatigue_gap_score,
        "content_volume_score": content_volume_score,
        "content_volume_state": content_volume_state,
        "recommended_repairs": repair_jobs,
        "expansion_candidates": ranked,
    }
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    (PLAN_DIR / f"{created_at.replace(':', '').replace('-', '')}_content_strategy.json").write_text(
        json.dumps(detailed_payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_payload = {
        "created_at": created_at,
        "next_focus_csv": ",".join(next_focus),
        "recommended_repairs_csv": ",".join(repair_jobs),
        "recommended_repairs_count": len(repair_jobs),
        "top_focus_family": next_focus[0] if next_focus else "",
        "average_depth_score": avg_depth,
        "average_retention_proxy": avg_retention,
        "average_quality_score": avg_quality,
        "first_loop_coverage_score": first_loop_coverage,
        "social_loop_density": social_loop_density,
        "runtime_queue_avg": queue_avg,
        "runtime_event_join_avg": event_join_avg,
        "runtime_return_player_reward_avg": return_player_reward_avg,
        "runtime_exploit_flag_total": exploit_flag_total,
        "estimated_completeness_percent": experience_percent,
        "experience_state": experience_state,
        "trust_pull": trust_pull,
        "fatigue_gap_score": fatigue_gap_score,
        "fatigue_state": str(fatigue.get("fatigue_state", "")),
        "content_volume_score": content_volume_score,
        "content_volume_state": content_volume_state,
        "candidate_count": len(ranked),
    }
    write_yaml(STRATEGY_PATH, summary_payload)
    print("CONTENT_STRATEGY_GOVERNOR")
    print(f"NEXT_FOCUS={','.join(next_focus)}")
    print(f"RECOMMENDED_REPAIRS={len(repair_jobs)}")
    print(f"AVERAGE_DEPTH_SCORE={avg_depth}")
    print(f"AVERAGE_RETENTION_PROXY={avg_retention}")
    print(f"RUNTIME_EVENT_JOIN_AVG={event_join_avg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

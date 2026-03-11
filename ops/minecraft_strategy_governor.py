#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
AUTONOMY = RUNTIME / "autonomy"
SUMMARY_PATH = AUTONOMY / "minecraft_strategy_summary.yml"
PLAN_DIR = RUNTIME / "minecraft_strategy"


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


def main() -> int:
    created_at = now_iso()
    content = load_yaml(AUTONOMY / "content_governor_summary.yml")
    content_strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    content_soak = load_yaml(AUTONOMY / "content_soak_summary.yml")
    economy = load_yaml(AUTONOMY / "economy_governor_summary.yml")
    anti_cheat = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    minecraft_bundle = load_yaml(AUTONOMY / "minecraft_bundle_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    player_experience_soak = load_yaml(AUTONOMY / "player_experience_soak_summary.yml")
    gameplay_progression = load_yaml(AUTONOMY / "gameplay_progression_summary.yml")
    engagement_fatigue = load_yaml(AUTONOMY / "engagement_fatigue_summary.yml")

    avg_depth = float(content.get("average_depth_score", 0.0))
    event_join_avg = float(content_strategy.get("runtime_event_join_avg", 0.0))
    return_player_reward_avg = float(content_strategy.get("runtime_return_player_reward_avg", 0.0))
    inflation_ratio = float(economy.get("inflation_ratio", 0.0))
    sandbox_cases = int(anti_cheat.get("sandbox_cases", 0))
    anti_cheat_mode = str(anti_cheat.get("mode", ""))
    progression_protection_score = float(anti_cheat.get("progression_protection_score", 0.0))
    held_actions = int(liveops.get("held_actions", 0))
    content_soak_state = str(content_soak.get("content_soak_state", ""))
    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    experience_soak_state = str(player_experience_soak.get("player_experience_soak_state", ""))
    progression_total_score = float(gameplay_progression.get("progression_total_score", 0.0))
    fatigue_gap_score = float(engagement_fatigue.get("fatigue_gap_score", 0.0))
    fatigue_state = str(engagement_fatigue.get("fatigue_state", ""))

    candidates = [
        {
            "domain": "gameplay_progression",
            "priority_score": round((2.2 - avg_depth) + (0.4 if content_soak_state != "stable" else 0.0) + (0.5 if experience_percent < 45 else 0.0) + (0.6 if progression_total_score < 9.0 else 0.0) + (0.4 if fatigue_gap_score >= 0.45 else 0.0), 2),
            "reason": f"avg_depth={avg_depth} content_soak_state={content_soak_state} experience_percent={experience_percent} progression_total_score={progression_total_score} fatigue_gap_score={fatigue_gap_score}",
            "repairs": ["content_governor", "player_experience_governor", "player_experience_soak_governor"] if (avg_depth < 1.85 or experience_percent < 50 or progression_total_score < 10.5 or fatigue_gap_score >= 0.38) else [],
        },
        {
            "domain": "economy_market",
            "priority_score": round(abs(1.0 - inflation_ratio) + (0.4 if return_player_reward_avg < 60 else 0.0), 2),
            "reason": f"inflation_ratio={inflation_ratio} return_player_reward_avg={return_player_reward_avg}",
            "repairs": ["economy_governor"] if abs(1.0 - inflation_ratio) >= 0.1 or return_player_reward_avg < 60 else [],
        },
        {
            "domain": "social_liveops",
            "priority_score": round((0.8 if event_join_avg < 950 else 0.0) + (0.6 if held_actions > 0 else 0.0) + (0.4 if return_player_reward_avg < 80 else 0.0) + (0.7 if experience_percent < 45 else 0.0) + (0.4 if experience_soak_state == "tune" else 0.0) + (0.6 if fatigue_gap_score >= 0.45 else 0.0), 2),
            "reason": f"event_join_avg={event_join_avg} held_actions={held_actions} return_player_reward_avg={return_player_reward_avg} experience_percent={experience_percent} experience_soak_state={experience_soak_state} fatigue_state={fatigue_state}",
            "repairs": ["liveops_governor", "content_governor", "player_experience_governor", "player_experience_soak_governor"],
        },
        {
            "domain": "anti_cheat_recovery",
            "priority_score": round((0.7 if sandbox_cases > 0 and anti_cheat_mode != 'observe_and_replay' else 0.0) + (0.4 if progression_protection_score < 0.9 else 0.0) + (0.3 if content_soak_state == 'tune' else 0.0), 2),
            "reason": f"sandbox_cases={sandbox_cases} anti_cheat_mode={anti_cheat_mode} progression_protection_score={progression_protection_score} content_soak_state={content_soak_state}",
            "repairs": ["anti_cheat_governor"] if anti_cheat_mode != "observe_and_replay" or progression_protection_score < 0.9 else [],
        },
        {
            "domain": "governance_autonomy",
            "priority_score": 0.0 if str(minecraft_bundle.get("governance_autonomy_bundle_state", "")) == "complete" else 1.0,
            "reason": f"governance_autonomy_bundle_state={minecraft_bundle.get('governance_autonomy_bundle_state', '')}",
            "repairs": ["minecraft_bundle_governor", "repo_bundle_governor"],
        },
    ]

    ranked = sorted(candidates, key=lambda item: (-item["priority_score"], item["domain"]))
    next_focus = [item["domain"] for item in ranked if item["priority_score"] > 0][:3]
    recommended_repairs: list[str] = []
    for item in ranked[:3]:
        if item["priority_score"] <= 0.2:
            continue
        for repair in item["repairs"]:
            if repair not in recommended_repairs:
                recommended_repairs.append(repair)

    payload = {
        "created_at": created_at,
        "next_focus_domains": next_focus,
        "recommended_repairs": recommended_repairs,
        "candidates": ranked,
        "signals": {
            "average_depth_score": avg_depth,
            "runtime_event_join_avg": event_join_avg,
            "runtime_return_player_reward_avg": return_player_reward_avg,
            "inflation_ratio": inflation_ratio,
            "sandbox_cases": sandbox_cases,
            "held_actions": held_actions,
            "content_soak_state": content_soak_state,
            "estimated_completeness_percent": experience_percent,
            "experience_state": str(player_experience.get("experience_state", "")),
            "player_experience_soak_state": experience_soak_state,
            "progression_total_score": progression_total_score,
            "fatigue_gap_score": fatigue_gap_score,
            "fatigue_state": fatigue_state,
        },
    }
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    (PLAN_DIR / f"{created_at.replace(':', '').replace('-', '')}_minecraft_strategy.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "created_at": created_at,
        "next_focus_csv": ",".join(next_focus),
        "recommended_repairs_csv": ",".join(recommended_repairs),
        "recommended_repairs_count": len(recommended_repairs),
        "top_focus_domain": next_focus[0] if next_focus else "",
        "average_depth_score": avg_depth,
        "runtime_event_join_avg": event_join_avg,
        "runtime_return_player_reward_avg": return_player_reward_avg,
        "inflation_ratio": inflation_ratio,
        "sandbox_cases": sandbox_cases,
        "content_soak_state": content_soak_state,
        "candidate_count": len(ranked),
        "estimated_completeness_percent": experience_percent,
        "experience_state": str(player_experience.get("experience_state", "")),
        "player_experience_soak_state": experience_soak_state,
        "progression_total_score": progression_total_score,
        "fatigue_gap_score": fatigue_gap_score,
        "fatigue_state": fatigue_state,
    }
    write_yaml(SUMMARY_PATH, summary)
    print("MINECRAFT_STRATEGY_GOVERNOR")
    print(f"NEXT_FOCUS={summary['next_focus_csv']}")
    print(f"RECOMMENDED_REPAIRS={summary['recommended_repairs_count']}")
    print(f"TOP_FOCUS_DOMAIN={summary['top_focus_domain']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

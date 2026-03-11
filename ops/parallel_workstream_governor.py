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
PARALLEL_DIR = AUTONOMY / "parallel"
PACKETS_DIR = PARALLEL_DIR / "packets"
SUMMARY_PATH = PARALLEL_DIR / "parallel_assignments.yml"


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def to_float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    return float(payload.get(key, default) or default)


def to_int(payload: dict[str, Any], key: str, default: int = 0) -> int:
    return int(payload.get(key, default) or default)


def packet_text(
    lane: str,
    objective: str,
    why_now: str,
    success_signals: list[str],
    primary_commands: list[str],
    do_not_do: list[str],
    context: dict[str, Any],
) -> str:
    lines = [
        f"# {lane}",
        "",
        f"Objective: {objective}",
        "",
        f"Why now: {why_now}",
        "",
        "Current context:",
    ]
    for key, value in context.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Success signals:"])
    for item in success_signals:
        lines.append(f"- {item}")
    lines.extend(["", "Primary commands:"])
    for item in primary_commands:
        lines.append(f"- `{item}`")
    lines.extend(["", "Do not do:"])
    for item in do_not_do:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Delivery rule:",
            "- Keep MetaOS constraints above Minecraft convenience.",
            "- Preserve append-only truth, lineage, replayability, and fail-closed behavior.",
            "- Prefer canonical surfaces, metrics, tests, and summary wiring over ad hoc outputs.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    created_at = now_iso()
    runtime_summary = load_yaml(AUTONOMY / "runtime_summary_cache.yml")
    if not runtime_summary:
        runtime_summary = {}
    content = load_yaml(AUTONOMY / "content_governor_summary.yml")
    strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    anti_cheat = load_yaml(AUTONOMY / "anti_cheat_governor_summary.yml")
    economy_market = load_yaml(AUTONOMY / "economy_market_summary.yml")
    fatigue = load_yaml(AUTONOMY / "engagement_fatigue_summary.yml")
    player_experience = load_yaml(AUTONOMY / "player_experience_summary.yml")
    final_eval = load_yaml(AUTONOMY / "final_threshold_eval.json")
    minecraft_bundle = load_yaml(AUTONOMY / "minecraft_bundle_summary.yml")
    repo_bundle = load_yaml(AUTONOMY / "repo_bundle_summary.yml")

    experience_percent = to_float(player_experience, "estimated_completeness_percent")
    fatigue_gap = to_float(fatigue, "fatigue_gap_score")
    event_join_avg = to_float(strategy, "runtime_event_join_avg")
    market_maturity = to_float(economy_market, "market_maturity_score")
    exploit_resilience = to_float(anti_cheat, "exploit_resilience_score")
    content_depth = to_float(content, "average_depth_score")
    content_quality = to_float(content, "average_quality_score")
    liveops_depth = to_float(liveops, "depth_strength")
    promoted_actions = to_int(liveops, "promoted_actions")
    minecraft_bundle_percent = to_float(minecraft_bundle, "bundle_completion_percent")
    repo_bundle_percent = to_float(repo_bundle, "bundle_completion_percent")
    human_lift = float(final_eval.get("quality_lift_if_human_intervenes", 0.0) or 0.0)

    assignments = [
        {
            "lane": "lane_01_content_density",
            "objective": "Increase absolute content density and progression breadth without regressing final-threshold stability.",
            "priority": 1,
            "why_now": f"Player experience is {experience_percent:.1f}% and content depth/quality are {content_depth:.2f}/{content_quality:.2f}.",
            "context": {
                "player_experience_percent": round(experience_percent, 1),
                "content_average_depth_score": round(content_depth, 2),
                "content_average_quality_score": round(content_quality, 2),
                "content_next_focus": strategy.get("next_focus_csv", ""),
            },
            "success_signals": [
                "Content governor raises generated/promoted counts without increasing held pressure.",
                "Content bundle stays complete.",
                "Player experience percent does not fall.",
            ],
            "primary_commands": [
                "python3 ops/content_governor.py",
                "python3 ops/content_strategy_governor.py",
                "python3 ops/content_bundle_governor.py",
            ],
            "do_not_do": [
                "Do not bypass hold/reject gates.",
                "Do not change canonical surfaces without wiring metrics and summary.",
            ],
        },
        {
            "lane": "lane_02_social_liveops_retention",
            "objective": "Increase returner retention, party stickiness, and social concurrency under stable soak.",
            "priority": 2,
            "why_now": f"Liveops depth is {liveops_depth:.2f} with {promoted_actions} promoted actions and event join avg {event_join_avg:.1f}.",
            "context": {
                "liveops_depth_strength": round(liveops_depth, 2),
                "liveops_promoted_actions": promoted_actions,
                "runtime_event_join_avg": round(event_join_avg, 1),
                "fatigue_gap_score": round(fatigue_gap, 2),
            },
            "success_signals": [
                "Liveops retains stable or higher promoted actions.",
                "Fatigue stays low.",
                "Minecraft soak remains stable.",
            ],
            "primary_commands": [
                "python3 ops/liveops_governor.py",
                "python3 ops/player_experience_governor.py",
                "python3 ops/player_experience_soak_governor.py",
            ],
            "do_not_do": [
                "Do not increase novelty by breaking replayability.",
                "Do not let repair counts climb above zero in stable state.",
            ],
        },
        {
            "lane": "lane_03_security_economy_hardening",
            "objective": "Tighten anti-cheat and market maturity so player trust stays maxed under load.",
            "priority": 3,
            "why_now": f"Exploit resilience is {exploit_resilience:.2f} and market maturity is {market_maturity:.2f}.",
            "context": {
                "anti_cheat_exploit_resilience_score": round(exploit_resilience, 2),
                "economy_market_maturity_score": round(market_maturity, 2),
                "final_threshold_human_lift": round(human_lift, 2),
            },
            "success_signals": [
                "Anti-cheat progression protection and exploit resilience stay at or near 1.0.",
                "Economy market maturity stays mature.",
                "Final threshold remains ready.",
            ],
            "primary_commands": [
                "python3 ops/anti_cheat_governor.py",
                "python3 ops/economy_governor.py",
                "python3 ops/economy_market_governor.py",
            ],
            "do_not_do": [
                "Do not trade exploit resilience for short-term reward inflation.",
                "Do not weaken fail-closed behavior.",
            ],
        },
        {
            "lane": "lane_04_scale_and_service_quality",
            "objective": "Improve service responsiveness, matchmaking clarity, and live-scale confidence as a single service-quality bundle.",
            "priority": 4,
            "why_now": "Large-server parity depends on responsiveness, fairness, and credible scale confidence moving together.",
            "context": {
                "minecraft_bundle_completion_percent": round(minecraft_bundle_percent, 1),
                "repo_bundle_completion_percent": round(repo_bundle_percent, 1),
                "player_experience_percent": round(experience_percent, 1),
            },
            "success_signals": [
                "Service responsiveness stays crisp.",
                "Matchmaking quality stays sharp or improves.",
                "Live scale confidence stays credible or moves toward broad.",
            ],
            "primary_commands": [
                "python3 ops/service_responsiveness_governor.py",
                "python3 ops/matchmaking_quality_governor.py",
                "python3 ops/live_scale_governor.py",
            ],
            "do_not_do": [
                "Do not optimize a single metric at the expense of bundle stability.",
                "Do not introduce non-deterministic state transitions.",
            ],
        },
        {
            "lane": "lane_05_threshold_and_canonical_integrity",
            "objective": "Keep final threshold, bundle governance, artifact canonicalization, and MetaOS conformance closed while other lanes move fast.",
            "priority": 5,
            "why_now": "Parallel work only helps if canonical operating truth stays coherent.",
            "context": {
                "final_threshold_ready": bool(final_eval.get("final_threshold_ready", False)),
                "failed_criteria_count": len(final_eval.get("failed_criteria", []) or []),
                "quality_lift_if_human_intervenes": round(human_lift, 2),
            },
            "success_signals": [
                "Final threshold stays ready with zero failed criteria.",
                "Artifact governor keeps canonical classes current.",
                "MetaOS conformance remains gap-free.",
            ],
            "primary_commands": [
                "python3 ops/artifact_governor.py",
                "python3 ops/metaos_conformance.py",
                "python3 ops/final_threshold_eval.py",
                "python3 ops/final_threshold_repair.py",
            ],
            "do_not_do": [
                "Do not let partial changes land without metrics, summary, and tests.",
                "Do not accept convenience over append-only truth or lineage preservation.",
            ],
        },
    ]

    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    for assignment in assignments:
        packet_path = PACKETS_DIR / f"{assignment['lane']}.md"
        assignment["packet_path"] = str(packet_path.relative_to(ROOT))
        write_text(
            packet_path,
            packet_text(
                lane=assignment["lane"],
                objective=assignment["objective"],
                why_now=assignment["why_now"],
                success_signals=assignment["success_signals"],
                primary_commands=assignment["primary_commands"],
                do_not_do=assignment["do_not_do"],
                context=assignment["context"],
            ),
        )

    summary = {
        "created_at": created_at,
        "server_completion_target": "hypixel_100_equivalent",
        "player_experience_percent": round(experience_percent, 1),
        "fatigue_gap_score": round(fatigue_gap, 2),
        "quality_lift_if_human_intervenes": round(human_lift, 2),
        "workstream_count": len(assignments),
        "workstreams": [
            {
                "lane": item["lane"],
                "priority": item["priority"],
                "objective": item["objective"],
                "packet_path": item["packet_path"],
            }
            for item in assignments
        ],
    }
    write_yaml(SUMMARY_PATH, summary)
    write_text(
        PARALLEL_DIR / "parallel_assignments.json",
        json.dumps(summary, ensure_ascii=True, indent=2) + "\n",
    )
    print("PARALLEL_WORKSTREAM_GOVERNOR")
    print(f"WORKSTREAM_COUNT={summary['workstream_count']}")
    print(f"PLAYER_EXPERIENCE_PERCENT={summary['player_experience_percent']}")
    print(f"QUALITY_LIFT_IF_HUMAN_INTERVENES={summary['quality_lift_if_human_intervenes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
STATUS_DIR = RUNTIME / "status"
SUMMARY_PATH = AUTONOMY / "community_identity_summary.yml"
OUTPUT_DIR = RUNTIME / "community_identity"


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def main() -> int:
    created_at = now_iso()
    content = load_yaml(AUTONOMY / "content_governor_summary.yml")
    liveops = load_yaml(AUTONOMY / "liveops_governor_summary.yml")
    fatigue = load_yaml(AUTONOMY / "engagement_fatigue_summary.yml")
    strategy = load_yaml(AUTONOMY / "content_strategy_summary.yml")

    totals = {
        "guild_created": 0.0,
        "guild_joined": 0.0,
        "rivalry_created": 0.0,
        "rivalry_match": 0.0,
        "rivalry_reward": 0.0,
        "event_join_count": 0.0,
        "status_files": 0.0,
    }
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1.0
        for key in totals:
            if key == "status_files":
                continue
            totals[key] += float(payload.get(key, 0) or 0)

    divisor = max(1.0, totals["status_files"])
    event_join_avg = totals["event_join_count"] / divisor
    social_persistence_strength = float(content.get("social_persistence_strength", 0.0))
    social_concurrency_strength = float(content.get("social_concurrency_strength", 0.0))
    rivalry_reward_pull = float(content.get("rivalry_reward_pull", 0.0))
    returner_retention_strength = float(content.get("returner_retention_strength", 0.0))
    cadence_diversity_score = float(liveops.get("cadence_diversity_score", 0.0))
    sustain_social = bool(liveops.get("sustain_social", False))
    party_concurrency_support = float(liveops.get("party_concurrency_support", 0.0))
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 1.0))

    guild_cohesion_score = round(
        clamp(
            totals["guild_joined"] / 8.0
            + totals["guild_created"] / 6.0
            + min(1.0, social_persistence_strength / 3.0) * 0.35
            + party_concurrency_support * 0.2
            + (0.1 if sustain_social else 0.0)
        ),
        2,
    )
    rivalry_identity_score = round(
        clamp(
            totals["rivalry_match"] / 10.0
            + totals["rivalry_created"] / 8.0
            + totals["rivalry_reward"] / 20.0
            + min(1.0, rivalry_reward_pull / 3.0) * 0.3
            + min(1.0, social_concurrency_strength / 3.0) * 0.2
        ),
        2,
    )
    community_identity_score = round(
        clamp(
            guild_cohesion_score * 0.35
            + rivalry_identity_score * 0.3
            + min(1.0, returner_retention_strength / 3.0) * 0.1
            + min(1.0, social_persistence_strength / 3.0) * 0.1
            + min(1.0, social_concurrency_strength / 3.0) * 0.08
            + cadence_diversity_score * 0.07
            + min(1.0, event_join_avg / 2500.0) * 0.08
            - fatigue_gap_score * 0.1
        ),
        2,
    )
    state = "magnetic" if community_identity_score >= 0.85 else "cohesive" if community_identity_score >= 0.6 else "forming"

    payload = {
        "created_at": created_at,
        "guild_created_total": int(totals["guild_created"]),
        "guild_joined_total": int(totals["guild_joined"]),
        "rivalry_created_total": int(totals["rivalry_created"]),
        "rivalry_match_total": int(totals["rivalry_match"]),
        "rivalry_reward_total": int(totals["rivalry_reward"]),
        "event_join_avg": round(event_join_avg, 2),
        "guild_cohesion_score": guild_cohesion_score,
        "rivalry_identity_score": rivalry_identity_score,
        "community_identity_score": community_identity_score,
        "community_identity_state": state,
        "content_next_focus": str(strategy.get("next_focus_csv", "")),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_community_identity.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("COMMUNITY_IDENTITY_GOVERNOR")
    print(f"COMMUNITY_IDENTITY_SCORE={community_identity_score}")
    print(f"COMMUNITY_IDENTITY_STATE={state}")
    print(f"GUILD_COHESION_SCORE={guild_cohesion_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

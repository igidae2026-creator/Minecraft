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
CONTENT_SUMMARY_PATH = AUTONOMY / "content_governor_summary.yml"
CONTENT_STRATEGY_PATH = AUTONOMY / "content_strategy_summary.yml"
SUMMARY_PATH = AUTONOMY / "content_volume_summary.yml"
OUTPUT_DIR = RUNTIME / "content_volume"

CORE_FAMILIES = [
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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> int:
    created_at = now_iso()
    content = load_yaml(CONTENT_SUMMARY_PATH)
    strategy = load_yaml(CONTENT_STRATEGY_PATH)

    by_type = content.get("by_type", {}) or {}
    generated = int(content.get("generated", 0))
    promoted = int(content.get("promoted", 0))
    player_facing_generated = int(content.get("player_facing_generated", 0))
    family_count = len(by_type)
    promoted_ratio = promoted / max(1, generated)
    core_family_coverage = sum(1 for family in CORE_FAMILIES if int(by_type.get(family, 0)) > 0)
    progression_span = int(by_type.get("quest_chain", 0)) + int(by_type.get("dungeon_variation", 0)) + int(by_type.get("season", 0))
    spectacle_density = int(by_type.get("event", 0)) + int(by_type.get("social", 0)) + int(by_type.get("onboarding", 0))
    queue_avg = float(strategy.get("runtime_queue_avg", 0.0))

    volume_score = round(
        clamp(
            (generated / 24.0) * 2.6
            + (promoted / 18.0) * 2.4
            + (player_facing_generated / 14.0) * 2.0
            + (core_family_coverage / len(CORE_FAMILIES)) * 1.4
            + (progression_span / 7.0) * 1.0
            + (spectacle_density / 11.0) * 0.9
            + promoted_ratio * 0.7
            - max(0.0, queue_avg - 6.0) * 0.08,
            0.0,
            10.0,
        ),
        2,
    )

    if volume_score >= 8.5 and core_family_coverage == len(CORE_FAMILIES):
        state = "mature"
    elif volume_score >= 5.5:
        state = "growing"
    else:
        state = "thin"

    payload = {
        "created_at": created_at,
        "generated": generated,
        "promoted": promoted,
        "player_facing_generated": player_facing_generated,
        "family_count": family_count,
        "core_family_coverage": core_family_coverage,
        "promoted_ratio": round(promoted_ratio, 2),
        "progression_span": progression_span,
        "spectacle_density": spectacle_density,
        "runtime_queue_avg": queue_avg,
        "content_volume_score": volume_score,
        "content_volume_state": state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_content_volume.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("CONTENT_VOLUME_GOVERNOR")
    print(f"CONTENT_VOLUME_SCORE={volume_score}")
    print(f"CONTENT_VOLUME_STATE={state}")
    print(f"CORE_FAMILY_COVERAGE={core_family_coverage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

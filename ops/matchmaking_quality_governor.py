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
SUMMARY_PATH = AUTONOMY / "matchmaking_quality_summary.yml"
OUTPUT_DIR = RUNTIME / "service_quality"


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
    totals = {
        "status_files": 0.0,
        "queue_size": 0.0,
        "player_density": 0.0,
        "routing_latency_ms": 0.0,
        "matchmaking_adjustment": 0.0,
        "guild_joined": 0.0,
        "rivalry_match": 0.0,
        "event_join_count": 0.0,
    }
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        totals["status_files"] += 1
        for key in totals:
            if key == "status_files":
                continue
            totals[key] += float(payload.get(key, 0) or 0)

    divisor = max(1.0, totals["status_files"])
    queue_avg = round(totals["queue_size"] / divisor, 2)
    density_avg = round(totals["player_density"] / divisor, 2)
    latency_avg = round(totals["routing_latency_ms"] / divisor, 2)
    event_join_avg = round(totals["event_join_count"] / divisor, 2)
    social_match_avg = round((totals["guild_joined"] + totals["rivalry_match"]) / divisor, 2)
    adjustment_avg = round(totals["matchmaking_adjustment"] / divisor, 2)

    queue_fairness_score = round(clamp(1.0 - max(0.0, queue_avg - 5.0) / 12.0, 0.0, 1.0), 2)
    routing_clarity_score = round(clamp(1.0 - max(0.0, latency_avg - 14.0) / 24.0, 0.0, 1.0), 2)
    density_match_score = round(clamp(1.0 - abs(density_avg - 22.0) / 20.0, 0.0, 1.0), 2)
    social_match_score = round(clamp((social_match_avg / 42.0) + (event_join_avg / 4200.0), 0.0, 1.0), 2)
    adjustment_confidence = round(clamp(adjustment_avg / 30.0, 0.0, 1.0), 2)
    matchmaking_quality_score = round(
        clamp(
            queue_fairness_score * 0.34
            + routing_clarity_score * 0.27
            + density_match_score * 0.16
            + social_match_score * 0.15
            + adjustment_confidence * 0.08,
            0.0,
            1.0,
        ),
        2,
    )
    if matchmaking_quality_score >= 0.85:
        matchmaking_state = "sharp"
    elif matchmaking_quality_score >= 0.65:
        matchmaking_state = "healthy"
    else:
        matchmaking_state = "uneven"

    payload = {
        "created_at": created_at,
        "queue_avg": queue_avg,
        "player_density_avg": density_avg,
        "latency_avg_ms": latency_avg,
        "event_join_avg": event_join_avg,
        "social_match_avg": social_match_avg,
        "matchmaking_adjustment_avg": adjustment_avg,
        "queue_fairness_score": queue_fairness_score,
        "routing_clarity_score": routing_clarity_score,
        "density_match_score": density_match_score,
        "social_match_score": social_match_score,
        "adjustment_confidence": adjustment_confidence,
        "matchmaking_quality_score": matchmaking_quality_score,
        "matchmaking_state": matchmaking_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_matchmaking_quality.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("MATCHMAKING_QUALITY_GOVERNOR")
    print(f"MATCHMAKING_QUALITY_SCORE={matchmaking_quality_score}")
    print(f"MATCHMAKING_STATE={matchmaking_state}")
    print(f"ROUTING_CLARITY_SCORE={routing_clarity_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

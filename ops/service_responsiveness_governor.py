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
SUMMARY_PATH = AUTONOMY / "service_responsiveness_summary.yml"
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
        "instance_spawn": 0.0,
        "instance_shutdown": 0.0,
        "event_join_count": 0.0,
        "adaptive_adjustment": 0.0,
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
    spawn_shutdown_balance = round(
        clamp(
            1.0 - abs(totals["instance_spawn"] - totals["instance_shutdown"]) / max(1.0, totals["instance_spawn"] + totals["instance_shutdown"]),
            0.0,
            1.0,
        ),
        2,
    )
    queue_immediacy_score = round(clamp(1.0 - max(0.0, queue_avg - 4.0) / 10.0, 0.0, 1.0), 2)
    latency_confidence = round(clamp(1.0 - max(0.0, latency_avg - 12.0) / 18.0, 0.0, 1.0), 2)
    density_balance_score = round(clamp(1.0 - abs(density_avg - 24.0) / 18.0, 0.0, 1.0), 2)
    event_flow_score = round(clamp(event_join_avg / 2600.0, 0.0, 1.0), 2)
    adaptive_responsiveness = round(clamp((totals["adaptive_adjustment"] / divisor) / 180.0, 0.0, 1.0), 2)
    responsiveness_score = round(
        clamp(
            queue_immediacy_score * 0.34
            + latency_confidence * 0.28
            + density_balance_score * 0.16
            + spawn_shutdown_balance * 0.12
            + event_flow_score * 0.05
            + adaptive_responsiveness * 0.05,
            0.0,
            1.0,
        ),
        2,
    )
    if responsiveness_score >= 0.85:
        responsiveness_state = "crisp"
    elif responsiveness_score >= 0.65:
        responsiveness_state = "steady"
    else:
        responsiveness_state = "strained"

    payload = {
        "created_at": created_at,
        "queue_avg": queue_avg,
        "player_density_avg": density_avg,
        "latency_avg_ms": latency_avg,
        "event_join_avg": event_join_avg,
        "queue_immediacy_score": queue_immediacy_score,
        "latency_confidence": latency_confidence,
        "density_balance_score": density_balance_score,
        "spawn_shutdown_balance": spawn_shutdown_balance,
        "adaptive_responsiveness": adaptive_responsiveness,
        "responsiveness_score": responsiveness_score,
        "responsiveness_state": responsiveness_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_service_responsiveness.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("SERVICE_RESPONSIVENESS_GOVERNOR")
    print(f"RESPONSIVENESS_SCORE={responsiveness_score}")
    print(f"RESPONSIVENESS_STATE={responsiveness_state}")
    print(f"QUEUE_IMMEDIACY_SCORE={queue_immediacy_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

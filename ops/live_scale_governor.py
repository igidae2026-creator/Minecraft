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
SUMMARY_PATH = AUTONOMY / "live_scale_summary.yml"
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
    player_densities: list[float] = []
    queue_sizes: list[float] = []
    event_joins: list[float] = []
    latencies: list[float] = []
    for path in sorted(STATUS_DIR.glob("*.yml")):
        payload = load_yaml(path)
        player_densities.append(float(payload.get("player_density", 0) or 0))
        queue_sizes.append(float(payload.get("queue_size", 0) or 0))
        event_joins.append(float(payload.get("event_join_count", 0) or 0))
        latencies.append(float(payload.get("network_routing_latency_ms", 0) or 0))

    server_count = max(1, len(player_densities))
    total_density = sum(player_densities)
    density_avg = round(total_density / server_count, 2)
    density_spread = round(max(player_densities) - min(player_densities), 2) if player_densities else 0.0
    queue_peak = round(max(queue_sizes), 2) if queue_sizes else 0.0
    event_peak = round(max(event_joins), 2) if event_joins else 0.0
    latency_peak = round(max(latencies), 2) if latencies else 0.0

    concurrent_load_score = round(clamp(total_density / 120.0 + event_peak / 6000.0, 0.0, 1.0), 2)
    density_spread_score = round(clamp(1.0 - density_spread / 32.0, 0.0, 1.0), 2)
    queue_peak_score = round(clamp(1.0 - max(0.0, queue_peak - 8.0) / 24.0, 0.0, 1.0), 2)
    latency_peak_score = round(clamp(1.0 - max(0.0, latency_peak - 18.0) / 24.0, 0.0, 1.0), 2)
    live_scale_confidence = round(
        clamp(
            concurrent_load_score * 0.34
            + density_spread_score * 0.24
            + queue_peak_score * 0.22
            + latency_peak_score * 0.2,
            0.0,
            1.0,
        ),
        2,
    )
    if live_scale_confidence >= 0.85:
        live_scale_state = "broad"
    elif live_scale_confidence >= 0.65:
        live_scale_state = "credible"
    else:
        live_scale_state = "narrow"

    payload = {
        "created_at": created_at,
        "server_count": server_count,
        "total_density": total_density,
        "density_avg": density_avg,
        "density_spread": density_spread,
        "queue_peak": queue_peak,
        "event_peak": event_peak,
        "latency_peak": latency_peak,
        "concurrent_load_score": concurrent_load_score,
        "density_spread_score": density_spread_score,
        "queue_peak_score": queue_peak_score,
        "latency_peak_score": latency_peak_score,
        "live_scale_confidence": live_scale_confidence,
        "live_scale_state": live_scale_state,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{created_at.replace(':', '').replace('-', '')}_live_scale.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("LIVE_SCALE_GOVERNOR")
    print(f"LIVE_SCALE_CONFIDENCE={live_scale_confidence}")
    print(f"LIVE_SCALE_STATE={live_scale_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

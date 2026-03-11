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
CONTROL_PATH = AUTONOMY / "control" / "state.yml"
CONTENT_SUMMARY_PATH = AUTONOMY / "content_governor_summary.yml"
CONTENT_STRATEGY_PATH = AUTONOMY / "content_strategy_summary.yml"
SUMMARY_PATH = AUTONOMY / "content_soak_summary.yml"
SOAK_DIR = RUNTIME / "content_soak"


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
    control = load_yaml(CONTROL_PATH)
    content = load_yaml(CONTENT_SUMMARY_PATH)
    strategy = load_yaml(CONTENT_STRATEGY_PATH)
    fatigue = load_yaml(AUTONOMY / "engagement_fatigue_summary.yml")
    steady_noop_streak = int(control.get("steady_noop_streak", 0))
    final_ready = bool(control.get("final_threshold_ready", False))
    active_soak = bool((control.get("active_soak", {}) or {}).get("decision_id", ""))
    avg_depth = float(content.get("average_depth_score", 0.0))
    avg_retention = float(content.get("average_retention_proxy", 0.0))
    avg_quality = float(content.get("average_quality_score", 0.0))
    recommended_repairs = int(strategy.get("recommended_repairs_count", 0))
    next_focus = str(strategy.get("next_focus_csv", ""))
    fatigue_gap_score = float(fatigue.get("fatigue_gap_score", 0.0))
    fatigue_state = str(fatigue.get("fatigue_state", ""))

    soak_state = "stable" if final_ready and not active_soak and steady_noop_streak >= 12 else "observe"
    if recommended_repairs > 0 or avg_depth < 2.0 or avg_retention < 1.7 or fatigue_gap_score > 0.35:
        soak_state = "tune"
    if active_soak:
        soak_state = "active"

    payload = {
        "created_at": created_at,
        "steady_noop_streak": steady_noop_streak,
        "final_threshold_ready": final_ready,
        "active_soak": active_soak,
        "content_average_depth_score": avg_depth,
        "content_average_retention_proxy": avg_retention,
        "content_average_quality_score": avg_quality,
        "content_next_focus_csv": next_focus,
        "recommended_repairs_count": recommended_repairs,
        "fatigue_gap_score": fatigue_gap_score,
        "fatigue_state": fatigue_state,
        "content_soak_state": soak_state,
    }
    SOAK_DIR.mkdir(parents=True, exist_ok=True)
    (SOAK_DIR / f"{created_at.replace(':', '').replace('-', '')}_content_soak.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_yaml(SUMMARY_PATH, payload)
    print("CONTENT_SOAK_GOVERNOR")
    print(f"CONTENT_SOAK_STATE={soak_state}")
    print(f"STEADY_NOOP_STREAK={steady_noop_streak}")
    print(f"RECOMMENDED_REPAIRS={recommended_repairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

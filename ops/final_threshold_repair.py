#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml

from autonomy_core import Job, JobQueue


ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "runtime_data" / "autonomy" / "final_threshold_eval.json"
CONTENT_STRATEGY_PATH = ROOT / "runtime_data" / "autonomy" / "content_strategy_summary.yml"
MINECRAFT_STRATEGY_PATH = ROOT / "runtime_data" / "autonomy" / "minecraft_strategy_summary.yml"
KNOWN_REPAIRS = {
    "validate_runtime_truth",
    "runtime_integrity",
    "reconcile_runtime",
    "autonomous_quality_loop",
    "artifact_governor",
    "metaos_conformance",
    "content_governor",
    "economy_governor",
    "anti_cheat_governor",
    "liveops_governor",
    "content_strategy_governor",
    "content_soak_governor",
    "content_bundle_governor",
    "repo_bundle_governor",
    "minecraft_bundle_governor",
    "minecraft_strategy_governor",
    "minecraft_soak_governor",
    "player_experience_governor",
    "player_experience_soak_governor",
    "engagement_fatigue_governor",
    "service_responsiveness_governor",
    "matchmaking_quality_governor",
    "runtime_summary",
}


def load_eval() -> dict[str, Any]:
    if not EVAL_PATH.exists():
        return {}
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> int:
    payload = load_eval()
    repairs = [repair for repair in payload.get("next_required_repairs", []) if repair in KNOWN_REPAIRS]
    strategy = load_yaml(CONTENT_STRATEGY_PATH)
    minecraft_strategy = load_yaml(MINECRAFT_STRATEGY_PATH)
    strategy_repairs = [item.strip() for item in str(strategy.get("recommended_repairs_csv", "")).split(",") if item.strip() in KNOWN_REPAIRS]
    for repair in strategy_repairs:
        if repair not in repairs:
            repairs.append(repair)
    minecraft_strategy_repairs = [item.strip() for item in str(minecraft_strategy.get("recommended_repairs_csv", "")).split(",") if item.strip() in KNOWN_REPAIRS]
    for repair in minecraft_strategy_repairs:
        if repair not in repairs:
            repairs.append(repair)
    queue = JobQueue()
    existing = set()
    for root in (queue.pending, queue.running):
        for path in root.glob("*.yml"):
            job = load_yaml(path)
            job_type = str(job.get("job_type", ""))
            if job_type:
                existing.add(job_type)
    enqueued = 0
    for priority, repair in enumerate(repairs, start=120):
        if repair in existing:
            continue
        queue.enqueue(Job.create(repair, priority, {"source": "final_threshold_eval"}))
        enqueued += 1

    print("FINAL_THRESHOLD_REPAIR")
    print(f"ENQUEUED={enqueued}")
    for repair in repairs:
        print(f"REPAIR={repair}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

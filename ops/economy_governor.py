#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime_data"
CONFIG = ROOT / "configs"
CONTROL_STATE = RUNTIME / "autonomy" / "control" / "state.yml"
SUMMARY_PATH = RUNTIME / "autonomy" / "economy_governor_summary.yml"
ECONOMY_DIR = RUNTIME / "economy_operations"
LEDGER_PATH = ECONOMY_DIR / "ledger.jsonl"


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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def main() -> int:
    created_at = now_iso()
    control = load_yaml(CONTROL_STATE)
    ECONOMY_DIR.mkdir(parents=True, exist_ok=True)
    status_dir = RUNTIME / "status"
    economy = load_yaml(CONFIG / "economy.yml")
    threshold = float(((load_yaml(CONFIG / "autonomy.yml").get("quality_targets", {}) or {}).get("economy_inflation_ratio_warning", 1.35)))
    earn = 0
    spend = 0
    exploit_flags = 0
    for status_path in sorted(status_dir.glob("*.yml")):
        status = load_yaml(status_path)
        earn += int(status.get("economy_earn", 0))
        spend += int(status.get("economy_spend", 0))
        exploit_flags += int(status.get("exploit_flag", 0))

    ratio = (earn / spend) if spend else float(earn > 0)
    anomaly = ratio >= threshold or exploit_flags > 0
    action = "adjust" if anomaly else "observe"
    proposal = {
        "proposal_id": f"economy-{uuid.uuid4().hex[:12]}",
        "created_at": created_at,
        "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
        "market_tax": float(economy.get("market_tax", 0.0)),
        "earn_total": earn,
        "spend_total": spend,
        "inflation_ratio": round(ratio, 3),
        "exploit_flags": exploit_flags,
        "action": action,
        "calibration": {
            "faucet_sink_balance": "tighten_tax_and_progression_cost" if anomaly else "hold_current_parameters",
            "rare_supply_watch": "increase_binding_pressure" if anomaly else "stable",
            "progression_cost_watch": "raise_upgrade_sink" if anomaly else "stable",
        },
        "next_job_type": "autonomous_quality_loop" if anomaly else "runtime_summary",
    }
    proposal["signature"] = hashlib.sha256(json.dumps(proposal, sort_keys=True).encode("utf-8")).hexdigest()
    write_yaml(ECONOMY_DIR / f"{created_at.replace(':', '').replace('-', '')}_{proposal['proposal_id']}.yml", proposal)
    append_jsonl(
        LEDGER_PATH,
        {
            "created_at": created_at,
            "proposal_id": proposal["proposal_id"],
            "action": action,
            "inflation_ratio": proposal["inflation_ratio"],
            "signature": proposal["signature"],
        },
    )
    summary = {
        "created_at": created_at,
        "proposal_id": proposal["proposal_id"],
        "action": action,
        "inflation_ratio": proposal["inflation_ratio"],
        "earn_total": earn,
        "spend_total": spend,
        "economy_inflation_ratio_warning": threshold,
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("ECONOMY_GOVERNOR")
    print(f"ACTION={action}")
    print(f"INFLATION_RATIO={proposal['inflation_ratio']}")
    print(f"NEXT_JOB={proposal['next_job_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

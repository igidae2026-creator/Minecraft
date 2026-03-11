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
SUMMARY_PATH = RUNTIME / "autonomy" / "anti_cheat_governor_summary.yml"
ANTI_CHEAT_DIR = RUNTIME / "anti_cheat"
LEDGER_PATH = ANTI_CHEAT_DIR / "ledger.jsonl"
PLAYER_EXPERIENCE_PATH = RUNTIME / "autonomy" / "player_experience_summary.yml"


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
    player_experience = load_yaml(PLAYER_EXPERIENCE_PATH)
    ANTI_CHEAT_DIR.mkdir(parents=True, exist_ok=True)
    threshold = float(((load_yaml(CONFIG / "autonomy.yml").get("quality_targets", {}) or {}).get("exploit_incident_warning", 2.0)))
    status_dir = RUNTIME / "status"
    incidents = 0.0
    exploit_flags = 0
    sandbox_cases: list[dict[str, Any]] = []
    for status_path in sorted(status_dir.glob("*.yml")):
        status = load_yaml(status_path)
        server = status_path.stem
        incident_total = float((status.get("exploit_forensics_plane", {}) or {}).get("incident_total", 0.0))
        flag_count = int(status.get("exploit_flag", 0))
        incidents += incident_total
        exploit_flags += flag_count
        if incident_total > 0 or flag_count > 0:
            sandbox_cases.append(
                {
                    "server": server,
                    "signal": "exploit_incident" if incident_total > 0 else "exploit_flag",
                    "sandbox": True,
                    "review_required": True,
                }
            )

    if not sandbox_cases:
        sandbox_cases.append(
            {
                "server": "synthetic_fault_injection",
                "signal": "macro_path_probe",
                "sandbox": incidents >= threshold,
                "review_required": incidents >= threshold,
            }
        )

    experience_percent = float(player_experience.get("estimated_completeness_percent", 0.0))
    first_session_strength = float(player_experience.get("first_session_strength", 0.0))
    progression_protection_score = round(
        max(
            0.0,
            min(
                1.0,
                0.55
                + (0.25 if incidents == 0 else 0.0)
                + (0.1 if exploit_flags == 0 else 0.0)
                + (0.1 if first_session_strength >= 0.9 else 0.0),
            ),
        ),
        2,
    )
    trusted_progression_window = bool(incidents == 0 and exploit_flags == 0 and experience_percent >= 40.0)

    plan_id = f"ac-{uuid.uuid4().hex[:12]}"
    payload = {
        "plan_id": plan_id,
        "created_at": created_at,
        "control_ref": str(CONTROL_STATE.relative_to(ROOT)),
        "incident_total": incidents,
        "exploit_flags": exploit_flags,
        "threshold": threshold,
        "sandbox_cases": sandbox_cases,
        "rule_change": {
            "mode": "hold_and_review" if incidents >= threshold or exploit_flags > 0 else "observe_and_replay",
            "replayable": True,
            "append_only_truth": True,
        },
        "progression_protection": {
            "progression_protection_score": progression_protection_score,
            "trusted_progression_window": trusted_progression_window,
        },
    }
    payload["signature"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    write_yaml(ANTI_CHEAT_DIR / f"{created_at.replace(':', '').replace('-', '')}_{plan_id}.yml", payload)
    append_jsonl(
        LEDGER_PATH,
        {
            "created_at": created_at,
            "plan_id": plan_id,
            "sandbox_cases": len(sandbox_cases),
            "incident_total": incidents,
            "signature": payload["signature"],
        },
    )
    summary = {
        "created_at": created_at,
        "plan_id": plan_id,
        "sandbox_cases": len(sandbox_cases),
        "incident_total": incidents,
        "exploit_flags": exploit_flags,
        "mode": payload["rule_change"]["mode"],
        "progression_protection_score": progression_protection_score,
        "trusted_progression_window": trusted_progression_window,
        "autonomy_threshold_ready": bool(control.get("autonomy_threshold_ready", False)),
    }
    write_yaml(SUMMARY_PATH, summary)
    print("ANTI_CHEAT_GOVERNOR")
    print(f"SANDBOX_CASES={len(sandbox_cases)}")
    print(f"INCIDENT_TOTAL={incidents:.1f}")
    print(f"MODE={payload['rule_change']['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

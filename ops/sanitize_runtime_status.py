#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "runtime_data" / "status"


def sanitize_text(text: str) -> tuple[str, int]:
    fixed = []
    changes = 0
    for line in text.splitlines():
        updated = line
        if updated.startswith("   ") and not updated.startswith("    ") and ":" in updated and not updated.lstrip().startswith("-"):
            updated = " " + updated
            changes += 1
        if "archive_export_path/" in updated:
            updated = updated.replace("archive_export_path/", "archive_export_path: /", 1)
            changes += 1
        if updated.strip() == "}":
            changes += 1
            continue
        fixed.append(updated)
    return "\n".join(fixed) + ("\n" if text.endswith("\n") else ""), changes


def main() -> int:
    total_changes = 0
    for path in sorted(STATUS_DIR.glob("*.yml")):
        if path.name == ".gitkeep":
            continue
        original = path.read_text(encoding="utf-8")
        sanitized, changes = sanitize_text(original)
        if changes:
            path.write_text(sanitized, encoding="utf-8")
            total_changes += changes
    print(f"SANITIZED_LINES={total_changes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

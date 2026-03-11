#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    completed = subprocess.run([sys.executable, str(ROOT / "ops" / "runtime_summary.py")], cwd=ROOT, text=True, capture_output=False, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

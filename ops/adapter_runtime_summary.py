#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def adapter_target() -> str:
    return str(ROOT / "ops" / "runtime_summary.py")


if __name__ == "__main__":
    print(adapter_target())

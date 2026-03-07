from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs"

def load_yaml(name: str):
    normalized = name[8:] if name.startswith("configs/") else name
    with (CONFIG / normalized).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

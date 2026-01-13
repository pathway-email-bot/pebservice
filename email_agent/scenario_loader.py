# scenario_loader.py

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

import yaml

from scenarios import Scenario


def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported scenario file extension: {path.suffix}")


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    raw = _load_raw(path)
    return Scenario(**raw)

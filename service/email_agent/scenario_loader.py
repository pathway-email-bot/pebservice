# scenario_loader.py

import json
from pathlib import Path
from typing import Any, Dict

import yaml

from .scenario_models import Scenario

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


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
    # If no extension or not an absolute path, resolve relative to scenarios dir
    if not path.is_absolute() and not path.suffix:
        # Try .json first, then .yaml
        for ext in ['.json', '.yaml', '.yml']:
            candidate = SCENARIOS_DIR / f"{path}{ext}"
            if candidate.exists():
                path = candidate
                break
        else:
            # Fall back to original for error message
            path = SCENARIOS_DIR / path
    raw = _load_raw(path)
    return Scenario(**raw)

"""Utilities for loading rubric definitions from JSON or YAML files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

import yaml

from rubric import RubricItem


@dataclass(frozen=True)
class RubricDefinition:
    """Complete rubric definition returned by loaders."""

    name: str
    description: str
    items: List[RubricItem]


def _coerce_items(raw_items: Sequence[Mapping[str, Any]]) -> List[RubricItem]:
    items: List[RubricItem] = []
    for idx, item in enumerate(raw_items, start=1):
        if "name" not in item or "description" not in item:
            raise ValueError(
                f"Rubric item #{idx} is missing required 'name' or 'description' fields"
            )
        items.append(
            RubricItem(
                name=str(item["name"]),
                description=str(item["description"]),
                max_score=int(item.get("max_score", 5)),
            )
        )
    if not items:
        raise ValueError("Rubric must include at least one item")
    return items


def _load_raw(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Rubric file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    raise ValueError(f"Unsupported rubric file type: {path.suffix}")


def load_rubric(path: str | Path) -> RubricDefinition:
    path = Path(path)
    raw = _load_raw(path)

    if isinstance(raw, Mapping):
        if "items" not in raw:
            raise ValueError("Rubric JSON must contain an 'items' array")
        name = str(raw.get("name") or path.stem)
        description = str(raw.get("description") or "")
        items = _coerce_items(raw["items"])
    elif isinstance(raw, Sequence):
        name = path.stem
        description = ""
        items = _coerce_items(raw)  # type: ignore[arg-type]
    else:
        raise ValueError("Rubric file must be a list or an object with an 'items' list")

    return RubricDefinition(name=name, description=description, items=items) 
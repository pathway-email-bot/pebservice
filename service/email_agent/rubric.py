# rubric.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RubricItem:
    name: str
    description: str
    max_score: int = 5


# Global rubric reused across all scenarios
GLOBAL_RUBRIC: List[RubricItem] = [
    RubricItem(
        name="Tone & respect",
        description="Email is polite and respectful, not too casual or emotional.",
    ),
    RubricItem(
        name="Clarity & conciseness",
        description="Message is easy to understand and not too long.",
    ),
    RubricItem(
        name="Structure",
        description="Email has a clear greeting, organized body, and proper closing.",
    ),
    RubricItem(
        name="Professionalism & responsibility",
        description="Student takes responsibility where needed and shows commitment.",
    ),
    RubricItem(
        name="Task fulfillment",
        description="Student clearly answers the request or makes a clear ask.",
    ),
]

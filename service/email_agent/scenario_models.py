# scenarios.py (or scenario_models.py)

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InteractionType(str, Enum):
    """Whether the student initiates or replies to an email."""
    INITIATE = "initiate"
    REPLY = "reply"


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    environment: str
    counterpart_role: str

    # What the student is expected to do
    student_task: str          # was student_instructions

    # How the counterpart behaves
    counterpart_style: str = ""   # was counterpart_instructions

    # Scenario-specific grading hints
    grading_focus: str = ""       # was grading_instructions

    # What the counterpart realistically knows (used in reply prompt only)
    counterpart_context: str = ""

    # Type of interaction
    interaction_type: InteractionType = InteractionType.INITIATE

    # Starter email
    starter_sender_name: str = "Jordan Smith (Manager - Bot)"
    starter_subject: str = "Regarding your work today"
    starter_email_body: Optional[str] = None
    starter_email_generation_hint: str = (
        "Write a realistic starter email for the situation, 1-3 short paragraphs."
    )

    def __post_init__(self):
        # Coerce plain strings from JSON into the enum
        if isinstance(self.interaction_type, str):
            # frozen=True requires object.__setattr__
            object.__setattr__(
                self, 'interaction_type', InteractionType(self.interaction_type)
            )

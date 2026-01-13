# scenarios.py (or scenario_models.py)

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


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

    # Starter email
    starter_sender_name: str = "Jordan Smith (Manager)"
    starter_subject: str = "Regarding your work today"
    starter_email_body: Optional[str] = None
    starter_email_generation_hint: str = (
        "Write a realistic starter email for the situation, 1–3 short paragraphs."
    )

# rubric.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RubricItem:
    name: str
    description: str
    max_score: int = 5


# Global rubric reused across all scenarios (matches peb_rubric_v1.json)
GLOBAL_RUBRIC: List[RubricItem] = [
    RubricItem(
        name="Tone & respect",
        description=(
            "Tone is professional, courteous, and culturally appropriate. "
            "Avoids slang, excessive informality, emotional language, or abruptness. "
            "Adapts formality to the recipient and context."
        ),
    ),
    RubricItem(
        name="Clarity & purpose",
        description=(
            "The email clearly states its purpose early — ideally in the first 1-2 sentences. "
            "The reader immediately understands why the message was sent. "
            "Content is concise, focused on relevant details, and avoids unnecessary information."
        ),
    ),
    RubricItem(
        name="Structure & formatting",
        description=(
            "Has a clear greeting, organized body paragraphs, and a professional closing or sign-off. "
            "Uses short paragraphs or bullet points where appropriate to aid readability."
        ),
    ),
    RubricItem(
        name="Professionalism & responsibility",
        description=(
            "Takes ownership where appropriate and avoids blame or excessive excuses. "
            "Demonstrates reliability and commitment. "
            "Offers solutions or next steps proactively rather than just stating problems."
        ),
    ),
    RubricItem(
        name="Task fulfillment & actionable next steps",
        description=(
            "Addresses all parts of the assignment. "
            "Explicitly states any required actions — what is needed, from whom, and by when. "
            "Ends with a clear call-to-action or next step so the recipient knows exactly how to respond."
        ),
    ),
    RubricItem(
        name="Grammar & readability",
        description=(
            "Language is correct enough not to distract or confuse the reader. "
            "Sentences are complete and easy to follow. "
            "Spelling and punctuation do not undermine the writer's credibility."
        ),
    ),
    RubricItem(
        name="Subject line",
        description=(
            "Subject line is clear, specific, and professional. "
            "It accurately reflects the email's content and would help the recipient prioritize the message. "
            "For reply scenarios where the subject is pre-set, full marks are appropriate "
            "if the student does not change it to something less appropriate."
        ),
    ),
]

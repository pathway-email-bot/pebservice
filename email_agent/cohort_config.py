from dataclasses import dataclass


@dataclass(frozen=True)
class CohortConfig:
    student_program: str = "BYU-Pathway Worldwide"
    student_background: str = (
        "Most learners are from developing countries, improving their earning "
        "ability through remote work, and are non-native English speakers."
    )
    english_level: str = "intermediate"
    remote_context: str = (
        "The student may have unstable internet and power but is trying to be "
        "professional and reliable."
    )
    employer_region: str = "US-based employer in a different time zone"

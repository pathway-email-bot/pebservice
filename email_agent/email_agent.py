from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Sequence

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from .scenario_models import Scenario
from .rubric import GLOBAL_RUBRIC, RubricItem


# ----------------- Data models -----------------


@dataclass(frozen=True)
class EmailMessage:
    sender: str
    subject: str
    body: str


@dataclass(frozen=True)
class RubricScoreResult:
    name: str
    score: int
    max_score: int


@dataclass(frozen=True)
class GradingResult:
    scenario_name: str
    scores: List[RubricScoreResult]
    total_score: int
    max_total_score: int
    overall_comment: str
    revision_example: str
    model_info: Dict[str, Any]
    raw_json: Dict[str, Any]


@dataclass(frozen=True)
class EvaluationAndReply:
    grading: GradingResult
    counterpart_reply: str


class TaskType(str, Enum):
    COUNTERPART_PROMPT = "counterpart_prompt"
    COUNTERPART_REPLY = "counterpart_reply"
    GRADE_STUDENT_EMAIL = "grade_student_email"


# ----------------- Helpers & prompts -----------------

# (Keeping prompts as they were)
BASE_SYSTEM_PROMPT = (
    "You are part of an email etiquette training simulator for students in the "
    "BYU-Pathway Worldwide program.\n"
    "Most learners are from developing countries and are non-native English speakers.\n"
    "They are preparing for remote work with employers in other countries.\n"
    "Your job is to model and support clear, respectful, and professional email "
    "communication in a global workplace.\n"
    "Always:\n"
    "- Use clear, simple English (CEFR B1–B2 level).\n"
    "- Avoid slang, idioms, or cultural references that may be confusing.\n"
    "- Show how to be respectful but also confident and responsible.\n"
)


def _thread_to_text(thread: Sequence[EmailMessage]) -> str:
    if not thread:
        return "(no prior emails yet)"
    lines: list[str] = []
    for idx, message in enumerate(thread, start=1):
        header = f"Message {idx} — From: {message.sender} | Subject: {message.subject}".strip()
        body = message.body.strip()
        lines.append(f"{header}\n{body}\n")
    return "\n".join(lines).strip()

# ... (Templates unchanged) ...
COUNTERPART_PROMPT_TEMPLATE = """
{system_prompt}

LEARNER & CONTEXT:
- Program: BYU-Pathway Worldwide
- Learner background: Most learners are from developing countries, improving their earning
  ability through remote work, and are non-native English speakers.
- English level: intermediate
- Remote work context: The student may have unstable internet and power but is trying to be
  professional and reliable.
- Typical employer region: US-based employer in a different time zone

SCENARIO:
- Name: {scenario_name}
- Environment: {environment}
- You are role-playing as: {counterpart_role}

What the student is expected to do in this assignment:
{student_task}

How you (the counterpart) should sound:
{counterpart_style}

Your job:
- Write a realistic email from the counterpart to the student in a REMOTE WORK situation.
- This email will usually be the first email in the thread.
- Use clear, professional English that is easy for an intermediate learner to understand.
- Avoid slang, idioms, or heavy cultural references.
- 1–3 short paragraphs is enough.

Operator instructions:
{instructions}

Draft the full counterpart email below as plain text.
Do not explain your reasoning, only output the email body.
"""


COUNTERPART_REPLY_TEMPLATE = """
{system_prompt}

LEARNER & CONTEXT:
- Program: BYU-Pathway Worldwide
- Learner background: Most learners are from developing countries, improving their earning
  ability through remote work, and are non-native English speakers.
- English level: intermediate
- Remote work context: The student may have unstable internet and power but is trying to be
  professional and reliable.
- Typical employer region: US-based employer in a different time zone

SCENARIO:
- Name: {scenario_name}
- Environment: {environment}
- You are role-playing as: {counterpart_role}

What the student is expected to do in this assignment:
{student_task}

How you (the counterpart) should sound:
{counterpart_style}

Email thread so far (newest last):
{email_thread}

You have just received the student's email above.
Write a realistic reply from the counterpart (manager, client, etc.) to the student.

Guidelines:
- Respond in a calm, professional tone.
- Acknowledge what the student said.
- Confirm any decisions, next steps, or expectations.
- Use clear, simple English.
- Keep it 1–3 short paragraphs.

Operator instructions:
{instructions}

Draft the full counterpart reply below as plain text.
Do not explain your reasoning, only output the email body.
"""


GRADING_JSON_TEMPLATE = """
{system_prompt}

You are grading a student's email for a remote-work email etiquette assignment.

LEARNER & CONTEXT:
- Program: BYU-Pathway Worldwide
- Learner background: Most learners are from developing countries, improving their earning
  ability through remote work, and are non-native English speakers.
- English level: intermediate
- Remote work context: The student may have unstable internet and power but is trying to be
  professional and reliable.
- Typical employer region: US-based employer in a different time zone

SCENARIO:
- Name: {scenario_name}
- Environment: {environment}
- Counterpart role: {counterpart_role}

What the student was asked to do:
{student_task}

Grading focus for this scenario:
{grading_focus}

Here is the email thread the student is responding to (newest last):
{email_thread}

Here is the student's email to grade:
{student_email}

RUBRIC:
{rubric_text}

Return your feedback as a single JSON object with this structure:

{{
  "scores": [
    {{"name": "<rubric item name>", "score": 1-5, "max_score": 5}},
    ...
  ],
  "overall_comment": "<3-6 sentences of feedback in simple, kind English>",
  "revision_example": "<a revised version of the student's email that is better but realistic>"
}}

Important:
- Do NOT include any text before or after the JSON.
- Do NOT wrap the JSON in backticks or say 'Here is the JSON'.
- Only output valid JSON.
"""


# ----------------- EmailAgent -----------------


class EmailAgent:
    def __init__(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.2,
        base_url: str | None = None,
        scenario: Scenario,
        api_key: str | None = None,
    ) -> None:
        self.scenario = scenario

        llm_kwargs: Dict[str, Any] = {"model": model, "temperature": temperature}
        if base_url is not None:
            llm_kwargs["base_url"] = base_url
        if api_key:
            llm_kwargs["api_key"] = api_key

        self._llm = ChatOpenAI(**llm_kwargs)

        # Build prompt chains
        self._counterpart_prompt_chain = self._build_chain(
            COUNTERPART_PROMPT_TEMPLATE
        )
        self._counterpart_reply_chain = self._build_chain(
            COUNTERPART_REPLY_TEMPLATE
        )

    def _build_chain(self, template: str) -> RunnableSequence:
        prompt = PromptTemplate(
            template=template,
            input_variables=[
                "system_prompt",
                "scenario_name",
                "environment",
                "counterpart_role",
                "student_task",
                "counterpart_style",
                "grading_focus",
                "email_thread",
                "instructions",
            ],
        )
        return prompt | self._llm | StrOutputParser()

    def _base_payload(self) -> Dict[str, str]:
        s = self.scenario
        return {
            "system_prompt": BASE_SYSTEM_PROMPT,
            "scenario_name": s.name,
            "environment": s.environment,
            "counterpart_role": s.counterpart_role,
            "student_task": s.student_task,
            "counterpart_style": s.counterpart_style,
            "grading_focus": s.grading_focus,
        }

    # ---------- Starter email generation ----------

    def build_starter_thread(self) -> List[EmailMessage]:
        """Create the initial thread (first email from counterpart)."""
        s = self.scenario

        if s.starter_email_body:
            body = s.starter_email_body
        else:
            payload = self._base_payload()
            payload["email_thread"] = _thread_to_text([])
            combined_instructions = (
                (s.counterpart_style or "").strip()
                + "\n\n"
                + (s.starter_email_generation_hint or "").strip()
            ).strip()
            payload["instructions"] = (
                combined_instructions
                or "Write a simple starter email for this scenario."
            )
            body = self._counterpart_prompt_chain.invoke(payload)

        return [
            EmailMessage(
                sender=s.starter_sender_name,
                subject=s.starter_subject,
                body=body,
            )
        ]

    # ---------- Counterpart reply ----------

    def reply_as_counterpart(
        self,
        thread: Sequence[EmailMessage],
        *,
        instructions: str | None = None,
    ) -> str:
        """Generate the AI counterpart's reply to the current email thread."""
        payload = self._base_payload()
        payload["email_thread"] = _thread_to_text(thread)
        payload["instructions"] = (
            instructions.strip()
            if instructions
            else (self.scenario.counterpart_style or "Respond as a professional manager.")
        )
        return self._counterpart_reply_chain.invoke(payload)

    # ---------- Grading ----------

    def grade_student_email(
        self,
        thread: Sequence[EmailMessage],
        student_email: str,
        rubric: Sequence[RubricItem] = GLOBAL_RUBRIC,
        *,
        model_name: str | None = None,
        temperature: float | None = None,
    ) -> GradingResult:
        """Grade a student's email against a rubric and return structured results."""
        s = self.scenario

        rubric_lines = [
            f"- {item.name} (1–{item.max_score}): {item.description}"
            for item in rubric
        ]
        rubric_text = "\n".join(rubric_lines)

        prompt = PromptTemplate(
            template=GRADING_JSON_TEMPLATE,
            input_variables=[
                "system_prompt",
                "scenario_name",
                "environment",
                "counterpart_role",
                "student_task",
                "grading_focus",
                "email_thread",
                "student_email",
                "rubric_text",
            ],
        )

        chain: RunnableSequence = prompt | self._llm | StrOutputParser()

        payload = {
            "system_prompt": BASE_SYSTEM_PROMPT,
            "scenario_name": s.name,
            "environment": s.environment,
            "counterpart_role": s.counterpart_role,
            "student_task": s.student_task,
            "grading_focus": s.grading_focus or "",
            "email_thread": _thread_to_text(thread),
            "student_email": student_email.strip(),
            "rubric_text": rubric_text,
        }

        raw_output = chain.invoke(payload).strip()
        data = json.loads(raw_output)

        scores: List[RubricScoreResult] = []
        total_score = 0
        max_total_score = 0

        for item in data.get("scores", []):
            score = int(item["score"])
            max_score = int(item.get("max_score", 5))
            scores.append(
                RubricScoreResult(
                    name=item["name"],
                    score=score,
                    max_score=max_score,
                )
            )
            total_score += score
            max_total_score += max_score

        if max_total_score == 0 and scores:
            max_total_score = sum(s.max_score for s in scores)

        model_info = {
            "model_name": model_name or getattr(self._llm, "model_name", "unknown"),
            "temperature": temperature
            if temperature is not None
            else getattr(self._llm, "temperature", None),
        }

        return GradingResult(
            scenario_name=s.name,
            scores=scores,
            total_score=total_score,
            max_total_score=max_total_score,
            overall_comment=data.get("overall_comment", "").strip(),
            revision_example=data.get("revision_example", "").strip(),
            model_info=model_info,
            raw_json=data,
        )

    # ---------- High-level operation ----------

    def evaluate_and_respond(
        self,
        *,
        prior_thread: Sequence[EmailMessage],
        student_email: EmailMessage,
        rubric: Sequence[RubricItem] = GLOBAL_RUBRIC,
    ) -> EvaluationAndReply:
        """Given prior thread + student's email, return grading + counterpart reply."""
        grading = self.grade_student_email(
            thread=prior_thread,
            student_email=student_email.body,
            rubric=rubric,
        )

        full_thread = list(prior_thread) + [student_email]
        counterpart_reply = self.reply_as_counterpart(full_thread)

        return EvaluationAndReply(
            grading=grading,
            counterpart_reply=counterpart_reply,
        )

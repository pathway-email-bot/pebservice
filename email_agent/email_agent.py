# email_agent.py

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Sequence

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI

from scenarios import Scenario
from rubric import GLOBAL_RUBRIC, RubricItem


# ----------------- Data models -----------------
# ... (intermediate code omitted for brevity) ...

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
        
        # If api_key is provided, pass it; otherwise it looks for env var OPENAI_API_KEY
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
        # Grading uses a dedicated chain built inside grade_student_email

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
        # OpenAI chat models outputs a message, so we pipe to StrOutputParser to get string
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
            "model_name": model_name or getattr(self._llm, "model", "unknown"),
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

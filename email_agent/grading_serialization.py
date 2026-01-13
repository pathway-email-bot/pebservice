from __future__ import annotations
from dataclasses import asdict
from typing import Dict, Any

from email_agent import GradingResult, RubricScoreResult


def grading_result_to_storage(gr: GradingResult) -> Dict[str, Any]:
    """Convert GradingResult into a dict suitable for storing in Supabase (jsonb)."""
    return {
        "version": 1,
        "scenario_name": gr.scenario_name,
        "rubric_scores": [
            {
                "name": s.name,
                "score": s.score,
                "max_score": s.max_score,
            }
            for s in gr.scores
        ],
        "total_score": gr.total_score,
        "max_total_score": gr.max_total_score,
        "overall_comment": gr.overall_comment,
        "revision_example": gr.revision_example,
        "model_info": gr.model_info,
        # Optional: keep raw LLM JSON if you ever change parsing logic
        "raw_llm_output": gr.raw_json,
    }


def grading_result_from_storage(data: Dict[str, Any]) -> GradingResult:
    """Rebuild a GradingResult from stored JSON. Useful if you want to
    reconstruct objects in Python for reporting, etc.
    """
    scores = [
        RubricScoreResult(
            name=item["name"],
            score=int(item["score"]),
            max_score=int(item.get("max_score", 5)),
        )
        for item in data.get("rubric_scores", [])
    ]

    total_score = int(data.get("total_score", sum(s.score for s in scores)))
    max_total_score = int(
        data.get("max_total_score", sum(s.max_score for s in scores))
    )

    return GradingResult(
        scenario_name=data["scenario_name"],
        scores=scores,
        total_score=total_score,
        max_total_score=max_total_score,
        overall_comment=data.get("overall_comment", "").strip(),
        revision_example=data.get("revision_example", "").strip(),
        model_info=data.get("model_info", {}),
        raw_json=data.get("raw_llm_output", {}),
    )

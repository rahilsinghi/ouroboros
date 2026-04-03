"""Real-world benchmark dimension — LLM-graded open-ended evaluation."""
from __future__ import annotations

from ouroboros.types import DimensionScore


class RealWorldScorer:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.model = model

    def score(self, evaluations: list[dict[str, float]]) -> DimensionScore:
        """Score from LLM evaluations. Each eval has helpfulness, accuracy, completeness (1-5)."""
        if not evaluations:
            return DimensionScore(name="real_world", value=0.0)
        total = 0.0
        for ev in evaluations:
            helpfulness = (ev.get("helpfulness", 1) - 1) / 4
            accuracy = (ev.get("accuracy", 1) - 1) / 4
            completeness = (ev.get("completeness", 1) - 1) / 4
            total += (helpfulness + accuracy + completeness) / 3
        return DimensionScore(name="real_world", value=total / len(evaluations))

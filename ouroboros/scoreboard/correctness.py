"""Correctness benchmark dimension — task pass/fail rate."""
from __future__ import annotations

from ouroboros.types import DimensionScore


class CorrectnessScorer:
    """Scores correctness as the fraction of tasks that pass.

    A pass/fail dict with no entries returns 0.0.
    """

    def score(self, results: dict[str, bool]) -> DimensionScore:
        """Score based on pass/fail results. Empty results = 0.0."""
        if not results:
            return DimensionScore(name="correctness", value=0.0)
        passed = sum(1 for v in results.values() if v)
        return DimensionScore(name="correctness", value=passed / len(results))

"""Efficiency benchmark dimension — token usage compared to baseline."""
from __future__ import annotations

from ouroboros.types import DimensionScore


class EfficiencyScorer:
    def __init__(self, baseline_tokens: int) -> None:
        self.baseline_tokens = baseline_tokens

    def score(self, current_tokens: int) -> DimensionScore:
        """Score = baseline / current, capped at 1.0. Lower tokens = higher score."""
        if current_tokens <= 0 or self.baseline_tokens <= 0:
            return DimensionScore(name="efficiency", value=1.0)
        value = min(1.0, self.baseline_tokens / current_tokens)
        return DimensionScore(name="efficiency", value=value)

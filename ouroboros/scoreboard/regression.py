"""Regression benchmark dimension — previously-passing tasks still pass."""
from __future__ import annotations

from ouroboros.types import DimensionScore


class RegressionScorer:
    def score(self, previously_passing: set[str], still_passing: set[str]) -> DimensionScore:
        """Score = fraction of previously-passing tasks still passing."""
        if not previously_passing:
            return DimensionScore(name="regression", value=1.0)
        kept = len(previously_passing & still_passing)
        return DimensionScore(name="regression", value=kept / len(previously_passing))

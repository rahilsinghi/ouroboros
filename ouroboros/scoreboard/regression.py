"""Regression benchmark dimension — previously-passing tasks still pass."""
from __future__ import annotations

from ouroboros.types import DimensionScore


class RegressionScorer:
    """Scores regression as the fraction of previously-passing tasks that still pass.

    A regression score of 1.0 means no regressions were introduced; lower values
    indicate that some tasks which previously passed are now failing.
    """

    def score(self, previously_passing: set[str], still_passing: set[str]) -> DimensionScore:
        """Score = fraction of previously-passing tasks still passing.

        Parameters
        ----------
        previously_passing:
            Set of task IDs that passed before the change.
        still_passing:
            Set of task IDs that pass after the change.

        Returns
        -------
        DimensionScore
            A score between 0.0 and 1.0 representing the fraction of
            *previously_passing* tasks found in *still_passing*.  Returns
            1.0 when *previously_passing* is empty (nothing to regress).
        """
        if not previously_passing:
            return DimensionScore(name="regression", value=1.0)
        kept = len(previously_passing & still_passing)
        return DimensionScore(name="regression", value=kept / len(previously_passing))

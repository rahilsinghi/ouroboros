# ouroboros/scoreboard/runner.py
"""Scoreboard runner and merge gate logic."""

from __future__ import annotations

from dataclasses import dataclass

from ouroboros.types import DimensionScore, ScoreboardSnapshot


@dataclass(frozen=True)
class MergeGate:
    regression_floor: float
    noise_tolerance: float

    def can_merge(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> bool:
        """Check if the after snapshot passes the merge gate relative to before."""
        # Hard requirement: regression must meet floor
        regression = after.get("regression")
        if regression is not None and regression.value < self.regression_floor:
            return False

        # Hard requirement: correctness never drops
        before_correctness = before.get("correctness")
        after_correctness = after.get("correctness")
        if before_correctness and after_correctness:
            if after_correctness.value < before_correctness.value:
                return False

        # At least one dimension must improve beyond noise
        improved = False
        for after_dim in after.dimensions:
            before_dim = before.get(after_dim.name)
            if before_dim is None:
                continue
            if after_dim.value > before_dim.value + self.noise_tolerance:
                improved = True

        if not improved:
            return False

        # No dimension regresses beyond noise (except new dimensions)
        for before_dim in before.dimensions:
            after_dim = after.get(before_dim.name)
            if after_dim is None:
                continue
            if after_dim.value < before_dim.value - self.noise_tolerance:
                return False

        return True


def can_merge(
    before: ScoreboardSnapshot,
    after: ScoreboardSnapshot,
    regression_floor: float = 1.0,
    noise_tolerance: float = 0.02,
) -> bool:
    """Convenience function for merge gate check."""
    gate = MergeGate(regression_floor=regression_floor, noise_tolerance=noise_tolerance)
    return gate.can_merge(before, after)

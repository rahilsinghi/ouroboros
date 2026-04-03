# tests/ouroboros/test_scoreboard_runner.py
import pytest

from ouroboros.types import DimensionScore, ScoreboardSnapshot
from ouroboros.scoreboard.runner import MergeGate, can_merge


class TestMergeGate:
    def _snap(self, iteration: int, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=iteration, dimensions=dims)

    def test_improvement_merges(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is True

    def test_regression_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=0.95)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_correctness_drop_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.75, tool_selection=0.72, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_no_improvement_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.65, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_noise_tolerance_ignores_tiny_regression(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=1.0,
                           code_quality=0.89)  # new dimension
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is True

    def test_dimension_regresses_beyond_noise(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, efficiency=0.7, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, efficiency=0.63, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

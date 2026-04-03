from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.evaluator import EvaluatorAgent, EvalDecision
from ouroboros.config import DEFAULT_CONFIG
from ouroboros.types import DimensionScore, ScoreboardSnapshot


class TestEvaluatorAgent:
    def _snap(self, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=1, dimensions=dims)

    def test_merge_when_improved(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.75, regression=1.0)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.MERGE

    def test_rollback_when_regressed(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.72, regression=0.9)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.ROLLBACK

    def test_rollback_when_no_improvement(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.ROLLBACK

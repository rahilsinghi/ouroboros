import pytest

from ouroboros.types import DimensionScore
from ouroboros.scoreboard.correctness import CorrectnessScorer
from ouroboros.scoreboard.efficiency import EfficiencyScorer
from ouroboros.scoreboard.regression import RegressionScorer


class TestCorrectnessScorer:
    def test_all_pass(self):
        scorer = CorrectnessScorer()
        results = {"task1": True, "task2": True, "task3": True}
        score = scorer.score(results)
        assert score.name == "correctness"
        assert score.value == 1.0

    def test_partial_pass(self):
        scorer = CorrectnessScorer()
        results = {"task1": True, "task2": False, "task3": True}
        score = scorer.score(results)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_empty_results(self):
        scorer = CorrectnessScorer()
        score = scorer.score({})
        assert score.value == 0.0


class TestEfficiencyScorer:
    def test_better_than_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=500)
        assert score.name == "efficiency"
        assert score.value == 1.0  # capped at 1.0

    def test_worse_than_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=2000)
        assert score.value == 0.5

    def test_same_as_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=1000)
        assert score.value == 1.0

    def test_zero_current(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=0)
        assert score.value == 1.0


class TestRegressionScorer:
    def test_no_regressions(self):
        scorer = RegressionScorer()
        previously_passing = {"task1", "task2", "task3"}
        still_passing = {"task1", "task2", "task3"}
        score = scorer.score(previously_passing, still_passing)
        assert score.name == "regression"
        assert score.value == 1.0

    def test_one_regression(self):
        scorer = RegressionScorer()
        previously_passing = {"task1", "task2", "task3"}
        still_passing = {"task1", "task3"}
        score = scorer.score(previously_passing, still_passing)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_empty_history(self):
        scorer = RegressionScorer()
        score = scorer.score(set(), {"task1"})
        assert score.value == 1.0

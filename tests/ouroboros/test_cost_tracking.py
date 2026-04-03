"""Tests for cost tracking."""
from ouroboros.agents.base import tokens_to_usd, CostTracker


class TestTokensToUsd:
    def test_sonnet_pricing(self):
        cost = tokens_to_usd(input_tokens=1000, output_tokens=1000, model="claude-sonnet-4-6")
        expected = (1000 * 3.0 / 1_000_000) + (1000 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_opus_pricing(self):
        cost = tokens_to_usd(input_tokens=1000, output_tokens=1000, model="claude-opus-4-6")
        expected = (1000 * 15.0 / 1_000_000) + (1000 * 75.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_haiku_pricing(self):
        cost = tokens_to_usd(input_tokens=1000, output_tokens=1000, model="claude-haiku-4-5-20251001")
        expected = (1000 * 0.80 / 1_000_000) + (1000 * 4.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001

    def test_unknown_model_uses_sonnet_pricing(self):
        cost = tokens_to_usd(input_tokens=1000, output_tokens=1000, model="unknown-model")
        expected = (1000 * 3.0 / 1_000_000) + (1000 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 0.0001


class TestCostTracker:
    def test_accumulates_costs(self):
        tracker = CostTracker()
        tracker.add(input_tokens=1000, output_tokens=500, model="claude-sonnet-4-6")
        tracker.add(input_tokens=2000, output_tokens=1000, model="claude-sonnet-4-6")
        assert tracker.total_input_tokens == 3000
        assert tracker.total_output_tokens == 1500
        assert tracker.total_usd > 0

    def test_exceeds_budget(self):
        tracker = CostTracker(budget_usd=0.001)
        tracker.add(input_tokens=1_000_000, output_tokens=1_000_000, model="claude-opus-4-6")
        assert tracker.over_budget is True

    def test_within_budget(self):
        tracker = CostTracker(budget_usd=10.0)
        tracker.add(input_tokens=100, output_tokens=50, model="claude-sonnet-4-6")
        assert tracker.over_budget is False

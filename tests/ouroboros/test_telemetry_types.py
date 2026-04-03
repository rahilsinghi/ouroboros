"""Tests for TelemetryRecord dataclass."""
from __future__ import annotations

from ouroboros.telemetry.types import AgentTokens, TelemetryRecord


class TestTelemetryRecord:
    def test_creation(self):
        record = TelemetryRecord(
            run_id="2026-04-03T14-00-00_iter001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v1",
            observer_output='{"weakest_dimension": "real_world"}',
            strategist_output='{"hypothesis": "add docstrings"}',
            implementer_output='{"files_written": {}}',
            tokens_observer=AgentTokens(input=1000, output=200, cost_usd=0.01),
            tokens_strategist=AgentTokens(input=2000, output=400, cost_usd=0.02),
            tokens_implementer=AgentTokens(input=3000, output=600, cost_usd=0.06),
            files_changed=("ouroboros/types.py",),
            git_diff="+ added docstring",
            eval_score=0.12,
            outcome="MERGED",
            failure_reason="",
            traceback_output="",
            cost_usd=0.09,
            input_tokens=6000,
            output_tokens=1200,
        )
        assert record.run_id == "2026-04-03T14-00-00_iter001"
        assert record.iteration == 1
        assert record.tokens_observer.input == 1000

    def test_to_frontmatter(self):
        record = TelemetryRecord(
            run_id="test_001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v2",
            observer_output="{}",
            strategist_output="{}",
            implementer_output="{}",
            tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
            tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
            tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
            files_changed=(),
            git_diff="",
            eval_score=0.0,
            outcome="ABANDONED",
            failure_reason="empty JSON",
            traceback_output="",
            cost_usd=0.008,
            input_tokens=600,
            output_tokens=300,
        )
        fm = record.to_frontmatter()
        assert fm["run_id"] == "test_001"
        assert fm["prompt_implementer"] == "v2"
        assert fm["outcome"] == "ABANDONED"
        assert fm["tokens_observer_in"] == 100
        assert fm["cost_observer"] == 0.001

    def test_to_markdown_body(self):
        record = TelemetryRecord(
            run_id="test_001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v1",
            observer_output='{"key": "value"}',
            strategist_output='{"hyp": "test"}',
            implementer_output='{"files": {}}',
            tokens_observer=AgentTokens(input=0, output=0, cost_usd=0.0),
            tokens_strategist=AgentTokens(input=0, output=0, cost_usd=0.0),
            tokens_implementer=AgentTokens(input=0, output=0, cost_usd=0.0),
            files_changed=("a.py",),
            git_diff="diff content",
            eval_score=0.5,
            outcome="ROLLED_BACK",
            failure_reason="no improvement",
            traceback_output="some error",
            cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
        )
        body = record.to_markdown_body()
        assert "## Observation" in body
        assert '{"key": "value"}' in body
        assert "## Diff" in body
        assert "diff content" in body
        assert "## Traceback" in body
        assert "some error" in body

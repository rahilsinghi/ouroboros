from unittest.mock import MagicMock, patch
import json

import pytest

from ouroboros.agents.observer import ObserverAgent
from ouroboros.types import DimensionScore, ObservationReport, ScoreboardSnapshot, TraceEvent


class TestObserverAgent:
    def _make_snapshot(self, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=1, dimensions=dims)

    def _make_traces(self) -> list[TraceEvent]:
        return [
            TraceEvent("cli_run", "2026-04-02T00:00:00Z", {
                "prompt": "list files",
                "command": "python -m src.main route 'list files'",
                "stdout": "Routed to: GrepTool (wrong)",
                "returncode": 0,
                "duration_ms": 500,
                "tokens_used": 100,
            }),
        ]

    @patch("ouroboros.agents.observer.BaseAgent.call")
    def test_observe_returns_report(self, mock_call: MagicMock):
        mock_call.return_value = MagicMock(
            text=json.dumps({
                "weakest_dimension": "tool_selection",
                "current_score": 0.65,
                "failure_examples": ["list files routed to GrepTool instead of BashTool"],
                "patterns": ["filesystem commands misrouted to search tools"],
            }),
            input_tokens=500,
            output_tokens=200,
        )
        agent = ObserverAgent(model="claude-sonnet-4-6")
        report = agent.observe(
            scoreboard=self._make_snapshot(
                correctness=0.8, tool_selection=0.65, regression=1.0
            ),
            traces=self._make_traces(),
            ledger_summary="No previous iterations.",
        )
        assert isinstance(report, ObservationReport)
        assert report.weakest_dimension == "tool_selection"
        assert report.current_score == 0.65
        assert len(report.failure_examples) == 1
        assert len(report.patterns) == 1

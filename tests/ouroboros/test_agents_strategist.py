from unittest.mock import MagicMock, patch
import json

import pytest

from ouroboros.agents.strategist import StrategistAgent
from ouroboros.types import ChangePlan, FileChange, ObservationReport


class TestStrategistAgent:
    def _make_report(self) -> ObservationReport:
        return ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("list files routed to GrepTool instead of BashTool",),
            patterns=("filesystem commands misrouted to search tools",),
        )

    @patch("ouroboros.agents.strategist.BaseAgent.call")
    def test_strategize_returns_plan(self, mock_call: MagicMock):
        mock_call.return_value = MagicMock(
            text=json.dumps({
                "hypothesis": "Add keyword boosting for filesystem terms in _score()",
                "target_dimension": "tool_selection",
                "file_changes": [
                    {
                        "path": "src/runtime.py",
                        "action": "modify",
                        "description": "Add filesystem keyword boosting to _score()",
                    }
                ],
                "expected_impact": "tool_selection +10%",
            }),
            input_tokens=800,
            output_tokens=300,
        )
        agent = StrategistAgent(model="claude-opus-4-6")
        plan = agent.strategize(
            observation=self._make_report(),
            source_files={"src/runtime.py": "def _score(tokens, module):\n    ..."},
            ledger_summary="No previous attempts.",
        )
        assert isinstance(plan, ChangePlan)
        assert plan.hypothesis == "Add keyword boosting for filesystem terms in _score()"
        assert len(plan.file_changes) == 1
        assert plan.file_changes[0].path == "src/runtime.py"

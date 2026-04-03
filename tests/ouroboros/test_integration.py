"""End-to-end integration test — runs a single iteration with mocked LLM calls."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.config import OuroborosConfig
from ouroboros.loop import ImprovementLoop
from ouroboros.types import (
    ChangePlan,
    DimensionScore,
    FileChange,
    IterationOutcome,
    ObservationReport,
    ScoreboardSnapshot,
)


@pytest.fixture
def integration_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with claw-code-like structure."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "runtime.py").write_text(
        "def _score(tokens: set, module) -> int:\n"
        "    count = 0\n"
        "    name_tokens = set(module.name.lower().split())\n"
        "    count += len(tokens & name_tokens)\n"
        "    return count\n"
    )

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestIntegration:
    @patch("ouroboros.agents.base.BaseAgent.call")
    def test_full_iteration_merged(
        self,
        mock_call: MagicMock,
        integration_repo: Path,
    ):
        # Responses in call order: Observer, Strategist, Implementer
        new_code = (
            "def _score(tokens: set, module) -> int:\n"
            "    count = 0\n"
            "    name_tokens = set(module.name.lower().split())\n"
            "    hint_tokens = set(module.source_hint.lower().replace('/', ' ').replace('-', ' ').split())\n"
            "    count += len(tokens & name_tokens) * 2\n"
            "    count += len(tokens & hint_tokens)\n"
            "    return count\n"
        )
        mock_call.side_effect = [
            # Observer response
            MagicMock(
                text=json.dumps({
                    "weakest_dimension": "tool_selection",
                    "current_score": 0.65,
                    "failure_examples": ["list files routed wrong"],
                    "patterns": ["filesystem misrouted"],
                }),
                input_tokens=500,
                output_tokens=200,
            ),
            # Strategist response
            MagicMock(
                text=json.dumps({
                    "hypothesis": "Add source_hint matching to _score",
                    "target_dimension": "tool_selection",
                    "file_changes": [{"path": "src/runtime.py", "action": "modify", "description": "Add source_hint tokens"}],
                    "expected_impact": "+10%",
                }),
                input_tokens=800,
                output_tokens=300,
            ),
            # Implementer response
            MagicMock(
                text=json.dumps({"files_written": {"src/runtime.py": new_code}}),
                input_tokens=600,
                output_tokens=200,
            ),
        ]

        config = OuroborosConfig(
            max_iterations=1,
            cooldown_seconds=0,
            sandbox_timeout_seconds=30,
        )
        loop = ImprovementLoop(config=config, repo_root=integration_repo)

        # Mock scoreboard to show improvement
        with patch.object(loop, "_run_scoreboard") as mock_sb:
            mock_sb.side_effect = [
                ScoreboardSnapshot(0, (
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.65),
                    DimensionScore("regression", 1.0),
                )),
                ScoreboardSnapshot(1, (
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.76),
                    DimensionScore("regression", 1.0),
                )),
            ]
            result = loop.run()

        assert result.iterations_run == 1
        assert result.iterations_merged == 1
        assert result.iterations_rolled_back == 0

        # Verify the change was merged to main
        runtime_content = (integration_repo / "src" / "runtime.py").read_text()
        assert "source_hint" in runtime_content

        # Verify ledger was written
        from ouroboros.history.ledger import Ledger
        ledger = Ledger(base_dir=integration_repo / ".ouroboros" / "ledger")
        entries = ledger.read_all()
        assert len(entries) == 1
        assert entries[0].outcome == IterationOutcome.MERGED

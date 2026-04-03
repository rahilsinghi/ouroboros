import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.config import DEFAULT_CONFIG
from ouroboros.loop import ImprovementLoop, LoopResult
from ouroboros.types import (
    ChangePlan,
    DimensionScore,
    FileChange,
    IterationOutcome,
    ObservationReport,
    ScoreboardSnapshot,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    src = tmp_path / "src"
    src.mkdir()
    (src / "runtime.py").write_text("def _score(tokens, module):\n    return 0\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestImprovementLoop:
    @patch("ouroboros.loop.ObserverAgent")
    @patch("ouroboros.loop.StrategistAgent")
    @patch("ouroboros.loop.ImplementerAgent")
    def test_single_iteration_merged(
        self,
        mock_impl_cls: MagicMock,
        mock_strat_cls: MagicMock,
        mock_obs_cls: MagicMock,
        git_repo: Path,
    ):
        # Mock Observer
        mock_observer = MagicMock()
        mock_observer.observe.return_value = ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("example",),
            patterns=("pattern",),
        )
        mock_obs_cls.return_value = mock_observer

        # Mock Strategist
        mock_strategist = MagicMock()
        mock_strategist.strategize.return_value = ChangePlan(
            hypothesis="Improve scoring",
            target_dimension="tool_selection",
            file_changes=(FileChange("src/runtime.py", "modify", "Improve _score"),),
            expected_impact="+10%",
        )
        mock_strat_cls.return_value = mock_strategist

        # Mock Implementer
        mock_implementer = MagicMock()
        mock_implementer.implement.return_value = MagicMock(
            success=True, files_written=("src/runtime.py",), error=""
        )
        mock_impl_cls.return_value = mock_implementer

        config = DEFAULT_CONFIG.with_overrides({"max_iterations": 1})
        loop = ImprovementLoop(config=config, repo_root=git_repo)

        # Provide mock scoreboard that shows improvement
        with patch.object(loop, "_run_scoreboard") as mock_score:
            mock_score.side_effect = [
                # Baseline
                ScoreboardSnapshot(iteration=0, dimensions=(
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.65),
                    DimensionScore("regression", 1.0),
                )),
                # After improvement
                ScoreboardSnapshot(iteration=1, dimensions=(
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.75),
                    DimensionScore("regression", 1.0),
                )),
            ]
            result = loop.run()

        assert isinstance(result, LoopResult)
        assert result.iterations_run == 1
        assert result.iterations_merged >= 1

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.implementer import ImplementerAgent
from ouroboros.config import DEFAULT_CONFIG
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.types import ChangePlan, FileChange


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


class TestImplementerAgent:
    @patch("ouroboros.agents.implementer.BaseAgent.call")
    def test_implement_writes_to_worktree(self, mock_call: MagicMock, git_repo: Path):
        mock_call.return_value = MagicMock(
            text='{"files_written": {"src/runtime.py": "def _score(tokens, module):\\n    return len(tokens)\\n"}}',
            input_tokens=600,
            output_tokens=200,
        )
        plan = ChangePlan(
            hypothesis="Improve scoring",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="src/runtime.py", action="modify", description="Improve _score"),
            ),
            expected_impact="+10%",
        )
        executor = SandboxExecutor(config=DEFAULT_CONFIG)
        agent = ImplementerAgent(model="claude-opus-4-6", executor=executor)
        result = agent.implement(plan=plan, worktree_path=git_repo)
        assert result.success
        assert "src/runtime.py" in result.files_written

    @patch("ouroboros.agents.implementer.BaseAgent.call")
    def test_blocked_path_rejected(self, mock_call: MagicMock, git_repo: Path):
        mock_call.return_value = MagicMock(
            text='{"files_written": {"ouroboros/loop.py": "hacked"}}',
            input_tokens=100,
            output_tokens=50,
        )
        plan = ChangePlan(
            hypothesis="Hack the engine",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="ouroboros/loop.py", action="modify", description="Hack"),
            ),
            expected_impact="n/a",
        )
        executor = SandboxExecutor(config=DEFAULT_CONFIG)
        agent = ImplementerAgent(model="claude-opus-4-6", executor=executor)
        result = agent.implement(plan=plan, worktree_path=git_repo)
        assert not result.success
        assert "blocked" in result.error.lower()

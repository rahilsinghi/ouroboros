"""Tests for implementer pre-commit validation."""
from pathlib import Path
from unittest.mock import patch

from ouroboros.agents.implementer import ImplementerAgent
from ouroboros.config import OuroborosConfig
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.types import ChangePlan, FileChange


class TestPreCommitValidation:
    def setup_method(self):
        config = OuroborosConfig()
        self.executor = SandboxExecutor(config=config)
        self.agent = ImplementerAgent(model="test", executor=self.executor)

    def test_rejects_syntax_error(self, tmp_path: Path):
        """Files with syntax errors should not be committed."""
        plan = ChangePlan(
            hypothesis="test",
            target_dimension="code_quality",
            file_changes=(
                FileChange(path="src/broken.py", action="create", description="test"),
            ),
            expected_impact="test",
        )

        with patch.object(self.agent.agent, "call_with_json_retry") as mock_call:
            mock_call.return_value = {
                "files_written": {
                    "src/broken.py": "def broken(\n    return 42"
                }
            }
            result = self.agent.implement(plan=plan, worktree_path=tmp_path)

        assert result.success is False
        assert "syntax" in result.error.lower() or "SyntaxError" in result.error

    def test_accepts_valid_python(self, tmp_path: Path):
        """Valid Python files should pass validation."""
        plan = ChangePlan(
            hypothesis="test",
            target_dimension="code_quality",
            file_changes=(
                FileChange(path="src/good.py", action="create", description="test"),
            ),
            expected_impact="test",
        )

        with patch.object(self.agent.agent, "call_with_json_retry") as mock_call:
            mock_call.return_value = {
                "files_written": {
                    "src/good.py": "def add(a: int, b: int) -> int:\n    return a + b\n"
                }
            }
            # Also need to mock subprocess (git add/commit) since tmp_path isn't a git repo
            with patch("ouroboros.agents.implementer.subprocess.run"):
                result = self.agent.implement(plan=plan, worktree_path=tmp_path)

        assert result.success is True

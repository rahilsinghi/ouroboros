import pytest
from ouroboros.config import DEFAULT_CONFIG
from ouroboros.sandbox.executor import SandboxExecutor, CommandBlocked

@pytest.fixture
def executor() -> SandboxExecutor:
    return SandboxExecutor(config=DEFAULT_CONFIG)

class TestSandboxExecutor:
    def test_allowed_command_runs(self, executor: SandboxExecutor):
        result = executor.run("python -m src.main summary", cwd="/tmp")
        assert isinstance(result.returncode, int)

    def test_blocked_command_raises(self, executor: SandboxExecutor):
        with pytest.raises(CommandBlocked, match="not in allowlist"):
            executor.run("rm -rf /", cwd="/tmp")

    def test_partial_match_allowed(self, executor: SandboxExecutor):
        result = executor.run("python -m src.main route test --limit 3", cwd="/tmp")
        assert isinstance(result.returncode, int)

    def test_blocked_path_check(self, executor: SandboxExecutor):
        assert executor.is_path_blocked("ouroboros/agents/observer.py")
        assert executor.is_path_blocked("tests/test_foo.py")
        assert executor.is_path_blocked(".git/config")
        assert not executor.is_path_blocked("src/runtime.py")
        assert not executor.is_path_blocked("src/commands.py")

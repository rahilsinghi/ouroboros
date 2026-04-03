import subprocess
from pathlib import Path

import pytest

from ouroboros.sandbox.rollback import safe_rollback
from ouroboros.sandbox.worktree import WorktreeInfo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    (tmp_path / "f.txt").write_text("ok")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestSafeRollback:
    def test_rollback_cleans_worktree(self, git_repo: Path):
        wt_path = git_repo / ".worktrees" / "test-wt"
        subprocess.run(
            ["git", "-C", str(git_repo), "worktree", "add", str(wt_path), "-b", "test-branch"],
            check=True, capture_output=True,
        )
        info = WorktreeInfo(path=wt_path, branch="test-branch", iteration=1)
        assert wt_path.exists()
        safe_rollback(repo_root=git_repo, info=info)
        assert not wt_path.exists()

    def test_rollback_nonexistent_is_safe(self, git_repo: Path):
        info = WorktreeInfo(path=git_repo / "nonexistent", branch="nope", iteration=99)
        # Should not raise
        safe_rollback(repo_root=git_repo, info=info)

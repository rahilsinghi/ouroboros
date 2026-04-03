import subprocess
from pathlib import Path
import pytest
from ouroboros.sandbox.worktree import WorktreeManager, WorktreeInfo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestWorktreeManager:
    def test_create_worktree(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        assert info.path.exists()
        assert info.branch == "ouroboros/attempt-001"
        assert (info.path / "file.txt").read_text() == "hello"

    def test_create_multiple_worktrees(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info1 = mgr.create(iteration=1)
        info2 = mgr.create(iteration=2)
        assert info1.path != info2.path
        assert info1.branch != info2.branch

    def test_merge_worktree(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        (info.path / "file.txt").write_text("modified")
        subprocess.run(["git", "-C", str(info.path), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(info.path), "commit", "-m", "improve"], check=True, capture_output=True)
        mgr.merge(info)
        assert not info.path.exists()
        assert (git_repo / "file.txt").read_text() == "modified"

    def test_rollback_worktree(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        (info.path / "file.txt").write_text("bad change")
        mgr.rollback(info)
        assert not info.path.exists()
        assert (git_repo / "file.txt").read_text() == "hello"

    def test_get_diff(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        (info.path / "file.txt").write_text("modified")
        subprocess.run(["git", "-C", str(info.path), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(info.path), "commit", "-m", "improve"], check=True, capture_output=True)
        diff = mgr.get_diff(info)
        assert "modified" in diff

"""Git worktree management for isolated improvement attempts."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str
    iteration: int


class WorktreeManager:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.worktree_dir = repo_root / ".worktrees"

    def create(self, iteration: int) -> WorktreeInfo:
        branch = f"ouroboros/attempt-{iteration:03d}"
        wt_path = self.worktree_dir / f"ouroboros-attempt-{iteration:03d}"
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "-C", str(self.repo_root), "worktree", "add", str(wt_path), "-b", branch],
            check=True,
            capture_output=True,
        )
        return WorktreeInfo(path=wt_path, branch=branch, iteration=iteration)

    def merge(self, info: WorktreeInfo) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo_root), "merge", info.branch],
            check=True,
            capture_output=True,
        )
        self._cleanup(info)

    def rollback(self, info: WorktreeInfo) -> None:
        self._cleanup(info)

    def get_diff(self, info: WorktreeInfo) -> str:
        main_branch = self._get_main_branch()
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "diff", f"{main_branch}...{info.branch}"],
            capture_output=True,
            text=True,
        )
        return result.stdout

    def _cleanup(self, info: WorktreeInfo) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo_root), "worktree", "remove", str(info.path), "--force"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo_root), "branch", "-D", info.branch],
            capture_output=True,
        )

    def _get_main_branch(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

"""Safe rollback — clean up worktree and branch, never crash."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ouroboros.sandbox.worktree import WorktreeInfo


def safe_rollback(repo_root: Path, info: WorktreeInfo) -> None:
    """Attempt to remove a worktree and its branch. Never raises."""
    try:
        if info.path.exists():
            subprocess.run(
                ["git", "-C", str(repo_root), "worktree", "remove", str(info.path), "--force"],
                capture_output=True,
            )
    except Exception:
        pass

    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", "-D", info.branch],
            capture_output=True,
        )
    except Exception:
        pass

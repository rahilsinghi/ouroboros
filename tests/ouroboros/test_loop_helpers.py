"""Tests for loop helper methods."""
from pathlib import Path

from ouroboros.config import OuroborosConfig
from ouroboros.loop import ImprovementLoop


class TestReadTargetFiles:
    def test_excludes_blocked_paths(self, tmp_path: Path):
        """Files matching blocked_paths should not appear in source context."""
        target = tmp_path / "ouroboros"
        target.mkdir()
        (target / "__init__.py").write_text("")
        (target / "types.py").write_text("# allowed file")
        (target / "config.py").write_text("# blocked file")
        (target / "loop.py").write_text("# blocked file")

        config = OuroborosConfig(
            target_path="ouroboros/",
            sandbox_blocked_paths=("ouroboros/config.py", "ouroboros/loop.py"),
        )
        loop = ImprovementLoop.__new__(ImprovementLoop)
        loop.config = config
        loop.repo_root = tmp_path

        files = loop._read_target_files("code_quality")
        assert "ouroboros/types.py" in files
        assert "ouroboros/__init__.py" in files
        assert "ouroboros/config.py" not in files
        assert "ouroboros/loop.py" not in files

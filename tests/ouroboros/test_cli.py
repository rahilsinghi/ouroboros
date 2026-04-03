import subprocess
import sys

import pytest


class TestCLI:
    def test_help_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "ouroboros", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "ouroboros" in result.stdout.lower()

    def test_config_show_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "ouroboros", "config", "show"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "target_path" in result.stdout

    def test_scoreboard_runs_without_data(self):
        result = subprocess.run(
            [sys.executable, "-m", "ouroboros", "scoreboard"],
            capture_output=True,
            text=True,
        )
        # Should succeed even with no data
        assert result.returncode == 0

    def test_ledger_runs_without_data(self):
        result = subprocess.run(
            [sys.executable, "-m", "ouroboros", "ledger"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

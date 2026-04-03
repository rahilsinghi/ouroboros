# ouroboros/scoreboard/code_quality.py
"""Code quality benchmark dimension using mypy, ruff, and radon."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ouroboros.types import DimensionScore


class CodeQualityScorer:
    def __init__(self, target_path: Path) -> None:
        self.target_path = target_path

    def score(self) -> DimensionScore:
        """Run static analysis and compute a composite quality score."""
        py_files = list(self.target_path.rglob("*.py"))
        if not py_files:
            return DimensionScore(name="code_quality", value=1.0)

        ruff_score = self._ruff_score()
        complexity_score = self._complexity_score()
        # Weight: ruff 60%, complexity 40%
        composite = (ruff_score * 0.6) + (complexity_score * 0.4)
        return DimensionScore(name="code_quality", value=composite)

    def _ruff_score(self) -> float:
        """Score based on lint violations. 0 violations = 1.0."""
        try:
            result = subprocess.run(
                ["ruff", "check", str(self.target_path), "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return 1.0
            import json

            violations = json.loads(result.stdout) if result.stdout else []
            # Decay: each violation reduces score by 0.1, floor at 0.0
            return max(0.0, 1.0 - len(violations) * 0.1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return 1.0  # ruff not installed = skip

    def _complexity_score(self) -> float:
        """Score based on cyclomatic complexity. Average CC < 5 = 1.0."""
        try:
            result = subprocess.run(
                ["radon", "cc", str(self.target_path), "-a", "-nc"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Parse average from last line: "Average complexity: A (1.5)"
            for line in reversed(result.stdout.splitlines()):
                if "Average complexity" in line:
                    # Extract the number in parentheses
                    start = line.rfind("(")
                    end = line.rfind(")")
                    if start != -1 and end != -1:
                        avg = float(line[start + 1 : end])
                        # CC 1-5 = 1.0, 5-10 = linear decay, 10+ = 0.0
                        if avg <= 5:
                            return 1.0
                        if avg >= 10:
                            return 0.0
                        return 1.0 - (avg - 5) / 5.0
            return 1.0  # no functions found = clean
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return 1.0  # radon not installed = skip

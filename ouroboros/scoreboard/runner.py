# ouroboros/scoreboard/runner.py
"""Scoreboard runner and merge gate logic."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ouroboros.types import DimensionScore, ScoreboardSnapshot


@dataclass(frozen=True)
class MergeGate:
    regression_floor: float
    noise_tolerance: float

    def can_merge(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> bool:
        """Check if the after snapshot passes the merge gate relative to before."""
        # Hard requirement: regression must meet floor
        regression = after.get("regression")
        if regression is not None and regression.value < self.regression_floor:
            return False

        # Hard requirement: correctness never drops
        before_correctness = before.get("correctness")
        after_correctness = after.get("correctness")
        if before_correctness and after_correctness:
            if after_correctness.value < before_correctness.value:
                return False

        # At least one dimension must improve beyond noise
        improved = False
        for after_dim in after.dimensions:
            before_dim = before.get(after_dim.name)
            if before_dim is None:
                continue
            if after_dim.value > before_dim.value + self.noise_tolerance:
                improved = True

        if not improved:
            return False

        # No dimension regresses beyond noise (except new dimensions)
        for before_dim in before.dimensions:
            after_dim = after.get(before_dim.name)
            if after_dim is None:
                continue
            if after_dim.value < before_dim.value - self.noise_tolerance:
                return False

        return True


def can_merge(
    before: ScoreboardSnapshot,
    after: ScoreboardSnapshot,
    regression_floor: float = 1.0,
    noise_tolerance: float = 0.02,
) -> bool:
    """Convenience function for merge gate check."""
    gate = MergeGate(regression_floor=regression_floor, noise_tolerance=noise_tolerance)
    return gate.can_merge(before, after)


def run_scoreboard(
    target_path: Path,
    iteration: int = 0,
    test_command: str = "python -m pytest tests/ -v",
    baseline_tokens: int = 1000,
    previously_passing: set[str] | None = None,
) -> ScoreboardSnapshot:
    """Run all 6 scoreboard dimensions against a target path.

    Args:
        target_path: Root directory containing the code to evaluate.
        iteration: Current iteration number.
        test_command: Command to run tests for correctness/regression.
        baseline_tokens: Token baseline for efficiency scoring.
        previously_passing: Set of test names that passed in the previous iteration.
    """
    from ouroboros.scoreboard.code_quality import CodeQualityScorer
    from ouroboros.scoreboard.correctness import CorrectnessScorer
    from ouroboros.scoreboard.efficiency import EfficiencyScorer
    from ouroboros.scoreboard.regression import RegressionScorer

    dimensions: list[DimensionScore] = []

    # 1. Code Quality — ruff + radon
    cq_scorer = CodeQualityScorer(target_path=target_path)
    dimensions.append(cq_scorer.score())

    # 2. Correctness — run tests, count pass/fail
    test_results, total_tokens = _run_tests(target_path, test_command)
    correctness_scorer = CorrectnessScorer()
    dimensions.append(correctness_scorer.score(test_results))

    # 3. Efficiency — token count vs baseline
    efficiency_scorer = EfficiencyScorer(baseline_tokens=baseline_tokens)
    dimensions.append(efficiency_scorer.score(current_tokens=total_tokens))

    # 4. Regression — previously passing tests still pass
    regression_scorer = RegressionScorer()
    currently_passing = {name for name, passed in test_results.items() if passed}
    dimensions.append(regression_scorer.score(
        previously_passing or set(),
        currently_passing,
    ))

    # 5. Tool Selection — skip if no challenges file available at target
    # (will score 1.0 placeholder for now — real routing benchmarks need the CLI)
    dimensions.append(DimensionScore(name="tool_selection", value=1.0))

    # 6. Real World — skip LLM eval in automated runs (expensive)
    # Placeholder 0.5 — neither penalizes nor rewards
    dimensions.append(DimensionScore(name="real_world", value=0.5))

    return ScoreboardSnapshot(
        iteration=iteration,
        dimensions=tuple(dimensions),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _run_tests(target_path: Path, test_command: str) -> tuple[dict[str, bool], int]:
    """Run tests and parse results. Returns (test_results, approximate_token_count)."""
    try:
        result = subprocess.run(
            test_command.split() + ["--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(target_path),
        )
        stdout = result.stdout
        test_results: dict[str, bool] = {}

        for line in stdout.splitlines():
            if " PASSED" in line:
                test_name = line.split(" PASSED")[0].strip()
                test_results[test_name] = True
            elif " FAILED" in line:
                test_name = line.split(" FAILED")[0].strip()
                test_results[test_name] = False

        # Fallback: parse summary line "X passed, Y failed"
        if not test_results:
            import re

            for line in reversed(stdout.splitlines()):
                if "passed" in line:
                    m = re.search(r"(\d+) passed", line)
                    if m:
                        test_results["suite"] = True
                        break
                if "failed" in line or "error" in line:
                    test_results["suite"] = False
                    break

        # If still nothing, use exit code
        if not test_results:
            test_results["suite"] = result.returncode == 0

        # Token count: count source file characters as proxy for code size
        token_count = 0
        for py_file in target_path.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                try:
                    token_count += len(py_file.read_text())
                except OSError:
                    pass

        return test_results, token_count

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {"suite": False}, 0

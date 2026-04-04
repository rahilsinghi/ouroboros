"""Tournament runner — evaluate prompts against benchmark tasks."""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

from ouroboros.meta.benchmark_gen import BenchmarkTask


def score_task_result(code: str, expected_check: str, target_function: str) -> float:
    """Score a single task result using AST-based deterministic checks.

    Returns 1.0 (pass), 0.5 (partial), or 0.0 (fail).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0.0

    if expected_check == "ruff_clean":
        return _check_ruff_clean(code)

    if expected_check == "has_docstring":
        return _check_has_docstring(tree, target_function)

    if expected_check == "low_complexity":
        return _check_low_complexity(tree, target_function)

    return 0.0


def _check_ruff_clean(code: str) -> float:
    """Check if code has zero ruff violations."""
    ruff_bin = shutil.which("ruff") or str(Path(sys.executable).parent / "ruff")
    try:
        result = subprocess.run(
            [ruff_bin, "check", "--stdin-filename", "check.py", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return 1.0
        violations = len([l for l in result.stdout.splitlines() if l.strip()])
        return 0.5 if violations <= 1 else 0.0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0.5


def _check_has_docstring(tree: ast.AST, target_function: str) -> float:
    """Check if the target function has a docstring using AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == target_function:
                if ast.get_docstring(node):
                    return 1.0
                return 0.0
    return 0.0


def _check_low_complexity(tree: ast.AST, target_function: str) -> float:
    """Check if target function has low complexity by counting branches."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == target_function:
                branches = sum(
                    1
                    for child in ast.walk(node)
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler))
                )
                if branches <= 3:
                    return 1.0
                if branches <= 5:
                    return 0.5
                return 0.0
    return 0.0


class Tournament:
    """Run benchmark tasks against a prompt and compute aggregate score."""

    def __init__(self, tasks: list[BenchmarkTask], worktree_path: Path) -> None:
        self.tasks = tasks
        self.worktree_path = worktree_path

    def run(self, agent_callable: object) -> float:
        """Run all tasks and return mean score.

        agent_callable: a function(task_description, setup_code) -> modified_code
        """
        if not self.tasks:
            return 0.0
        scores = []
        for task in self.tasks:
            try:
                result_code = agent_callable(task.description, task.setup_file)
                score = score_task_result(result_code, task.expected_check, task.target_function)
            except Exception:
                score = 0.0
            scores.append(score)
        return sum(scores) / len(scores)

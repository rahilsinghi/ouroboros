"""Real-world benchmark dimension — docstring coverage as code quality proxy."""
from __future__ import annotations

import ast
from pathlib import Path

from ouroboros.types import DimensionScore


class RealWorldScorer:
    """Score based on docstring coverage of public functions/classes/methods."""

    def __init__(self, target_path: Path) -> None:
        self.target_path = target_path

    def score(self) -> DimensionScore:
        """Score = fraction of public callables that have docstrings."""
        total = 0
        documented = 0

        for py_file in self.target_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name.startswith("_"):
                        continue
                    total += 1
                    if ast.get_docstring(node):
                        documented += 1

        if total == 0:
            return DimensionScore(name="real_world", value=1.0)
        return DimensionScore(name="real_world", value=documented / total)

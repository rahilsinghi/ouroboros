"""Benchmark task definitions and rotating task generation."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class BenchmarkTask:
    """A single benchmark task for tournament evaluation."""

    name: str
    task_type: str  # "core" or "rotating"
    description: str
    setup_file: str
    setup_path: str
    expected_check: str  # "ruff_clean", "has_docstring", "low_complexity"
    target_function: str = ""
    target_dimension: str = ""


def load_benchmark_tasks(benchmark_dir: Path) -> list[BenchmarkTask]:
    """Load benchmark tasks from YAML files in a directory."""
    if not benchmark_dir.exists():
        return []
    tasks = []
    for yaml_file in sorted(benchmark_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_file.read_text())
        if raw is None:
            continue
        tasks.append(BenchmarkTask(
            name=raw["name"],
            task_type=raw.get("type", "core"),
            description=raw.get("description", ""),
            setup_file=raw.get("setup_file", ""),
            setup_path=raw.get("setup_path", ""),
            expected_check=raw.get("expected_check", ""),
            target_function=raw.get("target_function", ""),
            target_dimension=raw.get("target_dimension", ""),
        ))
    return tasks


class BenchmarkGenerator:
    """Generate rotating benchmark tasks from the current codebase."""

    def __init__(self, target_path: Path) -> None:
        self.target_path = target_path

    def generate_rotating(self, count: int = 2) -> list[BenchmarkTask]:
        """Find undocumented public functions and generate add-docstring tasks."""
        candidates: list[tuple[str, str, str]] = []

        for py_file in sorted(self.target_path.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            try:
                source = py_file.read_text()
                tree = ast.parse(source)
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("_"):
                        continue
                    if not ast.get_docstring(node):
                        rel_path = str(py_file.relative_to(self.target_path.parent))
                        candidates.append((rel_path, node.name, source))

        tasks = []
        for file_path, func_name, source in candidates[:count]:
            tasks.append(BenchmarkTask(
                name=f"docstring_{func_name}",
                task_type="rotating",
                description=f"Add a docstring to the public function {func_name}() in {file_path}.",
                setup_file=source,
                setup_path=file_path,
                expected_check="has_docstring",
                target_function=func_name,
                target_dimension="real_world",
            ))
        return tasks

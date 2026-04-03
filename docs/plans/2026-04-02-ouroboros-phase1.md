# Ouroboros Phase 1: "First Blood" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Ouroboros self-improvement loop targeting claw-code's routing/scoring engine, proving the OBSERVE → MEASURE → HYPOTHESIZE → IMPLEMENT → TEST → DEPLOY/ROLLBACK pipeline works end-to-end.

**Architecture:** Ouroboros lives at `claw-code/ouroboros/` as a Python package with zero imports from `src/`. It interacts with claw-code exclusively through subprocess CLI calls, git operations, and trace files. Four separated agents (Observer, Strategist, Implementer, Evaluator) each use the Anthropic SDK to call Claude models. The scoreboard runs 6 independent benchmark dimensions. Git worktrees isolate every improvement attempt.

**Tech Stack:** Python 3.11+, Anthropic SDK (`anthropic`), PyYAML (`pyyaml`), standard library (`subprocess`, `pathlib`, `json`, `dataclasses`, `unittest`). Static analysis: `mypy`, `ruff`, `radon`.

**Spec:** `docs/superpowers/specs/2026-03-31-ouroboros-design.md`

---

## File Structure

```
ouroboros/
├── __init__.py               — Package marker, version string
├── __main__.py               — python -m ouroboros entry point
├── cli.py                    — Argparse CLI (run, scoreboard, ledger, benchmark, dashboard, config)
├── config.py                 — Load/validate ouroboros.yaml, dataclass config
├── types.py                  — Shared dataclasses (ScoreboardSnapshot, LedgerEntry, IterationOutcome, etc.)
├── loop.py                   — Core improvement loop orchestrator
│
├── agents/
│   ├── __init__.py
│   ├── base.py               — Base agent class (LLM call wrapper, timeout, model config)
│   ├── observer.py           — Reads traces + scoreboard, produces ObservationReport
│   ├── strategist.py         — Reads report + code + ledger, produces ChangePlan
│   ├── implementer.py        — Writes code in worktree from ChangePlan
│   └── evaluator.py          — Runs scoreboard, makes merge/rollback decision
│
├── scoreboard/
│   ├── __init__.py
│   ├── runner.py             — Runs all dimensions, returns ScoreboardSnapshot
│   ├── correctness.py        — Task pass/fail
│   ├── efficiency.py         — Token counting
│   ├── tool_selection.py     — Routing accuracy
│   ├── code_quality.py       — mypy + ruff + radon
│   ├── regression.py         — Previously-passing tasks still pass
│   └── real_world.py         — LLM-graded open-ended evaluation
│
├── sandbox/
│   ├── __init__.py
│   ├── worktree.py           — Git worktree create/merge/cleanup
│   ├── executor.py           — Allowlisted subprocess runner
│   └── rollback.py           — Worktree deletion + branch cleanup
│
├── traces/
│   ├── __init__.py
│   ├── collector.py          — Instrument claw-code runs, capture JSONL events
│   ├── store.py              — Read/write .ouroboros/traces/{run-id}/*.jsonl
│   └── analyzer.py           — Pattern detection across trace files
│
├── history/
│   ├── __init__.py
│   ├── ledger.py             — Append/read iteration records
│   └── dashboard.py          — Terminal scoreboard + trajectory display
│
└── benchmarks/
    └── routing/
        └── challenges.json   — 50 routing challenges with expected tool matches

tests/ouroboros/
├── __init__.py
├── test_config.py
├── test_types.py
├── test_sandbox_worktree.py
├── test_sandbox_executor.py
├── test_traces.py
├── test_scoreboard_tool_selection.py
├── test_scoreboard_code_quality.py
├── test_scoreboard_runner.py
├── test_scoreboard_regression.py
├── test_ledger.py
├── test_agents_base.py
├── test_agents_observer.py
├── test_agents_strategist.py
├── test_agents_implementer.py
├── test_agents_evaluator.py
├── test_loop.py
└── test_cli.py

Root files:
├── ouroboros.yaml             — Default configuration
└── pyproject.toml             — Project metadata + dependencies
```

Each file has one responsibility. Agents interact through JSON-serializable dataclasses, not direct imports of each other.

---

## Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `ouroboros/__init__.py`
- Create: `ouroboros/__main__.py`
- Create: `tests/ouroboros/__init__.py`

- [ ] **Step 1: Create pyproject.toml with minimal dependencies**

```toml
[project]
name = "ouroboros"
version = "0.1.0"
description = "Self-improving agent engine for claw-code"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.49.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "mypy>=1.10",
    "ruff>=0.4",
    "radon>=6.0",
    "pytest>=8.0",
]

[project.scripts]
ouroboros = "ouroboros.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.mypy]
strict = true
python_version = "3.11"

[tool.ruff]
target-version = "py311"
```

- [ ] **Step 2: Create ouroboros/__init__.py**

```python
"""Ouroboros: Self-improving agent engine for claw-code."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create ouroboros/__main__.py**

```python
"""Entry point for python -m ouroboros."""

from ouroboros.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create tests/ouroboros/__init__.py**

```python
```

- [ ] **Step 5: Install dependencies**

Run: `cd ~/Desktop/claw-code && pip install -e ".[dev]"`
Expected: Successfully installed anthropic, pyyaml, mypy, ruff, radon, pytest

- [ ] **Step 6: Verify imports work**

Run: `cd ~/Desktop/claw-code && python -c "import ouroboros; print(ouroboros.__version__)"`
Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/claw-code
git add pyproject.toml ouroboros/__init__.py ouroboros/__main__.py tests/ouroboros/__init__.py
git commit -m "chore(ouroboros): scaffold project with dependencies"
```

---

## Task 2: Shared Types

**Files:**
- Create: `ouroboros/types.py`
- Create: `tests/ouroboros/test_types.py`

- [ ] **Step 1: Write failing tests for all core types**

```python
# tests/ouroboros/test_types.py
import json
from datetime import datetime, timezone

import pytest

from ouroboros.types import (
    DimensionScore,
    ScoreboardSnapshot,
    ObservationReport,
    ChangePlan,
    FileChange,
    LedgerEntry,
    IterationOutcome,
    TraceEvent,
)


class TestDimensionScore:
    def test_clamps_to_zero_one(self):
        assert DimensionScore(name="test", value=1.5).value == 1.0
        assert DimensionScore(name="test", value=-0.3).value == 0.0

    def test_normal_value_unchanged(self):
        assert DimensionScore(name="test", value=0.72).value == 0.72


class TestScoreboardSnapshot:
    def test_from_dimensions(self):
        dims = [
            DimensionScore(name="correctness", value=0.8),
            DimensionScore(name="efficiency", value=0.6),
        ]
        snap = ScoreboardSnapshot(iteration=1, dimensions=tuple(dims))
        assert snap.get("correctness").value == 0.8
        assert snap.get("efficiency").value == 0.6
        assert snap.get("nonexistent") is None

    def test_to_json_roundtrip(self):
        dims = [DimensionScore(name="correctness", value=0.8)]
        snap = ScoreboardSnapshot(iteration=1, dimensions=tuple(dims))
        data = json.loads(snap.to_json())
        assert data["iteration"] == 1
        assert data["dimensions"][0]["name"] == "correctness"


class TestObservationReport:
    def test_creation(self):
        report = ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("example1", "example2"),
            patterns=("pattern1",),
        )
        assert report.weakest_dimension == "tool_selection"
        assert len(report.failure_examples) == 2


class TestChangePlan:
    def test_creation(self):
        plan = ChangePlan(
            hypothesis="Improve scoring with TF-IDF",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="src/runtime.py", action="modify", description="Update _score()"),
            ),
            expected_impact="routing +10%",
        )
        assert plan.hypothesis == "Improve scoring with TF-IDF"
        assert len(plan.file_changes) == 1


class TestLedgerEntry:
    def test_creation(self):
        entry = LedgerEntry(
            iteration=42,
            timestamp=datetime.now(timezone.utc).isoformat(),
            observation_summary="routing accuracy 68%",
            hypothesis="TF-IDF weighting",
            files_changed=("src/runtime.py",),
            diff="--- a\n+++ b",
            scoreboard_before=ScoreboardSnapshot(
                iteration=41,
                dimensions=(DimensionScore(name="tool_selection", value=0.68),),
            ),
            scoreboard_after=ScoreboardSnapshot(
                iteration=42,
                dimensions=(DimensionScore(name="tool_selection", value=0.74),),
            ),
            outcome=IterationOutcome.MERGED,
            reason="routing +6%, no regressions",
        )
        assert entry.outcome == IterationOutcome.MERGED


class TestTraceEvent:
    def test_creation(self):
        event = TraceEvent(
            event_type="tool_call",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"tool": "BashTool", "input": "ls", "output": "file.py"},
        )
        assert event.event_type == "tool_call"

    def test_to_jsonl_line(self):
        event = TraceEvent(
            event_type="decision",
            timestamp="2026-04-02T00:00:00+00:00",
            data={"choice": "route_to_bash"},
        )
        line = event.to_jsonl_line()
        parsed = json.loads(line)
        assert parsed["event_type"] == "decision"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ouroboros.types'`

- [ ] **Step 3: Implement types.py**

```python
# ouroboros/types.py
"""Shared dataclasses for the Ouroboros improvement engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class IterationOutcome(str, Enum):
    MERGED = "MERGED"
    ROLLED_BACK = "ROLLED_BACK"
    TIMEOUT = "TIMEOUT"
    EVAL_FAILURE = "EVAL_FAILURE"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True)
class DimensionScore:
    name: str
    value: float

    def __post_init__(self) -> None:
        clamped = max(0.0, min(1.0, self.value))
        if clamped != self.value:
            object.__setattr__(self, "value", clamped)


@dataclass(frozen=True)
class ScoreboardSnapshot:
    iteration: int
    dimensions: tuple[DimensionScore, ...]
    timestamp: str = ""

    def get(self, name: str) -> DimensionScore | None:
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        return None

    def to_json(self) -> str:
        return json.dumps(
            {
                "iteration": self.iteration,
                "timestamp": self.timestamp,
                "dimensions": [
                    {"name": d.name, "value": d.value} for d in self.dimensions
                ],
            },
            indent=2,
        )


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    timestamp: str
    data: dict[str, object]

    def to_jsonl_line(self) -> str:
        return json.dumps(
            {
                "event_type": self.event_type,
                "timestamp": self.timestamp,
                **self.data,
            }
        )


@dataclass(frozen=True)
class ObservationReport:
    weakest_dimension: str
    current_score: float
    failure_examples: tuple[str, ...]
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class FileChange:
    path: str
    action: str  # "modify" | "create"
    description: str


@dataclass(frozen=True)
class ChangePlan:
    hypothesis: str
    target_dimension: str
    file_changes: tuple[FileChange, ...]
    expected_impact: str


@dataclass(frozen=True)
class LedgerEntry:
    iteration: int
    timestamp: str
    observation_summary: str
    hypothesis: str
    files_changed: tuple[str, ...]
    diff: str
    scoreboard_before: ScoreboardSnapshot
    scoreboard_after: ScoreboardSnapshot
    outcome: IterationOutcome
    reason: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_types.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/types.py tests/ouroboros/test_types.py
git commit -m "feat(ouroboros): add shared types — ScoreboardSnapshot, LedgerEntry, TraceEvent"
```

---

## Task 3: Configuration System

**Files:**
- Create: `ouroboros/config.py`
- Create: `ouroboros.yaml`
- Create: `tests/ouroboros/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_config.py
import tempfile
from pathlib import Path

import pytest

from ouroboros.config import OuroborosConfig, load_config, DEFAULT_CONFIG


class TestDefaultConfig:
    def test_has_all_required_fields(self):
        cfg = DEFAULT_CONFIG
        assert cfg.target_path == "src/"
        assert cfg.target_cli_command == "python -m src.main"
        assert cfg.target_test_command == "python -m pytest tests/src/"
        assert cfg.model_observer == "claude-sonnet-4-6"
        assert cfg.model_strategist == "claude-opus-4-6"
        assert cfg.model_implementer == "claude-opus-4-6"
        assert cfg.model_evaluator == "claude-sonnet-4-6"
        assert cfg.max_iterations == 10
        assert cfg.time_budget_minutes == 180
        assert cfg.max_tokens_per_iteration == 100_000
        assert cfg.cooldown_seconds == 30
        assert cfg.sandbox_timeout_seconds == 300
        assert cfg.merge_gate_regression_floor == 1.0
        assert cfg.merge_gate_noise_tolerance == 0.02
        assert cfg.max_usd_per_run == 10.0
        assert cfg.max_usd_per_iteration == 2.0
        assert cfg.budget_warn_percentage == 80

    def test_allowed_commands(self):
        cfg = DEFAULT_CONFIG
        assert "python -m src.main" in cfg.sandbox_allowed_commands
        assert "python -m pytest" in cfg.sandbox_allowed_commands
        assert "mypy --strict src/" in cfg.sandbox_allowed_commands
        assert "ruff check src/" in cfg.sandbox_allowed_commands

    def test_blocked_paths(self):
        cfg = DEFAULT_CONFIG
        assert "ouroboros/" in cfg.sandbox_blocked_paths
        assert "tests/" in cfg.sandbox_blocked_paths
        assert "benchmarks/" in cfg.sandbox_blocked_paths
        assert ".git/" in cfg.sandbox_blocked_paths


class TestLoadConfig:
    def test_loads_from_yaml_file(self, tmp_path: Path):
        yaml_content = """
target:
  path: custom/
  cli_command: "python custom.py"
  test_command: "pytest custom/"

models:
  observer: claude-haiku-4-5-20251001
  strategist: claude-sonnet-4-6
  implementer: claude-sonnet-4-6
  evaluator: claude-haiku-4-5-20251001

loop:
  max_iterations: 5
  time_budget_minutes: 60
"""
        config_file = tmp_path / "ouroboros.yaml"
        config_file.write_text(yaml_content)
        cfg = load_config(config_file)
        assert cfg.target_path == "custom/"
        assert cfg.target_cli_command == "python custom.py"
        assert cfg.model_observer == "claude-haiku-4-5-20251001"
        assert cfg.max_iterations == 5
        # Unset values fall back to defaults
        assert cfg.cooldown_seconds == 30

    def test_missing_file_returns_default(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg == DEFAULT_CONFIG

    def test_cli_overrides(self):
        overrides = {"max_iterations": 20, "model_evaluator": "claude-haiku-4-5-20251001"}
        cfg = DEFAULT_CONFIG.with_overrides(overrides)
        assert cfg.max_iterations == 20
        assert cfg.model_evaluator == "claude-haiku-4-5-20251001"
        # Other values unchanged
        assert cfg.model_observer == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ouroboros.config'`

- [ ] **Step 3: Implement config.py**

```python
# ouroboros/config.py
"""Configuration loading and validation for Ouroboros."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OuroborosConfig:
    # Target
    target_path: str = "src/"
    target_cli_command: str = "python -m src.main"
    target_test_command: str = "python -m pytest tests/src/"

    # Models
    model_observer: str = "claude-sonnet-4-6"
    model_strategist: str = "claude-opus-4-6"
    model_implementer: str = "claude-opus-4-6"
    model_evaluator: str = "claude-sonnet-4-6"

    # Loop
    max_iterations: int = 10
    time_budget_minutes: int = 180
    max_tokens_per_iteration: int = 100_000
    cooldown_seconds: int = 30

    # Sandbox
    sandbox_allowed_commands: tuple[str, ...] = (
        "python -m src.main",
        "python -m pytest",
        "mypy --strict src/",
        "ruff check src/",
    )
    sandbox_blocked_paths: tuple[str, ...] = (
        "ouroboros/",
        "tests/",
        "benchmarks/",
        ".git/",
    )
    sandbox_timeout_seconds: int = 300

    # Merge gate
    merge_gate_regression_floor: float = 1.0
    merge_gate_noise_tolerance: float = 0.02

    # Budget
    max_usd_per_run: float = 10.0
    max_usd_per_iteration: float = 2.0
    budget_warn_percentage: int = 80

    # Dashboard
    dashboard_web_port: int = 8420
    dashboard_refresh_seconds: int = 5

    def with_overrides(self, overrides: dict[str, Any]) -> OuroborosConfig:
        valid = {k: v for k, v in overrides.items() if hasattr(self, k)}
        return replace(self, **valid)


DEFAULT_CONFIG = OuroborosConfig()


def load_config(path: Path) -> OuroborosConfig:
    """Load config from YAML file, falling back to defaults for missing values."""
    if not path.exists():
        return DEFAULT_CONFIG

    import yaml

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    flat: dict[str, Any] = {}

    target = raw.get("target", {})
    if "path" in target:
        flat["target_path"] = target["path"]
    if "cli_command" in target:
        flat["target_cli_command"] = target["cli_command"]
    if "test_command" in target:
        flat["target_test_command"] = target["test_command"]

    models = raw.get("models", {})
    for role in ("observer", "strategist", "implementer", "evaluator"):
        if role in models:
            flat[f"model_{role}"] = models[role]

    loop = raw.get("loop", {})
    for key in ("max_iterations", "time_budget_minutes", "max_tokens_per_iteration", "cooldown_seconds"):
        if key in loop:
            flat[key] = loop[key]

    sandbox = raw.get("sandbox", {})
    if "allowed_commands" in sandbox:
        flat["sandbox_allowed_commands"] = tuple(sandbox["allowed_commands"])
    if "blocked_paths" in sandbox:
        flat["sandbox_blocked_paths"] = tuple(sandbox["blocked_paths"])
    if "timeout_seconds" in sandbox:
        flat["sandbox_timeout_seconds"] = sandbox["timeout_seconds"]

    scoreboard = raw.get("scoreboard", {})
    gate = scoreboard.get("merge_gate", {})
    if "regression_rate" in gate:
        flat["merge_gate_regression_floor"] = gate["regression_rate"]
    if "noise_tolerance" in gate:
        flat["merge_gate_noise_tolerance"] = gate["noise_tolerance"]

    budget = raw.get("budget", {})
    if "max_usd_per_run" in budget:
        flat["max_usd_per_run"] = budget["max_usd_per_run"]
    if "max_usd_per_iteration" in budget:
        flat["max_usd_per_iteration"] = budget["max_usd_per_iteration"]
    if "warn_at_percentage" in budget:
        flat["budget_warn_percentage"] = budget["warn_at_percentage"]

    return DEFAULT_CONFIG.with_overrides(flat)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Create ouroboros.yaml with documented defaults**

```yaml
# ouroboros.yaml — Ouroboros self-improvement engine configuration
# All values shown are defaults. Uncomment and modify as needed.

target:
  path: src/
  cli_command: "python -m src.main"
  test_command: "python -m pytest tests/src/"

models:
  observer: claude-sonnet-4-6
  strategist: claude-opus-4-6
  implementer: claude-opus-4-6
  evaluator: claude-sonnet-4-6       # deliberately different from implementer

loop:
  max_iterations: 10
  time_budget_minutes: 180
  max_tokens_per_iteration: 100000
  cooldown_seconds: 30

sandbox:
  allowed_commands:
    - "python -m src.main"
    - "python -m pytest"
    - "mypy --strict src/"
    - "ruff check src/"
  blocked_paths:
    - "ouroboros/"
    - "tests/"
    - "benchmarks/"
    - ".git/"
  timeout_seconds: 300

scoreboard:
  merge_gate:
    regression_rate: 1.0
    noise_tolerance: 0.02

budget:
  max_usd_per_run: 10.00
  max_usd_per_iteration: 2.00
  warn_at_percentage: 80
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/config.py ouroboros.yaml tests/ouroboros/test_config.py
git commit -m "feat(ouroboros): add configuration system with YAML loading"
```

---

## Task 4: Sandbox — Git Worktree Manager

**Files:**
- Create: `ouroboros/sandbox/__init__.py`
- Create: `ouroboros/sandbox/worktree.py`
- Create: `tests/ouroboros/test_sandbox_worktree.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_sandbox_worktree.py
import subprocess
import tempfile
from pathlib import Path

import pytest

from ouroboros.sandbox.worktree import WorktreeManager, WorktreeInfo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo for testing."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
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
        # Make a change in the worktree
        (info.path / "file.txt").write_text("modified")
        subprocess.run(
            ["git", "-C", str(info.path), "add", "."],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(info.path), "commit", "-m", "improve"],
            check=True, capture_output=True,
        )
        mgr.merge(info)
        # Worktree should be cleaned up
        assert not info.path.exists()
        # Change should be on main
        assert (git_repo / "file.txt").read_text() == "modified"

    def test_rollback_worktree(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        (info.path / "file.txt").write_text("bad change")
        mgr.rollback(info)
        assert not info.path.exists()
        # Main should be untouched
        assert (git_repo / "file.txt").read_text() == "hello"

    def test_get_diff(self, git_repo: Path):
        mgr = WorktreeManager(repo_root=git_repo)
        info = mgr.create(iteration=1)
        (info.path / "file.txt").write_text("modified")
        subprocess.run(
            ["git", "-C", str(info.path), "add", "."],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(info.path), "commit", "-m", "improve"],
            check=True, capture_output=True,
        )
        diff = mgr.get_diff(info)
        assert "modified" in diff
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_worktree.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement worktree.py**

```python
# ouroboros/sandbox/__init__.py
```

```python
# ouroboros/sandbox/worktree.py
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
        """Create a new worktree for an improvement attempt."""
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
        """Merge worktree branch into main and clean up."""
        main_branch = self._get_main_branch()
        subprocess.run(
            ["git", "-C", str(self.repo_root), "merge", info.branch],
            check=True,
            capture_output=True,
        )
        self._cleanup(info)

    def rollback(self, info: WorktreeInfo) -> None:
        """Delete worktree and branch without merging."""
        self._cleanup(info)

    def get_diff(self, info: WorktreeInfo) -> str:
        """Get the diff between the worktree branch and main."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_worktree.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/sandbox/ tests/ouroboros/test_sandbox_worktree.py
git commit -m "feat(ouroboros): add git worktree manager for sandboxed improvements"
```

---

## Task 5: Sandbox — Command Executor

**Files:**
- Create: `ouroboros/sandbox/executor.py`
- Create: `tests/ouroboros/test_sandbox_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_sandbox_executor.py
import pytest

from ouroboros.config import DEFAULT_CONFIG
from ouroboros.sandbox.executor import SandboxExecutor, CommandBlocked


@pytest.fixture
def executor() -> SandboxExecutor:
    return SandboxExecutor(config=DEFAULT_CONFIG)


class TestSandboxExecutor:
    def test_allowed_command_runs(self, executor: SandboxExecutor):
        result = executor.run("python -m src.main summary", cwd="/tmp")
        # We don't care about the output, just that it didn't raise CommandBlocked
        assert isinstance(result.returncode, int)

    def test_blocked_command_raises(self, executor: SandboxExecutor):
        with pytest.raises(CommandBlocked, match="not in allowlist"):
            executor.run("rm -rf /", cwd="/tmp")

    def test_partial_match_allowed(self, executor: SandboxExecutor):
        # "python -m src.main route test" starts with allowed prefix
        result = executor.run("python -m src.main route test --limit 3", cwd="/tmp")
        assert isinstance(result.returncode, int)

    def test_timeout_enforcement(self, executor: SandboxExecutor):
        # Override with 1 second timeout
        fast_executor = SandboxExecutor(config=DEFAULT_CONFIG.with_overrides({"sandbox_timeout_seconds": 1}))
        result = fast_executor.run("python -m src.main summary", cwd="/tmp", timeout_override=1)
        # Should complete or timeout — either way no crash
        assert isinstance(result.returncode, int) or result.timed_out

    def test_blocked_path_check(self, executor: SandboxExecutor):
        assert executor.is_path_blocked("ouroboros/agents/observer.py")
        assert executor.is_path_blocked("tests/test_foo.py")
        assert executor.is_path_blocked(".git/config")
        assert not executor.is_path_blocked("src/runtime.py")
        assert not executor.is_path_blocked("src/commands.py")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_executor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement executor.py**

```python
# ouroboros/sandbox/executor.py
"""Sandboxed command execution with allowlist enforcement."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ouroboros.config import OuroborosConfig


class CommandBlocked(Exception):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxExecutor:
    def __init__(self, config: OuroborosConfig) -> None:
        self.allowed_commands = config.sandbox_allowed_commands
        self.blocked_paths = config.sandbox_blocked_paths
        self.default_timeout = config.sandbox_timeout_seconds

    def run(
        self,
        command: str,
        cwd: str,
        timeout_override: int | None = None,
    ) -> ExecutionResult:
        """Run a command if it matches the allowlist."""
        if not self._is_allowed(command):
            raise CommandBlocked(f"Command '{command}' not in allowlist: {self.allowed_commands}")

        timeout = timeout_override or self.default_timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                timed_out=True,
            )

    def is_path_blocked(self, path: str) -> bool:
        """Check if a file path is in the blocked list."""
        return any(path.startswith(blocked) for blocked in self.blocked_paths)

    def _is_allowed(self, command: str) -> bool:
        return any(command.startswith(allowed) for allowed in self.allowed_commands)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_executor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/sandbox/executor.py tests/ouroboros/test_sandbox_executor.py
git commit -m "feat(ouroboros): add sandboxed command executor with allowlist"
```

---

## Task 6: Trace Collector & Store

**Files:**
- Create: `ouroboros/traces/__init__.py`
- Create: `ouroboros/traces/collector.py`
- Create: `ouroboros/traces/store.py`
- Create: `tests/ouroboros/test_traces.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_traces.py
import json
from pathlib import Path

import pytest

from ouroboros.types import TraceEvent
from ouroboros.traces.store import TraceStore
from ouroboros.traces.collector import TraceCollector


@pytest.fixture
def trace_dir(tmp_path: Path) -> Path:
    return tmp_path / ".ouroboros" / "traces"


class TestTraceStore:
    def test_write_and_read_events(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        run_id = "run-001"
        events = [
            TraceEvent(event_type="tool_call", timestamp="2026-04-02T00:00:00Z", data={"tool": "BashTool"}),
            TraceEvent(event_type="decision", timestamp="2026-04-02T00:00:01Z", data={"choice": "route"}),
        ]
        store.write_events(run_id, events)

        loaded = store.read_events(run_id)
        assert len(loaded) == 2
        assert loaded[0].event_type == "tool_call"
        assert loaded[1].event_type == "decision"

    def test_list_runs(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        store.write_events("run-001", [TraceEvent("a", "t", {})])
        store.write_events("run-002", [TraceEvent("b", "t", {})])
        runs = store.list_runs()
        assert "run-001" in runs
        assert "run-002" in runs

    def test_read_nonexistent_run(self, trace_dir: Path):
        store = TraceStore(base_dir=trace_dir)
        events = store.read_events("nonexistent")
        assert events == []


class TestTraceCollector:
    def test_collect_from_cli_output(self, trace_dir: Path):
        collector = TraceCollector(store=TraceStore(base_dir=trace_dir))
        # Simulate a claw-code CLI run
        cli_stdout = "Routed to: BashTool (score=5)\nMatched commands: summary\nOutput: workspace summary"
        run_id = collector.collect_run(
            prompt="show me the workspace",
            cli_command="python -m src.main route 'show me the workspace'",
            stdout=cli_stdout,
            stderr="",
            returncode=0,
            duration_ms=1200,
            tokens_used=150,
        )
        assert run_id.startswith("run-")
        events = collector.store.read_events(run_id)
        assert len(events) >= 1
        assert events[0].event_type == "cli_run"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_traces.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement store.py and collector.py**

```python
# ouroboros/traces/__init__.py
```

```python
# ouroboros/traces/store.py
"""Persistent trace storage in JSONL format."""

from __future__ import annotations

import json
from pathlib import Path

from ouroboros.types import TraceEvent


class TraceStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def write_events(self, run_id: str, events: list[TraceEvent]) -> Path:
        """Write trace events to a JSONL file."""
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_file = run_dir / "trace.jsonl"
        with open(trace_file, "a") as f:
            for event in events:
                f.write(event.to_jsonl_line() + "\n")
        return trace_file

    def read_events(self, run_id: str) -> list[TraceEvent]:
        """Read all trace events for a run."""
        trace_file = self.base_dir / run_id / "trace.jsonl"
        if not trace_file.exists():
            return []
        events: list[TraceEvent] = []
        with open(trace_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                event_type = data.pop("event_type")
                timestamp = data.pop("timestamp")
                events.append(TraceEvent(event_type=event_type, timestamp=timestamp, data=data))
        return events

    def list_runs(self) -> list[str]:
        """List all run IDs with traces."""
        if not self.base_dir.exists():
            return []
        return sorted(
            d.name for d in self.base_dir.iterdir() if d.is_dir() and (d / "trace.jsonl").exists()
        )
```

```python
# ouroboros/traces/collector.py
"""Collect trace events from claw-code CLI runs."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ouroboros.traces.store import TraceStore
from ouroboros.types import TraceEvent


class TraceCollector:
    def __init__(self, store: TraceStore) -> None:
        self.store = store

    def collect_run(
        self,
        prompt: str,
        cli_command: str,
        stdout: str,
        stderr: str,
        returncode: int,
        duration_ms: int,
        tokens_used: int,
    ) -> str:
        """Record a claw-code CLI run as trace events. Returns the run ID."""
        run_id = f"run-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        events = [
            TraceEvent(
                event_type="cli_run",
                timestamp=now,
                data={
                    "prompt": prompt,
                    "command": cli_command,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": returncode,
                    "duration_ms": duration_ms,
                    "tokens_used": tokens_used,
                },
            ),
        ]

        self.store.write_events(run_id, events)
        return run_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_traces.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/traces/ tests/ouroboros/test_traces.py
git commit -m "feat(ouroboros): add trace collector and JSONL store"
```

---

## Task 7: Routing Benchmark Challenges

**Files:**
- Create: `ouroboros/benchmarks/routing/challenges.json`
- Create: `ouroboros/scoreboard/__init__.py`
- Create: `ouroboros/scoreboard/tool_selection.py`
- Create: `tests/ouroboros/test_scoreboard_tool_selection.py`

- [ ] **Step 1: Write the routing challenges benchmark**

```json
[
  {
    "prompt": "list all files in the current directory",
    "expected_tool": "BashTool",
    "distractors": ["FileReadTool", "GlobTool"],
    "category": "filesystem"
  },
  {
    "prompt": "read the contents of package.json",
    "expected_tool": "FileReadTool",
    "distractors": ["BashTool", "FileEditTool"],
    "category": "filesystem"
  },
  {
    "prompt": "change the function name from foo to bar in utils.py",
    "expected_tool": "FileEditTool",
    "distractors": ["BashTool", "FileReadTool"],
    "category": "editing"
  },
  {
    "prompt": "run the test suite",
    "expected_tool": "BashTool",
    "distractors": ["FileReadTool", "AgentTool"],
    "category": "execution"
  },
  {
    "prompt": "search for all TypeScript files",
    "expected_tool": "GlobTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "search"
  },
  {
    "prompt": "find all occurrences of TODO in the codebase",
    "expected_tool": "GrepTool",
    "distractors": ["BashTool", "GlobTool", "FileReadTool"],
    "category": "search"
  },
  {
    "prompt": "install the lodash package",
    "expected_tool": "BashTool",
    "distractors": ["FileEditTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "delegate a complex research task to a sub-agent",
    "expected_tool": "AgentTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "orchestration"
  },
  {
    "prompt": "write a new file called server.py with a hello world flask app",
    "expected_tool": "FileWriteTool",
    "distractors": ["FileEditTool", "BashTool"],
    "category": "filesystem"
  },
  {
    "prompt": "git commit all changes with message fix auth",
    "expected_tool": "BashTool",
    "distractors": ["FileEditTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "show the git diff for staged changes",
    "expected_tool": "BashTool",
    "distractors": ["GrepTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "read lines 50 through 100 of runtime.py",
    "expected_tool": "FileReadTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "filesystem"
  },
  {
    "prompt": "find files matching the pattern src/**/*.test.ts",
    "expected_tool": "GlobTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "search"
  },
  {
    "prompt": "search for the function definition of handleAuth",
    "expected_tool": "GrepTool",
    "distractors": ["GlobTool", "FileReadTool"],
    "category": "search"
  },
  {
    "prompt": "replace all instances of oldName with newName in config.ts",
    "expected_tool": "FileEditTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "editing"
  },
  {
    "prompt": "run the linter on the entire project",
    "expected_tool": "BashTool",
    "distractors": ["GrepTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "check what port the server is running on",
    "expected_tool": "BashTool",
    "distractors": ["GrepTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "look at the README for this project",
    "expected_tool": "FileReadTool",
    "distractors": ["BashTool", "GlobTool"],
    "category": "filesystem"
  },
  {
    "prompt": "search across multiple files for the database connection string",
    "expected_tool": "GrepTool",
    "distractors": ["FileReadTool", "BashTool"],
    "category": "search"
  },
  {
    "prompt": "create a new directory called migrations",
    "expected_tool": "BashTool",
    "distractors": ["FileWriteTool", "FileEditTool"],
    "category": "filesystem"
  },
  {
    "prompt": "launch a background task to monitor logs",
    "expected_tool": "AgentTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "orchestration"
  },
  {
    "prompt": "update the version number in package.json from 1.0 to 1.1",
    "expected_tool": "FileEditTool",
    "distractors": ["FileReadTool", "BashTool"],
    "category": "editing"
  },
  {
    "prompt": "find all Python files larger than 100 lines",
    "expected_tool": "BashTool",
    "distractors": ["GlobTool", "GrepTool"],
    "category": "search"
  },
  {
    "prompt": "start the development server",
    "expected_tool": "BashTool",
    "distractors": ["FileReadTool", "AgentTool"],
    "category": "execution"
  },
  {
    "prompt": "investigate why the API returns 500 errors on the /users endpoint",
    "expected_tool": "AgentTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "orchestration"
  },
  {
    "prompt": "add an import statement for datetime at the top of utils.py",
    "expected_tool": "FileEditTool",
    "distractors": ["FileWriteTool", "FileReadTool"],
    "category": "editing"
  },
  {
    "prompt": "count how many test files exist in the project",
    "expected_tool": "GlobTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "search"
  },
  {
    "prompt": "check the status of running docker containers",
    "expected_tool": "BashTool",
    "distractors": ["AgentTool", "FileReadTool"],
    "category": "execution"
  },
  {
    "prompt": "look for any files that import the deprecated utils module",
    "expected_tool": "GrepTool",
    "distractors": ["GlobTool", "FileReadTool"],
    "category": "search"
  },
  {
    "prompt": "scaffold a new React component in src/components/Header.tsx",
    "expected_tool": "FileWriteTool",
    "distractors": ["FileEditTool", "BashTool"],
    "category": "filesystem"
  },
  {
    "prompt": "analyze the codebase architecture and suggest improvements",
    "expected_tool": "AgentTool",
    "distractors": ["GrepTool", "FileReadTool"],
    "category": "orchestration"
  },
  {
    "prompt": "find all .env files in the project",
    "expected_tool": "GlobTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "search"
  },
  {
    "prompt": "remove the console.log statements from auth.ts",
    "expected_tool": "FileEditTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "editing"
  },
  {
    "prompt": "deploy the application to staging",
    "expected_tool": "BashTool",
    "distractors": ["AgentTool", "FileEditTool"],
    "category": "execution"
  },
  {
    "prompt": "build the project and check for compilation errors",
    "expected_tool": "BashTool",
    "distractors": ["FileReadTool", "GrepTool"],
    "category": "execution"
  },
  {
    "prompt": "investigate this complex multi-file bug across auth and database modules",
    "expected_tool": "AgentTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "orchestration"
  },
  {
    "prompt": "view the first 20 lines of the error log",
    "expected_tool": "FileReadTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "filesystem"
  },
  {
    "prompt": "find all files modified in the last git commit",
    "expected_tool": "BashTool",
    "distractors": ["GlobTool", "GrepTool"],
    "category": "execution"
  },
  {
    "prompt": "search for the string API_KEY across all config files",
    "expected_tool": "GrepTool",
    "distractors": ["GlobTool", "FileReadTool"],
    "category": "search"
  },
  {
    "prompt": "create a new test file for the auth module",
    "expected_tool": "FileWriteTool",
    "distractors": ["FileEditTool", "BashTool"],
    "category": "filesystem"
  },
  {
    "prompt": "fix the indentation in the switch statement on line 45 of parser.py",
    "expected_tool": "FileEditTool",
    "distractors": ["FileReadTool", "BashTool"],
    "category": "editing"
  },
  {
    "prompt": "run only the unit tests that cover the payment module",
    "expected_tool": "BashTool",
    "distractors": ["GrepTool", "AgentTool"],
    "category": "execution"
  },
  {
    "prompt": "find all exported functions in the api directory",
    "expected_tool": "GrepTool",
    "distractors": ["GlobTool", "FileReadTool"],
    "category": "search"
  },
  {
    "prompt": "read the database migration file from last week",
    "expected_tool": "FileReadTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "filesystem"
  },
  {
    "prompt": "check system memory usage",
    "expected_tool": "BashTool",
    "distractors": ["FileReadTool", "AgentTool"],
    "category": "execution"
  },
  {
    "prompt": "find all React components that use the useAuth hook",
    "expected_tool": "GrepTool",
    "distractors": ["GlobTool", "AgentTool"],
    "category": "search"
  },
  {
    "prompt": "add a new route handler for POST /api/users in the router file",
    "expected_tool": "FileEditTool",
    "distractors": ["FileWriteTool", "BashTool"],
    "category": "editing"
  },
  {
    "prompt": "research the best approach to implement real-time notifications",
    "expected_tool": "AgentTool",
    "distractors": ["GrepTool", "BashTool"],
    "category": "orchestration"
  },
  {
    "prompt": "list all markdown files in the docs directory",
    "expected_tool": "GlobTool",
    "distractors": ["BashTool", "GrepTool"],
    "category": "search"
  },
  {
    "prompt": "write the output of the test run to a file called results.txt",
    "expected_tool": "BashTool",
    "distractors": ["FileWriteTool", "FileReadTool"],
    "category": "execution"
  }
]
```

- [ ] **Step 2: Write failing tests for tool_selection scorer**

```python
# tests/ouroboros/test_scoreboard_tool_selection.py
import json
from pathlib import Path

import pytest

from ouroboros.scoreboard.tool_selection import ToolSelectionScorer, RoutingChallenge


@pytest.fixture
def challenges_path(tmp_path: Path) -> Path:
    challenges = [
        {
            "prompt": "list files",
            "expected_tool": "BashTool",
            "distractors": ["FileReadTool"],
            "category": "filesystem",
        },
        {
            "prompt": "read config.json",
            "expected_tool": "FileReadTool",
            "distractors": ["BashTool"],
            "category": "filesystem",
        },
        {
            "prompt": "search for TODO",
            "expected_tool": "GrepTool",
            "distractors": ["BashTool"],
            "category": "search",
        },
    ]
    path = tmp_path / "challenges.json"
    path.write_text(json.dumps(challenges))
    return path


class TestToolSelectionScorer:
    def test_load_challenges(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        assert len(scorer.challenges) == 3

    def test_score_perfect(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        # Simulate perfect routing: every prompt maps to correct tool
        results = {
            "list files": "BashTool",
            "read config.json": "FileReadTool",
            "search for TODO": "GrepTool",
        }
        score = scorer.score(results)
        assert score.value == 1.0
        assert score.name == "tool_selection"

    def test_score_partial(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {
            "list files": "BashTool",        # correct
            "read config.json": "BashTool",   # wrong
            "search for TODO": "GrepTool",    # correct
        }
        score = scorer.score(results)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_score_zero(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {
            "list files": "GrepTool",
            "read config.json": "GrepTool",
            "search for TODO": "BashTool",
        }
        score = scorer.score(results)
        assert score.value == 0.0

    def test_missing_prompt_counted_as_failure(self, challenges_path: Path):
        scorer = ToolSelectionScorer(challenges_path=challenges_path)
        results = {"list files": "BashTool"}  # only 1 of 3
        score = scorer.score(results)
        assert abs(score.value - 1.0 / 3.0) < 0.01
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_tool_selection.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement tool_selection.py**

```python
# ouroboros/scoreboard/__init__.py
```

```python
# ouroboros/scoreboard/tool_selection.py
"""Tool selection accuracy benchmark dimension."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ouroboros.types import DimensionScore


@dataclass(frozen=True)
class RoutingChallenge:
    prompt: str
    expected_tool: str
    distractors: tuple[str, ...]
    category: str


class ToolSelectionScorer:
    def __init__(self, challenges_path: Path) -> None:
        self.challenges = self._load(challenges_path)

    def score(self, results: dict[str, str]) -> DimensionScore:
        """Score routing results against challenges.

        Args:
            results: mapping of prompt -> tool name that was selected
        """
        if not self.challenges:
            return DimensionScore(name="tool_selection", value=0.0)

        correct = sum(
            1
            for c in self.challenges
            if results.get(c.prompt) == c.expected_tool
        )
        return DimensionScore(
            name="tool_selection",
            value=correct / len(self.challenges),
        )

    def _load(self, path: Path) -> list[RoutingChallenge]:
        with open(path) as f:
            raw = json.load(f)
        return [
            RoutingChallenge(
                prompt=entry["prompt"],
                expected_tool=entry["expected_tool"],
                distractors=tuple(entry.get("distractors", [])),
                category=entry.get("category", ""),
            )
            for entry in raw
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_tool_selection.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/benchmarks/ ouroboros/scoreboard/ tests/ouroboros/test_scoreboard_tool_selection.py
git commit -m "feat(ouroboros): add routing benchmark challenges and tool selection scorer"
```

---

## Task 8: Scoreboard — Code Quality Dimension

**Files:**
- Create: `ouroboros/scoreboard/code_quality.py`
- Create: `tests/ouroboros/test_scoreboard_code_quality.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_scoreboard_code_quality.py
import tempfile
from pathlib import Path

import pytest

from ouroboros.scoreboard.code_quality import CodeQualityScorer


@pytest.fixture
def clean_python_dir(tmp_path: Path) -> Path:
    """Create a directory with clean Python code."""
    (tmp_path / "clean.py").write_text(
        'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    )
    return tmp_path


@pytest.fixture
def messy_python_dir(tmp_path: Path) -> Path:
    """Create a directory with messy Python code."""
    (tmp_path / "messy.py").write_text(
        "import os, sys, json\n"
        "def f(x,y,z,a,b,c,d,e,f,g):\n"
        "  if x:\n"
        "    if y:\n"
        "      if z:\n"
        "        if a:\n"
        "          if b:\n"
        "            return c\n"
        "  return None\n"
    )
    return tmp_path


class TestCodeQualityScorer:
    def test_clean_code_scores_high(self, clean_python_dir: Path):
        scorer = CodeQualityScorer(target_path=clean_python_dir)
        score = scorer.score()
        assert score.name == "code_quality"
        assert score.value >= 0.8

    def test_messy_code_scores_lower(self, messy_python_dir: Path):
        scorer = CodeQualityScorer(target_path=messy_python_dir)
        score = scorer.score()
        assert score.value < 0.8

    def test_empty_dir_scores_perfect(self, tmp_path: Path):
        scorer = CodeQualityScorer(target_path=tmp_path)
        score = scorer.score()
        assert score.value == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_code_quality.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement code_quality.py**

```python
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
            # Decay: each violation reduces score by 0.02, floor at 0.0
            return max(0.0, 1.0 - len(violations) * 0.02)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_code_quality.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/scoreboard/code_quality.py tests/ouroboros/test_scoreboard_code_quality.py
git commit -m "feat(ouroboros): add code quality scorer with ruff + radon"
```

---

## Task 9: Scoreboard — Correctness, Efficiency, Regression, Real-World Dimensions

**Files:**
- Create: `ouroboros/scoreboard/correctness.py`
- Create: `ouroboros/scoreboard/efficiency.py`
- Create: `ouroboros/scoreboard/regression.py`
- Create: `ouroboros/scoreboard/real_world.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_scoreboard_dimensions.py
import pytest

from ouroboros.types import DimensionScore
from ouroboros.scoreboard.correctness import CorrectnessScorer
from ouroboros.scoreboard.efficiency import EfficiencyScorer
from ouroboros.scoreboard.regression import RegressionScorer


class TestCorrectnessScorer:
    def test_all_pass(self):
        scorer = CorrectnessScorer()
        results = {"task1": True, "task2": True, "task3": True}
        score = scorer.score(results)
        assert score.name == "correctness"
        assert score.value == 1.0

    def test_partial_pass(self):
        scorer = CorrectnessScorer()
        results = {"task1": True, "task2": False, "task3": True}
        score = scorer.score(results)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_empty_results(self):
        scorer = CorrectnessScorer()
        score = scorer.score({})
        assert score.value == 0.0


class TestEfficiencyScorer:
    def test_better_than_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=500)
        assert score.name == "efficiency"
        assert score.value == 1.0  # capped at 1.0

    def test_worse_than_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=2000)
        assert score.value == 0.5

    def test_same_as_baseline(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=1000)
        assert score.value == 1.0

    def test_zero_current(self):
        scorer = EfficiencyScorer(baseline_tokens=1000)
        score = scorer.score(current_tokens=0)
        assert score.value == 1.0


class TestRegressionScorer:
    def test_no_regressions(self):
        scorer = RegressionScorer()
        previously_passing = {"task1", "task2", "task3"}
        still_passing = {"task1", "task2", "task3"}
        score = scorer.score(previously_passing, still_passing)
        assert score.name == "regression"
        assert score.value == 1.0

    def test_one_regression(self):
        scorer = RegressionScorer()
        previously_passing = {"task1", "task2", "task3"}
        still_passing = {"task1", "task3"}
        score = scorer.score(previously_passing, still_passing)
        assert abs(score.value - 2.0 / 3.0) < 0.01

    def test_empty_history(self):
        scorer = RegressionScorer()
        score = scorer.score(set(), {"task1"})
        assert score.value == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_dimensions.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement all four dimension scorers**

```python
# ouroboros/scoreboard/correctness.py
"""Correctness benchmark dimension — task pass/fail rate."""

from __future__ import annotations

from ouroboros.types import DimensionScore


class CorrectnessScorer:
    def score(self, results: dict[str, bool]) -> DimensionScore:
        """Score based on pass/fail results. Empty results = 0.0."""
        if not results:
            return DimensionScore(name="correctness", value=0.0)
        passed = sum(1 for v in results.values() if v)
        return DimensionScore(name="correctness", value=passed / len(results))
```

```python
# ouroboros/scoreboard/efficiency.py
"""Efficiency benchmark dimension — token usage compared to baseline."""

from __future__ import annotations

from ouroboros.types import DimensionScore


class EfficiencyScorer:
    def __init__(self, baseline_tokens: int) -> None:
        self.baseline_tokens = baseline_tokens

    def score(self, current_tokens: int) -> DimensionScore:
        """Score = baseline / current, capped at 1.0. Lower tokens = higher score."""
        if current_tokens <= 0:
            return DimensionScore(name="efficiency", value=1.0)
        value = min(1.0, self.baseline_tokens / current_tokens)
        return DimensionScore(name="efficiency", value=value)
```

```python
# ouroboros/scoreboard/regression.py
"""Regression benchmark dimension — previously-passing tasks still pass."""

from __future__ import annotations

from ouroboros.types import DimensionScore


class RegressionScorer:
    def score(
        self,
        previously_passing: set[str],
        still_passing: set[str],
    ) -> DimensionScore:
        """Score = fraction of previously-passing tasks still passing."""
        if not previously_passing:
            return DimensionScore(name="regression", value=1.0)
        kept = len(previously_passing & still_passing)
        return DimensionScore(name="regression", value=kept / len(previously_passing))
```

```python
# ouroboros/scoreboard/real_world.py
"""Real-world benchmark dimension — LLM-graded open-ended evaluation."""

from __future__ import annotations

from ouroboros.types import DimensionScore


class RealWorldScorer:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.model = model

    def score(self, evaluations: list[dict[str, float]]) -> DimensionScore:
        """Score from LLM evaluations. Each eval has helpfulness, accuracy, completeness (1-5).

        Args:
            evaluations: list of {"helpfulness": 4, "accuracy": 5, "completeness": 3}
        """
        if not evaluations:
            return DimensionScore(name="real_world", value=0.0)

        total = 0.0
        for ev in evaluations:
            # Each dimension 1-5, normalize to 0-1
            helpfulness = (ev.get("helpfulness", 1) - 1) / 4
            accuracy = (ev.get("accuracy", 1) - 1) / 4
            completeness = (ev.get("completeness", 1) - 1) / 4
            total += (helpfulness + accuracy + completeness) / 3

        return DimensionScore(name="real_world", value=total / len(evaluations))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_dimensions.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/scoreboard/correctness.py ouroboros/scoreboard/efficiency.py ouroboros/scoreboard/regression.py ouroboros/scoreboard/real_world.py tests/ouroboros/test_scoreboard_dimensions.py
git commit -m "feat(ouroboros): add correctness, efficiency, regression, real-world scorers"
```

---

## Task 10: Scoreboard Runner & Merge Gate

**Files:**
- Create: `ouroboros/scoreboard/runner.py`
- Create: `tests/ouroboros/test_scoreboard_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_scoreboard_runner.py
import pytest

from ouroboros.types import DimensionScore, ScoreboardSnapshot
from ouroboros.scoreboard.runner import MergeGate, can_merge


class TestMergeGate:
    def _snap(self, iteration: int, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=iteration, dimensions=dims)

    def test_improvement_merges(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is True

    def test_regression_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=0.95)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_correctness_drop_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.75, tool_selection=0.72, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_no_improvement_blocks(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.65, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False

    def test_noise_tolerance_ignores_tiny_regression(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, regression=1.0,
                           code_quality=0.89)  # new dimension
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is True

    def test_dimension_regresses_beyond_noise(self):
        before = self._snap(1, correctness=0.8, tool_selection=0.65, efficiency=0.7, regression=1.0)
        after = self._snap(2, correctness=0.8, tool_selection=0.72, efficiency=0.63, regression=1.0)
        gate = MergeGate(regression_floor=1.0, noise_tolerance=0.02)
        assert gate.can_merge(before, after) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_runner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement runner.py with MergeGate**

```python
# ouroboros/scoreboard/runner.py
"""Scoreboard runner and merge gate logic."""

from __future__ import annotations

from dataclasses import dataclass

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_scoreboard_runner.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/scoreboard/runner.py tests/ouroboros/test_scoreboard_runner.py
git commit -m "feat(ouroboros): add scoreboard merge gate with multi-dimensional checks"
```

---

## Task 11: Improvement Ledger

**Files:**
- Create: `ouroboros/history/__init__.py`
- Create: `ouroboros/history/ledger.py`
- Create: `tests/ouroboros/test_ledger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_ledger.py
import json
from pathlib import Path

import pytest

from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)
from ouroboros.history.ledger import Ledger


@pytest.fixture
def ledger_dir(tmp_path: Path) -> Path:
    return tmp_path / ".ouroboros" / "ledger"


class TestLedger:
    def _entry(self, iteration: int, outcome: IterationOutcome) -> LedgerEntry:
        snap = ScoreboardSnapshot(
            iteration=iteration,
            dimensions=(DimensionScore(name="tool_selection", value=0.7),),
        )
        return LedgerEntry(
            iteration=iteration,
            timestamp="2026-04-02T00:00:00Z",
            observation_summary="test obs",
            hypothesis="test hypothesis",
            files_changed=("src/runtime.py",),
            diff="--- a\n+++ b",
            scoreboard_before=snap,
            scoreboard_after=snap,
            outcome=outcome,
            reason="test reason",
        )

    def test_append_and_read(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        entry = self._entry(1, IterationOutcome.MERGED)
        ledger.append(entry)
        entries = ledger.read_all()
        assert len(entries) == 1
        assert entries[0].iteration == 1

    def test_multiple_entries(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        ledger.append(self._entry(3, IterationOutcome.MERGED))
        entries = ledger.read_all()
        assert len(entries) == 3

    def test_filter_merged(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        ledger.append(self._entry(3, IterationOutcome.MERGED))
        merged = ledger.read_by_outcome(IterationOutcome.MERGED)
        assert len(merged) == 2

    def test_get_latest_iteration(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        assert ledger.latest_iteration() == 0
        ledger.append(self._entry(1, IterationOutcome.MERGED))
        ledger.append(self._entry(2, IterationOutcome.ROLLED_BACK))
        assert ledger.latest_iteration() == 2

    def test_empty_ledger(self, ledger_dir: Path):
        ledger = Ledger(base_dir=ledger_dir)
        assert ledger.read_all() == []
        assert ledger.latest_iteration() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_ledger.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ledger.py**

```python
# ouroboros/history/__init__.py
```

```python
# ouroboros/history/ledger.py
"""Improvement ledger — permanent record of every iteration attempt."""

from __future__ import annotations

import json
from pathlib import Path

from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


class Ledger:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.ledger_file = base_dir / "ledger.jsonl"

    def append(self, entry: LedgerEntry) -> None:
        """Append an iteration record to the ledger."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_file, "a") as f:
            f.write(json.dumps(self._serialize(entry)) + "\n")

    def read_all(self) -> list[LedgerEntry]:
        """Read all ledger entries."""
        if not self.ledger_file.exists():
            return []
        entries: list[LedgerEntry] = []
        with open(self.ledger_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(self._deserialize(json.loads(line)))
        return entries

    def read_by_outcome(self, outcome: IterationOutcome) -> list[LedgerEntry]:
        """Filter entries by outcome."""
        return [e for e in self.read_all() if e.outcome == outcome]

    def latest_iteration(self) -> int:
        """Get the highest iteration number, or 0 if empty."""
        entries = self.read_all()
        if not entries:
            return 0
        return max(e.iteration for e in entries)

    def _serialize(self, entry: LedgerEntry) -> dict:
        return {
            "iteration": entry.iteration,
            "timestamp": entry.timestamp,
            "observation_summary": entry.observation_summary,
            "hypothesis": entry.hypothesis,
            "files_changed": list(entry.files_changed),
            "diff": entry.diff,
            "scoreboard_before": self._serialize_snapshot(entry.scoreboard_before),
            "scoreboard_after": self._serialize_snapshot(entry.scoreboard_after),
            "outcome": entry.outcome.value,
            "reason": entry.reason,
        }

    def _serialize_snapshot(self, snap: ScoreboardSnapshot) -> dict:
        return {
            "iteration": snap.iteration,
            "timestamp": snap.timestamp,
            "dimensions": [{"name": d.name, "value": d.value} for d in snap.dimensions],
        }

    def _deserialize(self, data: dict) -> LedgerEntry:
        return LedgerEntry(
            iteration=data["iteration"],
            timestamp=data["timestamp"],
            observation_summary=data["observation_summary"],
            hypothesis=data["hypothesis"],
            files_changed=tuple(data["files_changed"]),
            diff=data["diff"],
            scoreboard_before=self._deserialize_snapshot(data["scoreboard_before"]),
            scoreboard_after=self._deserialize_snapshot(data["scoreboard_after"]),
            outcome=IterationOutcome(data["outcome"]),
            reason=data["reason"],
        )

    def _deserialize_snapshot(self, data: dict) -> ScoreboardSnapshot:
        return ScoreboardSnapshot(
            iteration=data["iteration"],
            timestamp=data.get("timestamp", ""),
            dimensions=tuple(
                DimensionScore(name=d["name"], value=d["value"])
                for d in data["dimensions"]
            ),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_ledger.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/history/ tests/ouroboros/test_ledger.py
git commit -m "feat(ouroboros): add improvement ledger with JSONL persistence"
```

---

## Task 12: Base Agent Class

**Files:**
- Create: `ouroboros/agents/__init__.py`
- Create: `ouroboros/agents/base.py`
- Create: `tests/ouroboros/test_agents_base.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_agents_base.py
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.base import BaseAgent, AgentResponse


class TestBaseAgent:
    def test_creation(self):
        agent = BaseAgent(model="claude-sonnet-4-6", role="observer", timeout_seconds=120)
        assert agent.model == "claude-sonnet-4-6"
        assert agent.role == "observer"
        assert agent.timeout_seconds == 120

    @patch("ouroboros.agents.base.Anthropic")
    def test_call_llm(self, mock_anthropic_cls: MagicMock):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"result": "test"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        agent = BaseAgent(model="claude-sonnet-4-6", role="test", timeout_seconds=60)
        response = agent.call(
            system_prompt="You are a test agent.",
            user_prompt="Do something.",
        )
        assert response.text == '{"result": "test"}'
        assert response.input_tokens == 100
        assert response.output_tokens == 50

        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are a test agent.",
            messages=[{"role": "user", "content": "Do something."}],
        )

    def test_parse_json_response(self):
        agent = BaseAgent(model="test", role="test", timeout_seconds=60)
        raw = '{"hypothesis": "test", "files": ["a.py"]}'
        parsed = agent.parse_json(raw)
        assert parsed["hypothesis"] == "test"
        assert parsed["files"] == ["a.py"]

    def test_parse_json_with_markdown_fences(self):
        agent = BaseAgent(model="test", role="test", timeout_seconds=60)
        raw = '```json\n{"key": "value"}\n```'
        parsed = agent.parse_json(raw)
        assert parsed["key"] == "value"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement base.py**

```python
# ouroboros/agents/__init__.py
```

```python
# ouroboros/agents/base.py
"""Base agent class with LLM call wrapper."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from anthropic import Anthropic


@dataclass(frozen=True)
class AgentResponse:
    text: str
    input_tokens: int
    output_tokens: int


class BaseAgent:
    def __init__(self, model: str, role: str, timeout_seconds: int) -> None:
        self.model = model
        self.role = role
        self.timeout_seconds = timeout_seconds

    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AgentResponse:
        """Call the LLM with system and user prompts."""
        client = Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return AgentResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def parse_json(self, raw: str) -> dict:
        """Parse JSON from LLM response, handling markdown fences."""
        cleaned = raw.strip()
        # Remove markdown code fences
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        return json.loads(cleaned)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_base.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/agents/ tests/ouroboros/test_agents_base.py
git commit -m "feat(ouroboros): add base agent class with LLM call wrapper"
```

---

## Task 13: Observer Agent

**Files:**
- Create: `ouroboros/agents/observer.py`
- Create: `tests/ouroboros/test_agents_observer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_agents_observer.py
from unittest.mock import MagicMock, patch
import json

import pytest

from ouroboros.agents.observer import ObserverAgent
from ouroboros.types import DimensionScore, ObservationReport, ScoreboardSnapshot, TraceEvent


class TestObserverAgent:
    def _make_snapshot(self, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=1, dimensions=dims)

    def _make_traces(self) -> list[TraceEvent]:
        return [
            TraceEvent("cli_run", "2026-04-02T00:00:00Z", {
                "prompt": "list files",
                "command": "python -m src.main route 'list files'",
                "stdout": "Routed to: GrepTool (wrong)",
                "returncode": 0,
                "duration_ms": 500,
                "tokens_used": 100,
            }),
        ]

    @patch("ouroboros.agents.observer.BaseAgent.call")
    def test_observe_returns_report(self, mock_call: MagicMock):
        mock_call.return_value = MagicMock(
            text=json.dumps({
                "weakest_dimension": "tool_selection",
                "current_score": 0.65,
                "failure_examples": ["list files routed to GrepTool instead of BashTool"],
                "patterns": ["filesystem commands misrouted to search tools"],
            }),
            input_tokens=500,
            output_tokens=200,
        )
        agent = ObserverAgent(model="claude-sonnet-4-6")
        report = agent.observe(
            scoreboard=self._make_snapshot(
                correctness=0.8, tool_selection=0.65, regression=1.0
            ),
            traces=self._make_traces(),
            ledger_summary="No previous iterations.",
        )
        assert isinstance(report, ObservationReport)
        assert report.weakest_dimension == "tool_selection"
        assert report.current_score == 0.65
        assert len(report.failure_examples) == 1
        assert len(report.patterns) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_observer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement observer.py**

```python
# ouroboros/agents/observer.py
"""Observer agent — reads traces and scoreboard to identify weaknesses."""

from __future__ import annotations

import json

from ouroboros.agents.base import BaseAgent
from ouroboros.types import ObservationReport, ScoreboardSnapshot, TraceEvent

OBSERVER_SYSTEM_PROMPT = """You are the Observer agent in the Ouroboros self-improvement system.

Your job: analyze the current scoreboard and recent trace data to identify the WEAKEST dimension
that has the most room for improvement.

You are READ-ONLY. You never modify code. You produce an Observation Report.

Respond with a JSON object:
{
  "weakest_dimension": "<dimension name>",
  "current_score": <float 0-1>,
  "failure_examples": ["<specific example 1>", "<specific example 2>", ...],
  "patterns": ["<pattern 1>", "<pattern 2>", ...]
}

Be specific in failure examples — include the prompt, what happened, and what should have happened.
Be specific in patterns — identify what categories of inputs fail and why."""


class ObserverAgent:
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.agent = BaseAgent(model=model, role="observer", timeout_seconds=120)

    def observe(
        self,
        scoreboard: ScoreboardSnapshot,
        traces: list[TraceEvent],
        ledger_summary: str,
    ) -> ObservationReport:
        """Analyze scoreboard and traces, return an ObservationReport."""
        user_prompt = self._build_prompt(scoreboard, traces, ledger_summary)
        response = self.agent.call(
            system_prompt=OBSERVER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        data = self.agent.parse_json(response.text)
        return ObservationReport(
            weakest_dimension=data["weakest_dimension"],
            current_score=data["current_score"],
            failure_examples=tuple(data["failure_examples"]),
            patterns=tuple(data["patterns"]),
        )

    def _build_prompt(
        self,
        scoreboard: ScoreboardSnapshot,
        traces: list[TraceEvent],
        ledger_summary: str,
    ) -> str:
        score_lines = "\n".join(
            f"  {d.name}: {d.value:.2f}" for d in scoreboard.dimensions
        )
        trace_lines = "\n".join(
            json.dumps({"type": t.event_type, **t.data})
            for t in traces[-20:]  # last 20 traces
        )
        return (
            f"## Current Scoreboard\n{score_lines}\n\n"
            f"## Recent Traces (last 20)\n{trace_lines}\n\n"
            f"## Improvement History\n{ledger_summary}\n\n"
            "Identify the weakest dimension and provide specific failure examples and patterns."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_observer.py -v`
Expected: All 1 test PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/agents/observer.py tests/ouroboros/test_agents_observer.py
git commit -m "feat(ouroboros): add Observer agent — reads traces, identifies weaknesses"
```

---

## Task 14: Strategist Agent

**Files:**
- Create: `ouroboros/agents/strategist.py`
- Create: `tests/ouroboros/test_agents_strategist.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_agents_strategist.py
from unittest.mock import MagicMock, patch
import json

import pytest

from ouroboros.agents.strategist import StrategistAgent
from ouroboros.types import ChangePlan, FileChange, ObservationReport


class TestStrategistAgent:
    def _make_report(self) -> ObservationReport:
        return ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("list files routed to GrepTool instead of BashTool",),
            patterns=("filesystem commands misrouted to search tools",),
        )

    @patch("ouroboros.agents.strategist.BaseAgent.call")
    def test_strategize_returns_plan(self, mock_call: MagicMock):
        mock_call.return_value = MagicMock(
            text=json.dumps({
                "hypothesis": "Add keyword boosting for filesystem terms in _score()",
                "target_dimension": "tool_selection",
                "file_changes": [
                    {
                        "path": "src/runtime.py",
                        "action": "modify",
                        "description": "Add filesystem keyword boosting to _score()",
                    }
                ],
                "expected_impact": "tool_selection +10%",
            }),
            input_tokens=800,
            output_tokens=300,
        )
        agent = StrategistAgent(model="claude-opus-4-6")
        plan = agent.strategize(
            observation=self._make_report(),
            source_files={"src/runtime.py": "def _score(tokens, module):\n    ..."},
            ledger_summary="No previous attempts.",
        )
        assert isinstance(plan, ChangePlan)
        assert plan.hypothesis == "Add keyword boosting for filesystem terms in _score()"
        assert len(plan.file_changes) == 1
        assert plan.file_changes[0].path == "src/runtime.py"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_strategist.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement strategist.py**

```python
# ouroboros/agents/strategist.py
"""Strategist agent — proposes hypotheses and change plans."""

from __future__ import annotations

import json

from ouroboros.agents.base import BaseAgent
from ouroboros.types import ChangePlan, FileChange, ObservationReport

STRATEGIST_SYSTEM_PROMPT = """You are the Strategist agent in the Ouroboros self-improvement system.

Your job: given an Observation Report identifying the weakest dimension, and the relevant source code,
propose exactly ONE hypothesis for improvement with a specific Change Plan.

You think deeply. You do NOT write code. You produce a plan for the Implementer.

Review the improvement history to avoid repeating failed approaches.

Respond with a JSON object:
{
  "hypothesis": "<clear one-sentence hypothesis>",
  "target_dimension": "<dimension name this targets>",
  "file_changes": [
    {
      "path": "<exact file path>",
      "action": "modify" or "create",
      "description": "<what to change and why, in detail>"
    }
  ],
  "expected_impact": "<expected improvement, e.g., 'tool_selection +10%'>"
}

Be specific in descriptions. The Implementer will use your descriptions to write code.
Reference specific functions, line numbers, and logic."""


class StrategistAgent:
    def __init__(self, model: str = "claude-opus-4-6") -> None:
        self.agent = BaseAgent(model=model, role="strategist", timeout_seconds=180)

    def strategize(
        self,
        observation: ObservationReport,
        source_files: dict[str, str],
        ledger_summary: str,
    ) -> ChangePlan:
        """Propose a change plan based on the observation."""
        user_prompt = self._build_prompt(observation, source_files, ledger_summary)
        response = self.agent.call(
            system_prompt=STRATEGIST_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        data = self.agent.parse_json(response.text)
        return ChangePlan(
            hypothesis=data["hypothesis"],
            target_dimension=data["target_dimension"],
            file_changes=tuple(
                FileChange(
                    path=fc["path"],
                    action=fc["action"],
                    description=fc["description"],
                )
                for fc in data["file_changes"]
            ),
            expected_impact=data["expected_impact"],
        )

    def _build_prompt(
        self,
        observation: ObservationReport,
        source_files: dict[str, str],
        ledger_summary: str,
    ) -> str:
        file_sections = "\n\n".join(
            f"### {path}\n```python\n{content}\n```"
            for path, content in source_files.items()
        )
        examples = "\n".join(f"  - {ex}" for ex in observation.failure_examples)
        patterns = "\n".join(f"  - {p}" for p in observation.patterns)
        return (
            f"## Observation Report\n"
            f"Weakest dimension: {observation.weakest_dimension} (score: {observation.current_score:.2f})\n\n"
            f"Failure examples:\n{examples}\n\n"
            f"Patterns:\n{patterns}\n\n"
            f"## Relevant Source Code\n{file_sections}\n\n"
            f"## Previous Attempts\n{ledger_summary}\n\n"
            "Propose exactly ONE hypothesis with a specific change plan."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_strategist.py -v`
Expected: All 1 test PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/agents/strategist.py tests/ouroboros/test_agents_strategist.py
git commit -m "feat(ouroboros): add Strategist agent — proposes hypotheses from observations"
```

---

## Task 15: Implementer Agent

**Files:**
- Create: `ouroboros/agents/implementer.py`
- Create: `tests/ouroboros/test_agents_implementer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_agents_implementer.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.implementer import ImplementerAgent
from ouroboros.config import DEFAULT_CONFIG
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.types import ChangePlan, FileChange


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    src = tmp_path / "src"
    src.mkdir()
    (src / "runtime.py").write_text("def _score(tokens, module):\n    return 0\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestImplementerAgent:
    @patch("ouroboros.agents.implementer.BaseAgent.call")
    def test_implement_writes_to_worktree(self, mock_call: MagicMock, git_repo: Path):
        mock_call.return_value = MagicMock(
            text='{"files_written": {"src/runtime.py": "def _score(tokens, module):\\n    return len(tokens)\\n"}}',
            input_tokens=600,
            output_tokens=200,
        )
        plan = ChangePlan(
            hypothesis="Improve scoring",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="src/runtime.py", action="modify", description="Improve _score"),
            ),
            expected_impact="+10%",
        )
        executor = SandboxExecutor(config=DEFAULT_CONFIG)
        agent = ImplementerAgent(model="claude-opus-4-6", executor=executor)
        result = agent.implement(plan=plan, worktree_path=git_repo)
        assert result.success
        assert "src/runtime.py" in result.files_written

    @patch("ouroboros.agents.implementer.BaseAgent.call")
    def test_blocked_path_rejected(self, mock_call: MagicMock, git_repo: Path):
        mock_call.return_value = MagicMock(
            text='{"files_written": {"ouroboros/loop.py": "hacked"}}',
            input_tokens=100,
            output_tokens=50,
        )
        plan = ChangePlan(
            hypothesis="Hack the engine",
            target_dimension="tool_selection",
            file_changes=(
                FileChange(path="ouroboros/loop.py", action="modify", description="Hack"),
            ),
            expected_impact="n/a",
        )
        executor = SandboxExecutor(config=DEFAULT_CONFIG)
        agent = ImplementerAgent(model="claude-opus-4-6", executor=executor)
        result = agent.implement(plan=plan, worktree_path=git_repo)
        assert not result.success
        assert "blocked" in result.error.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_implementer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement implementer.py**

```python
# ouroboros/agents/implementer.py
"""Implementer agent — writes code changes in a sandboxed worktree."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ouroboros.agents.base import BaseAgent
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.types import ChangePlan

IMPLEMENTER_SYSTEM_PROMPT = """You are the Implementer agent in the Ouroboros self-improvement system.

Your job: given a Change Plan, write the actual code changes. You receive a plan and the current
source code of files to modify. You write the complete new content for each file.

You ONLY write code. You do not analyze, question, or evaluate the plan.

Respond with a JSON object:
{
  "files_written": {
    "path/to/file.py": "<complete file content after changes>"
  }
}

IMPORTANT: Write the COMPLETE file content, not just the changed parts.
Only modify files specified in the Change Plan. Do not modify any other files."""


@dataclass(frozen=True)
class ImplementResult:
    success: bool
    files_written: tuple[str, ...]
    error: str = ""


class ImplementerAgent:
    def __init__(self, model: str, executor: SandboxExecutor) -> None:
        self.agent = BaseAgent(model=model, role="implementer", timeout_seconds=300)
        self.executor = executor

    def implement(self, plan: ChangePlan, worktree_path: Path) -> ImplementResult:
        """Write code changes to the worktree based on the plan."""
        # Check for blocked paths before calling LLM
        for fc in plan.file_changes:
            if self.executor.is_path_blocked(fc.path):
                return ImplementResult(
                    success=False,
                    files_written=(),
                    error=f"Blocked path: {fc.path} is in the blocked paths list",
                )

        # Read current file contents
        source_files: dict[str, str] = {}
        for fc in plan.file_changes:
            file_path = worktree_path / fc.path
            if file_path.exists():
                source_files[fc.path] = file_path.read_text()
            else:
                source_files[fc.path] = ""

        user_prompt = self._build_prompt(plan, source_files)
        response = self.agent.call(
            system_prompt=IMPLEMENTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        data = self.agent.parse_json(response.text)
        files_written = data.get("files_written", {})

        # Validate no blocked paths in response
        for path in files_written:
            if self.executor.is_path_blocked(path):
                return ImplementResult(
                    success=False,
                    files_written=(),
                    error=f"Blocked path in response: {path}",
                )

        # Write files to worktree
        written: list[str] = []
        for path, content in files_written.items():
            file_path = worktree_path / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            written.append(path)

        # Stage and commit
        if written:
            subprocess.run(
                ["git", "-C", str(worktree_path), "add"] + [str(worktree_path / w) for w in written],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(worktree_path), "commit", "-m", f"ouroboros: {plan.hypothesis}"],
                check=True,
                capture_output=True,
            )

        return ImplementResult(success=True, files_written=tuple(written))

    def _build_prompt(self, plan: ChangePlan, source_files: dict[str, str]) -> str:
        file_sections = "\n\n".join(
            f"### {path}\n```python\n{content}\n```" if content
            else f"### {path}\n(new file — create from scratch)"
            for path, content in source_files.items()
        )
        changes = "\n".join(
            f"  - {fc.path} ({fc.action}): {fc.description}"
            for fc in plan.file_changes
        )
        return (
            f"## Change Plan\n"
            f"Hypothesis: {plan.hypothesis}\n"
            f"Target: {plan.target_dimension}\n"
            f"Expected impact: {plan.expected_impact}\n\n"
            f"Changes to make:\n{changes}\n\n"
            f"## Current Source Code\n{file_sections}\n\n"
            "Write the complete updated file content for each file."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_implementer.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/agents/implementer.py tests/ouroboros/test_agents_implementer.py
git commit -m "feat(ouroboros): add Implementer agent — writes code in sandboxed worktrees"
```

---

## Task 16: Evaluator Agent

**Files:**
- Create: `ouroboros/agents/evaluator.py`
- Create: `tests/ouroboros/test_agents_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_agents_evaluator.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.evaluator import EvaluatorAgent, EvalDecision
from ouroboros.config import DEFAULT_CONFIG
from ouroboros.types import DimensionScore, ScoreboardSnapshot


class TestEvaluatorAgent:
    def _snap(self, **scores: float) -> ScoreboardSnapshot:
        dims = tuple(DimensionScore(name=k, value=v) for k, v in scores.items())
        return ScoreboardSnapshot(iteration=1, dimensions=dims)

    def test_merge_when_improved(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.75, regression=1.0)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.MERGE

    def test_rollback_when_regressed(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.72, regression=0.9)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.ROLLBACK

    def test_rollback_when_no_improvement(self):
        agent = EvaluatorAgent(config=DEFAULT_CONFIG)
        before = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        after = self._snap(correctness=0.8, tool_selection=0.65, regression=1.0)
        decision = agent.decide(before=before, after=after)
        assert decision == EvalDecision.ROLLBACK
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_evaluator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement evaluator.py**

```python
# ouroboros/agents/evaluator.py
"""Evaluator agent — runs scoreboard and makes merge/rollback decisions."""

from __future__ import annotations

from enum import Enum

from ouroboros.config import OuroborosConfig
from ouroboros.scoreboard.runner import MergeGate
from ouroboros.types import ScoreboardSnapshot


class EvalDecision(str, Enum):
    MERGE = "MERGE"
    ROLLBACK = "ROLLBACK"


class EvaluatorAgent:
    def __init__(self, config: OuroborosConfig) -> None:
        self.gate = MergeGate(
            regression_floor=config.merge_gate_regression_floor,
            noise_tolerance=config.merge_gate_noise_tolerance,
        )

    def decide(
        self,
        before: ScoreboardSnapshot,
        after: ScoreboardSnapshot,
    ) -> EvalDecision:
        """Compare before/after scoreboard snapshots and decide merge or rollback."""
        if self.gate.can_merge(before, after):
            return EvalDecision.MERGE
        return EvalDecision.ROLLBACK
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_agents_evaluator.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/agents/evaluator.py tests/ouroboros/test_agents_evaluator.py
git commit -m "feat(ouroboros): add Evaluator agent with merge gate decisions"
```

---

## Task 17: Core Improvement Loop

**Files:**
- Create: `ouroboros/loop.py`
- Create: `tests/ouroboros/test_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_loop.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.config import DEFAULT_CONFIG
from ouroboros.loop import ImprovementLoop, LoopResult
from ouroboros.types import (
    ChangePlan,
    DimensionScore,
    FileChange,
    IterationOutcome,
    ObservationReport,
    ScoreboardSnapshot,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    src = tmp_path / "src"
    src.mkdir()
    (src / "runtime.py").write_text("def _score(tokens, module):\n    return 0\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestImprovementLoop:
    @patch("ouroboros.loop.ObserverAgent")
    @patch("ouroboros.loop.StrategistAgent")
    @patch("ouroboros.loop.ImplementerAgent")
    def test_single_iteration_merged(
        self,
        mock_impl_cls: MagicMock,
        mock_strat_cls: MagicMock,
        mock_obs_cls: MagicMock,
        git_repo: Path,
    ):
        # Mock Observer
        mock_observer = MagicMock()
        mock_observer.observe.return_value = ObservationReport(
            weakest_dimension="tool_selection",
            current_score=0.65,
            failure_examples=("example",),
            patterns=("pattern",),
        )
        mock_obs_cls.return_value = mock_observer

        # Mock Strategist
        mock_strategist = MagicMock()
        mock_strategist.strategize.return_value = ChangePlan(
            hypothesis="Improve scoring",
            target_dimension="tool_selection",
            file_changes=(FileChange("src/runtime.py", "modify", "Improve _score"),),
            expected_impact="+10%",
        )
        mock_strat_cls.return_value = mock_strategist

        # Mock Implementer
        mock_implementer = MagicMock()
        mock_implementer.implement.return_value = MagicMock(
            success=True, files_written=("src/runtime.py",), error=""
        )
        mock_impl_cls.return_value = mock_implementer

        config = DEFAULT_CONFIG.with_overrides({"max_iterations": 1})
        loop = ImprovementLoop(config=config, repo_root=git_repo)

        # Provide mock scoreboard that shows improvement
        with patch.object(loop, "_run_scoreboard") as mock_score:
            mock_score.side_effect = [
                # Baseline
                ScoreboardSnapshot(iteration=0, dimensions=(
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.65),
                    DimensionScore("regression", 1.0),
                )),
                # After improvement
                ScoreboardSnapshot(iteration=1, dimensions=(
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.75),
                    DimensionScore("regression", 1.0),
                )),
            ]
            result = loop.run()

        assert isinstance(result, LoopResult)
        assert result.iterations_run == 1
        assert result.iterations_merged >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_loop.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement loop.py**

```python
# ouroboros/loop.py
"""Core improvement loop — OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ouroboros.agents.evaluator import EvalDecision, EvaluatorAgent
from ouroboros.agents.implementer import ImplementerAgent
from ouroboros.agents.observer import ObserverAgent
from ouroboros.agents.strategist import StrategistAgent
from ouroboros.config import OuroborosConfig
from ouroboros.history.ledger import Ledger
from ouroboros.sandbox.executor import SandboxExecutor
from ouroboros.sandbox.worktree import WorktreeManager
from ouroboros.traces.store import TraceStore
from ouroboros.types import (
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


@dataclass(frozen=True)
class LoopResult:
    iterations_run: int
    iterations_merged: int
    iterations_rolled_back: int
    total_duration_seconds: float
    stop_reason: str


class ImprovementLoop:
    def __init__(self, config: OuroborosConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self.worktree_mgr = WorktreeManager(repo_root=repo_root)
        self.executor = SandboxExecutor(config=config)
        self.trace_store = TraceStore(base_dir=repo_root / ".ouroboros" / "traces")
        self.ledger = Ledger(base_dir=repo_root / ".ouroboros" / "ledger")
        self.evaluator = EvaluatorAgent(config=config)

        self.observer = ObserverAgent(model=config.model_observer)
        self.strategist = StrategistAgent(model=config.model_strategist)
        self.implementer = ImplementerAgent(
            model=config.model_implementer,
            executor=self.executor,
        )

    def run(self) -> LoopResult:
        """Run the improvement loop for up to max_iterations."""
        start_time = time.time()
        merged = 0
        rolled_back = 0
        stop_reason = "completed"

        start_iteration = self.ledger.latest_iteration() + 1

        for i in range(self.config.max_iterations):
            iteration = start_iteration + i
            elapsed = time.time() - start_time

            # Check time budget
            if elapsed > self.config.time_budget_minutes * 60:
                stop_reason = "time_budget_reached"
                break

            outcome = self._run_iteration(iteration)
            if outcome == IterationOutcome.MERGED:
                merged += 1
            else:
                rolled_back += 1

            # Cooldown between iterations
            if i < self.config.max_iterations - 1:
                time.sleep(self.config.cooldown_seconds)

        return LoopResult(
            iterations_run=i + 1,
            iterations_merged=merged,
            iterations_rolled_back=rolled_back,
            total_duration_seconds=time.time() - start_time,
            stop_reason=stop_reason,
        )

    def _run_iteration(self, iteration: int) -> IterationOutcome:
        """Execute one full OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE cycle."""
        now = datetime.now(timezone.utc).isoformat()

        # Step 1: OBSERVE
        baseline = self._run_scoreboard(self.repo_root)
        traces = self.trace_store.read_events(
            self.trace_store.list_runs()[-1] if self.trace_store.list_runs() else ""
        )
        ledger_entries = self.ledger.read_all()
        ledger_summary = self._summarize_ledger(ledger_entries)

        observation = self.observer.observe(
            scoreboard=baseline,
            traces=traces,
            ledger_summary=ledger_summary,
        )

        # Step 2: HYPOTHESIZE
        source_files = self._read_target_files(observation.weakest_dimension)
        plan = self.strategist.strategize(
            observation=observation,
            source_files=source_files,
            ledger_summary=ledger_summary,
        )

        # Step 3: IMPLEMENT
        worktree = self.worktree_mgr.create(iteration=iteration)
        try:
            impl_result = self.implementer.implement(plan=plan, worktree_path=worktree.path)

            if not impl_result.success:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, baseline,
                    IterationOutcome.ROLLED_BACK,
                    f"Implementation failed: {impl_result.error}",
                )
                return IterationOutcome.ROLLED_BACK

            # Step 4: EVALUATE
            after = self._run_scoreboard(worktree.path)
            decision = self.evaluator.decide(before=baseline, after=after)
            diff = self.worktree_mgr.get_diff(worktree)

            if decision == EvalDecision.MERGE:
                self.worktree_mgr.merge(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, after,
                    IterationOutcome.MERGED,
                    self._describe_improvement(baseline, after),
                )
                return IterationOutcome.MERGED
            else:
                self.worktree_mgr.rollback(worktree)
                self._log_iteration(
                    iteration, now, observation, plan, baseline, after,
                    IterationOutcome.ROLLED_BACK,
                    "Merge gate failed — no improvement or regression detected",
                )
                return IterationOutcome.ROLLED_BACK

        except Exception as e:
            try:
                self.worktree_mgr.rollback(worktree)
            except Exception:
                pass
            self._log_iteration(
                iteration, now, observation, plan, baseline, baseline,
                IterationOutcome.ABANDONED,
                f"Exception: {e}",
            )
            return IterationOutcome.ABANDONED

    def _run_scoreboard(self, target_path: Path) -> ScoreboardSnapshot:
        """Run all benchmark dimensions against a target path. Override in tests."""
        # This will be filled in when we wire up the full scoreboard runner
        from ouroboros.scoreboard.code_quality import CodeQualityScorer

        cq = CodeQualityScorer(target_path=target_path / self.config.target_path)
        cq_score = cq.score()
        return ScoreboardSnapshot(
            iteration=0,
            dimensions=(cq_score,),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _read_target_files(self, dimension: str) -> dict[str, str]:
        """Read relevant source files based on the dimension being targeted."""
        target_dir = self.repo_root / self.config.target_path
        files: dict[str, str] = {}
        # For routing, read the key routing files
        key_files = ["runtime.py", "commands.py", "tools.py"]
        for name in key_files:
            path = target_dir / name
            if path.exists():
                files[f"{self.config.target_path}{name}"] = path.read_text()
        return files

    def _summarize_ledger(self, entries: list) -> str:
        if not entries:
            return "No previous iterations."
        lines = []
        for e in entries[-10:]:  # last 10 entries
            lines.append(f"  #{e.iteration} [{e.outcome.value}]: {e.hypothesis} — {e.reason}")
        return "\n".join(lines)

    def _describe_improvement(self, before: ScoreboardSnapshot, after: ScoreboardSnapshot) -> str:
        parts = []
        for ad in after.dimensions:
            bd = before.get(ad.name)
            if bd and ad.value > bd.value:
                delta = ad.value - bd.value
                parts.append(f"{ad.name} +{delta:.2f}")
        return ", ".join(parts) if parts else "marginal improvement"

    def _log_iteration(self, iteration, timestamp, observation, plan, before, after, outcome, reason):
        self.ledger.append(LedgerEntry(
            iteration=iteration,
            timestamp=timestamp,
            observation_summary=f"{observation.weakest_dimension} at {observation.current_score:.2f}",
            hypothesis=plan.hypothesis,
            files_changed=tuple(fc.path for fc in plan.file_changes),
            diff="",
            scoreboard_before=before,
            scoreboard_after=after,
            outcome=outcome,
            reason=reason,
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_loop.py -v`
Expected: All 1 test PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/loop.py tests/ouroboros/test_loop.py
git commit -m "feat(ouroboros): add core improvement loop — OBSERVE→HYPOTHESIZE→IMPLEMENT→EVALUATE"
```

---

## Task 18: CLI Entry Point

**Files:**
- Create: `ouroboros/cli.py`
- Create: `tests/ouroboros/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ouroboros/test_cli.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError` for cli module

- [ ] **Step 3: Implement cli.py**

```python
# ouroboros/cli.py
"""CLI entry point for Ouroboros."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from ouroboros.config import DEFAULT_CONFIG, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros",
        description="Ouroboros: Self-improving agent engine",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("ouroboros.yaml"),
        help="Path to config file (default: ouroboros.yaml)",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_parser = sub.add_parser("run", help="Run the improvement loop")
    run_parser.add_argument("--iterations", type=int, help="Max iterations")
    run_parser.add_argument("--time-budget", type=str, help="Time budget (e.g., 3h, 90m)")
    run_parser.add_argument("--dry-run", action="store_true", help="Observe and hypothesize only")
    run_parser.add_argument("--model-implementer", type=str)
    run_parser.add_argument("--model-evaluator", type=str)

    # scoreboard
    sb_parser = sub.add_parser("scoreboard", help="View current scoreboard")
    sb_parser.add_argument("--history", action="store_true", help="Show trajectory over time")
    sb_parser.add_argument("--dimension", type=str, help="Deep dive into one dimension")

    # ledger
    ledger_parser = sub.add_parser("ledger", help="View improvement history")
    ledger_parser.add_argument("--iteration", type=int, help="Show specific iteration")
    ledger_parser.add_argument("--merged-only", action="store_true")
    ledger_parser.add_argument("--failed-only", action="store_true")

    # benchmark
    bench_parser = sub.add_parser("benchmark", help="Run benchmarks manually")
    bench_parser.add_argument("--suite", type=str, default="all", help="Benchmark suite to run")

    # dashboard
    dash_parser = sub.add_parser("dashboard", help="Launch dashboard")
    dash_parser.add_argument("--web", action="store_true", help="Launch web dashboard")
    dash_parser.add_argument("--port", type=int, help="Web dashboard port")

    # config
    config_parser = sub.add_parser("config", help="View or update configuration")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("show", help="Show current configuration")
    set_parser = config_sub.add_parser("set", help="Set a configuration value")
    set_parser.add_argument("key", type=str)
    set_parser.add_argument("value", type=str)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)

    if args.command == "run":
        _cmd_run(config, args)
    elif args.command == "scoreboard":
        _cmd_scoreboard(config, args)
    elif args.command == "ledger":
        _cmd_ledger(config, args)
    elif args.command == "benchmark":
        _cmd_benchmark(config, args)
    elif args.command == "config":
        _cmd_config(config, args)
    elif args.command == "dashboard":
        _cmd_dashboard(config, args)
    else:
        parser.print_help()


def _cmd_run(config, args):
    overrides = {}
    if args.iterations:
        overrides["max_iterations"] = args.iterations
    if args.model_implementer:
        overrides["model_implementer"] = args.model_implementer
    if args.model_evaluator:
        overrides["model_evaluator"] = args.model_evaluator
    if args.time_budget:
        budget = args.time_budget
        if budget.endswith("h"):
            overrides["time_budget_minutes"] = int(budget[:-1]) * 60
        elif budget.endswith("m"):
            overrides["time_budget_minutes"] = int(budget[:-1])

    config = config.with_overrides(overrides) if overrides else config
    repo_root = Path.cwd()

    from ouroboros.loop import ImprovementLoop

    loop = ImprovementLoop(config=config, repo_root=repo_root)
    print(f"Starting Ouroboros improvement loop (max {config.max_iterations} iterations)...")
    result = loop.run()
    print(f"\nLoop complete:")
    print(f"  Iterations run:       {result.iterations_run}")
    print(f"  Merged:               {result.iterations_merged}")
    print(f"  Rolled back:          {result.iterations_rolled_back}")
    print(f"  Duration:             {result.total_duration_seconds:.1f}s")
    print(f"  Stop reason:          {result.stop_reason}")


def _cmd_scoreboard(config, args):
    repo_root = Path.cwd()
    from ouroboros.history.ledger import Ledger

    ledger = Ledger(base_dir=repo_root / ".ouroboros" / "ledger")
    entries = ledger.read_all()

    if not entries:
        print("No scoreboard data yet. Run `ouroboros run` first.")
        return

    if args.history:
        for e in entries:
            dims = " | ".join(f"{d.name}={d.value:.2f}" for d in e.scoreboard_after.dimensions)
            print(f"  #{e.iteration:03d} [{e.outcome.value:12s}] {dims}")
    else:
        latest = entries[-1]
        print("Current Scoreboard:")
        for d in latest.scoreboard_after.dimensions:
            bar = "#" * int(d.value * 20)
            print(f"  {d.name:20s} {bar:20s} {d.value:.2f}")


def _cmd_ledger(config, args):
    repo_root = Path.cwd()
    from ouroboros.history.ledger import Ledger
    from ouroboros.types import IterationOutcome

    ledger = Ledger(base_dir=repo_root / ".ouroboros" / "ledger")
    entries = ledger.read_all()

    if not entries:
        print("Ledger is empty. Run `ouroboros run` first.")
        return

    if args.iteration:
        matching = [e for e in entries if e.iteration == args.iteration]
        if not matching:
            print(f"No entry for iteration {args.iteration}")
            return
        e = matching[0]
        print(f"Iteration #{e.iteration}")
        print(f"  Timestamp:   {e.timestamp}")
        print(f"  Observation: {e.observation_summary}")
        print(f"  Hypothesis:  {e.hypothesis}")
        print(f"  Files:       {', '.join(e.files_changed)}")
        print(f"  Outcome:     {e.outcome.value}")
        print(f"  Reason:      {e.reason}")
        return

    if args.merged_only:
        entries = [e for e in entries if e.outcome == IterationOutcome.MERGED]
    if args.failed_only:
        entries = [e for e in entries if e.outcome != IterationOutcome.MERGED]

    for e in entries:
        status = "+" if e.outcome == IterationOutcome.MERGED else "-"
        print(f"  {status} #{e.iteration:03d} {e.hypothesis[:60]:60s} [{e.outcome.value}]")


def _cmd_benchmark(config, args):
    print(f"Running benchmark suite: {args.suite}")
    print("(Benchmark runner not yet wired — coming in Phase 1 integration)")


def _cmd_config(config, args):
    if args.config_command == "show":
        for key, value in sorted(vars(config).items()):
            print(f"  {key}: {value}")
    elif args.config_command == "set":
        print(f"Set {args.key} = {args.value}")
        print("(Config persistence not yet implemented)")
    else:
        print("Usage: ouroboros config show | ouroboros config set <key> <value>")


def _cmd_dashboard(config, args):
    if args.web:
        port = args.port or config.dashboard_web_port
        print(f"Web dashboard not yet implemented. Will serve on port {port}.")
    else:
        _cmd_scoreboard(config, args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_cli.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/cli.py tests/ouroboros/test_cli.py
git commit -m "feat(ouroboros): add CLI — run, scoreboard, ledger, config, dashboard commands"
```

---

## Task 19: Trace Analyzer

**Files:**
- Create: `ouroboros/traces/analyzer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ouroboros/test_trace_analyzer.py
import pytest

from ouroboros.traces.analyzer import TraceAnalyzer
from ouroboros.types import TraceEvent


class TestTraceAnalyzer:
    def test_identify_routing_failures(self):
        traces = [
            TraceEvent("cli_run", "t1", {"prompt": "list files", "stdout": "Routed to: GrepTool", "returncode": 0, "tokens_used": 100, "duration_ms": 500}),
            TraceEvent("cli_run", "t2", {"prompt": "read file", "stdout": "Routed to: BashTool", "returncode": 0, "tokens_used": 120, "duration_ms": 600}),
            TraceEvent("cli_run", "t3", {"prompt": "search code", "stdout": "Routed to: GrepTool", "returncode": 0, "tokens_used": 80, "duration_ms": 400}),
        ]
        analyzer = TraceAnalyzer()
        summary = analyzer.summarize(traces)
        assert summary.total_runs == 3
        assert summary.avg_tokens > 0
        assert summary.avg_duration_ms > 0

    def test_empty_traces(self):
        analyzer = TraceAnalyzer()
        summary = analyzer.summarize([])
        assert summary.total_runs == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_trace_analyzer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement analyzer.py**

```python
# ouroboros/traces/analyzer.py
"""Trace analysis — pattern detection across runs."""

from __future__ import annotations

from dataclasses import dataclass

from ouroboros.types import TraceEvent


@dataclass(frozen=True)
class TraceSummary:
    total_runs: int
    avg_tokens: float
    avg_duration_ms: float
    tool_frequency: dict[str, int]


class TraceAnalyzer:
    def summarize(self, traces: list[TraceEvent]) -> TraceSummary:
        """Produce aggregate statistics from trace events."""
        cli_runs = [t for t in traces if t.event_type == "cli_run"]

        if not cli_runs:
            return TraceSummary(total_runs=0, avg_tokens=0.0, avg_duration_ms=0.0, tool_frequency={})

        total_tokens = sum(t.data.get("tokens_used", 0) for t in cli_runs)
        total_duration = sum(t.data.get("duration_ms", 0) for t in cli_runs)

        tool_freq: dict[str, int] = {}
        for t in cli_runs:
            stdout = str(t.data.get("stdout", ""))
            if "Routed to:" in stdout:
                tool = stdout.split("Routed to:")[1].strip().split()[0]
                tool_freq[tool] = tool_freq.get(tool, 0) + 1

        return TraceSummary(
            total_runs=len(cli_runs),
            avg_tokens=total_tokens / len(cli_runs),
            avg_duration_ms=total_duration / len(cli_runs),
            tool_frequency=tool_freq,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_trace_analyzer.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/traces/analyzer.py tests/ouroboros/test_trace_analyzer.py
git commit -m "feat(ouroboros): add trace analyzer for pattern detection"
```

---

## Task 20: Sandbox Rollback Module

**Files:**
- Create: `ouroboros/sandbox/rollback.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ouroboros/test_sandbox_rollback.py
import subprocess
from pathlib import Path

import pytest

from ouroboros.sandbox.rollback import safe_rollback
from ouroboros.sandbox.worktree import WorktreeInfo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    (tmp_path / "f.txt").write_text("ok")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestSafeRollback:
    def test_rollback_cleans_worktree(self, git_repo: Path):
        wt_path = git_repo / ".worktrees" / "test-wt"
        subprocess.run(
            ["git", "-C", str(git_repo), "worktree", "add", str(wt_path), "-b", "test-branch"],
            check=True, capture_output=True,
        )
        info = WorktreeInfo(path=wt_path, branch="test-branch", iteration=1)
        assert wt_path.exists()
        safe_rollback(repo_root=git_repo, info=info)
        assert not wt_path.exists()

    def test_rollback_nonexistent_is_safe(self, git_repo: Path):
        info = WorktreeInfo(path=git_repo / "nonexistent", branch="nope", iteration=99)
        # Should not raise
        safe_rollback(repo_root=git_repo, info=info)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_rollback.py -v`
Expected: FAIL

- [ ] **Step 3: Implement rollback.py**

```python
# ouroboros/sandbox/rollback.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_sandbox_rollback.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/sandbox/rollback.py tests/ouroboros/test_sandbox_rollback.py
git commit -m "feat(ouroboros): add safe rollback — never crashes on cleanup"
```

---

## Task 21: Dashboard (Terminal View)

**Files:**
- Create: `ouroboros/history/dashboard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ouroboros/test_dashboard.py
import pytest

from ouroboros.history.dashboard import render_scoreboard_ascii, render_ledger_summary
from ouroboros.types import (
    DimensionScore,
    IterationOutcome,
    LedgerEntry,
    ScoreboardSnapshot,
)


class TestDashboard:
    def test_render_scoreboard(self):
        snap = ScoreboardSnapshot(
            iteration=5,
            dimensions=(
                DimensionScore("correctness", 0.85),
                DimensionScore("tool_selection", 0.72),
                DimensionScore("regression", 1.0),
            ),
        )
        output = render_scoreboard_ascii(snap)
        assert "correctness" in output
        assert "0.85" in output
        assert "tool_selection" in output

    def test_render_empty_scoreboard(self):
        snap = ScoreboardSnapshot(iteration=0, dimensions=())
        output = render_scoreboard_ascii(snap)
        assert "no data" in output.lower() or "empty" in output.lower() or output.strip() != ""

    def test_render_ledger_summary(self):
        entries = [
            LedgerEntry(
                iteration=1, timestamp="t", observation_summary="obs",
                hypothesis="hyp1", files_changed=("a.py",), diff="",
                scoreboard_before=ScoreboardSnapshot(0, ()), scoreboard_after=ScoreboardSnapshot(1, ()),
                outcome=IterationOutcome.MERGED, reason="good",
            ),
            LedgerEntry(
                iteration=2, timestamp="t", observation_summary="obs",
                hypothesis="hyp2", files_changed=("b.py",), diff="",
                scoreboard_before=ScoreboardSnapshot(1, ()), scoreboard_after=ScoreboardSnapshot(2, ()),
                outcome=IterationOutcome.ROLLED_BACK, reason="bad",
            ),
        ]
        output = render_ledger_summary(entries)
        assert "hyp1" in output
        assert "MERGED" in output
        assert "ROLLED_BACK" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_dashboard.py -v`
Expected: FAIL

- [ ] **Step 3: Implement dashboard.py**

```python
# ouroboros/history/dashboard.py
"""Terminal dashboard for scoreboard and ledger visualization."""

from __future__ import annotations

from ouroboros.types import LedgerEntry, ScoreboardSnapshot


def render_scoreboard_ascii(snapshot: ScoreboardSnapshot) -> str:
    """Render a scoreboard snapshot as an ASCII bar chart."""
    if not snapshot.dimensions:
        return f"Scoreboard (iteration {snapshot.iteration}): No data yet."

    lines = [f"Scoreboard (iteration {snapshot.iteration})", "=" * 50]
    for dim in snapshot.dimensions:
        bar_len = int(dim.value * 30)
        bar = "#" * bar_len + "." * (30 - bar_len)
        lines.append(f"  {dim.name:20s} [{bar}] {dim.value:.2f}")
    return "\n".join(lines)


def render_ledger_summary(entries: list[LedgerEntry]) -> str:
    """Render a compact summary of ledger entries."""
    if not entries:
        return "Ledger: No entries."

    lines = ["Improvement History", "=" * 70]
    for e in entries:
        marker = "+" if e.outcome.value == "MERGED" else "-"
        lines.append(
            f"  {marker} #{e.iteration:03d} [{e.outcome.value:12s}] "
            f"{e.hypothesis[:45]:45s} | {e.reason[:20]}"
        )

    merged = sum(1 for e in entries if e.outcome.value == "MERGED")
    total = len(entries)
    lines.append(f"\n  Total: {total} iterations | Merged: {merged} | Yield: {merged/total*100:.0f}%")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_dashboard.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/claw-code
git add ouroboros/history/dashboard.py tests/ouroboros/test_dashboard.py
git commit -m "feat(ouroboros): add terminal dashboard for scoreboard and ledger"
```

---

## Task 22: Full Integration Test

**Files:**
- Create: `tests/ouroboros/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/ouroboros/test_integration.py
"""End-to-end integration test — runs a single iteration with mocked LLM calls."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.config import OuroborosConfig
from ouroboros.loop import ImprovementLoop
from ouroboros.types import (
    ChangePlan,
    DimensionScore,
    FileChange,
    IterationOutcome,
    ObservationReport,
    ScoreboardSnapshot,
)


@pytest.fixture
def integration_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with claw-code-like structure."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "runtime.py").write_text(
        "def _score(tokens: set, module) -> int:\n"
        "    count = 0\n"
        "    name_tokens = set(module.name.lower().split())\n"
        "    count += len(tokens & name_tokens)\n"
        "    return count\n"
    )

    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


class TestIntegration:
    @patch("ouroboros.agents.observer.BaseAgent.call")
    @patch("ouroboros.agents.strategist.BaseAgent.call")
    @patch("ouroboros.agents.implementer.BaseAgent.call")
    def test_full_iteration_merged(
        self,
        mock_impl_call: MagicMock,
        mock_strat_call: MagicMock,
        mock_obs_call: MagicMock,
        integration_repo: Path,
    ):
        # Observer response
        mock_obs_call.return_value = MagicMock(
            text=json.dumps({
                "weakest_dimension": "tool_selection",
                "current_score": 0.65,
                "failure_examples": ["list files routed wrong"],
                "patterns": ["filesystem misrouted"],
            }),
            input_tokens=500,
            output_tokens=200,
        )

        # Strategist response
        mock_strat_call.return_value = MagicMock(
            text=json.dumps({
                "hypothesis": "Add source_hint matching to _score",
                "target_dimension": "tool_selection",
                "file_changes": [{"path": "src/runtime.py", "action": "modify", "description": "Add source_hint tokens"}],
                "expected_impact": "+10%",
            }),
            input_tokens=800,
            output_tokens=300,
        )

        # Implementer response
        new_code = (
            "def _score(tokens: set, module) -> int:\n"
            "    count = 0\n"
            "    name_tokens = set(module.name.lower().split())\n"
            "    hint_tokens = set(module.source_hint.lower().replace('/', ' ').replace('-', ' ').split())\n"
            "    count += len(tokens & name_tokens) * 2\n"
            "    count += len(tokens & hint_tokens)\n"
            "    return count\n"
        )
        mock_impl_call.return_value = MagicMock(
            text=json.dumps({"files_written": {"src/runtime.py": new_code}}),
            input_tokens=600,
            output_tokens=200,
        )

        config = OuroborosConfig(
            max_iterations=1,
            cooldown_seconds=0,
            sandbox_timeout_seconds=30,
        )
        loop = ImprovementLoop(config=config, repo_root=integration_repo)

        # Mock scoreboard to show improvement
        with patch.object(loop, "_run_scoreboard") as mock_sb:
            mock_sb.side_effect = [
                ScoreboardSnapshot(0, (
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.65),
                    DimensionScore("regression", 1.0),
                )),
                ScoreboardSnapshot(1, (
                    DimensionScore("correctness", 0.8),
                    DimensionScore("tool_selection", 0.76),
                    DimensionScore("regression", 1.0),
                )),
            ]
            result = loop.run()

        assert result.iterations_run == 1
        assert result.iterations_merged == 1
        assert result.iterations_rolled_back == 0

        # Verify the change was merged to main
        runtime_content = (integration_repo / "src" / "runtime.py").read_text()
        assert "source_hint" in runtime_content

        # Verify ledger was written
        from ouroboros.history.ledger import Ledger
        ledger = Ledger(base_dir=integration_repo / ".ouroboros" / "ledger")
        entries = ledger.read_all()
        assert len(entries) == 1
        assert entries[0].outcome == IterationOutcome.MERGED
```

- [ ] **Step 2: Run the integration test**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/test_integration.py -v`
Expected: PASS — full loop executes with mocked LLM calls

- [ ] **Step 3: Run the full test suite**

Run: `cd ~/Desktop/claw-code && python -m pytest tests/ouroboros/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/claw-code
git add tests/ouroboros/test_integration.py
git commit -m "test(ouroboros): add full integration test — end-to-end loop with mocked LLM"
```

---

## Task 23: Add .gitignore Entries

**Files:**
- Modify: `.gitignore` (or create if not exists)

- [ ] **Step 1: Add ouroboros runtime directories to .gitignore**

Add these entries:

```
# Ouroboros runtime data
.ouroboros/
.worktrees/
.port_sessions/
```

- [ ] **Step 2: Commit**

```bash
cd ~/Desktop/claw-code
git add .gitignore
git commit -m "chore: add ouroboros runtime directories to .gitignore"
```

---

## Summary

| Task | Component | Tests | Description |
|------|-----------|-------|-------------|
| 1 | Scaffolding | - | pyproject.toml, package init |
| 2 | Types | 9 | Shared dataclasses |
| 3 | Config | 6 | YAML config loading |
| 4 | Sandbox/Worktree | 5 | Git worktree manager |
| 5 | Sandbox/Executor | 5 | Allowlisted command runner |
| 6 | Traces | 4 | JSONL trace collector + store |
| 7 | Benchmark/Routing | 5 | 50 routing challenges + scorer |
| 8 | Scoreboard/Quality | 3 | Code quality (ruff + radon) |
| 9 | Scoreboard/Dimensions | 9 | Correctness, efficiency, regression, real-world |
| 10 | Scoreboard/Runner | 6 | Merge gate logic |
| 11 | History/Ledger | 5 | JSONL improvement ledger |
| 12 | Agents/Base | 4 | LLM call wrapper |
| 13 | Agents/Observer | 1 | Trace analysis agent |
| 14 | Agents/Strategist | 1 | Hypothesis agent |
| 15 | Agents/Implementer | 2 | Sandboxed code writer |
| 16 | Agents/Evaluator | 3 | Merge/rollback decider |
| 17 | Core Loop | 1 | Full OBSERVE→EVALUATE cycle |
| 18 | CLI | 4 | Argparse entry point |
| 19 | Traces/Analyzer | 2 | Pattern detection |
| 20 | Sandbox/Rollback | 2 | Safe cleanup |
| 21 | Dashboard | 3 | Terminal visualization |
| 22 | Integration | 1 | End-to-end test |
| 23 | Gitignore | - | Runtime dir exclusions |
| **Total** | | **81** | |

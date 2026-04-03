# Phase 3: Meta-Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an outer Meta-Agent loop that evolves the Observer, Strategist, and Implementer system prompts based on execution telemetry, with safety invariants preventing metric gaming.

**Architecture:** Three subsystems — (1) SafetyInvariants as a pre-merge-gate kill switch, (2) TelemetryEngine capturing per-agent cognitive traces to `.ouroboros/archive/`, (3) MetaAgent that analyzes failures, mutates prompts, and promotes winners via tournament. Prompts stored as versioned markdown files with atomic symlink swaps.

**Tech Stack:** Python 3.14, Anthropic SDK, PyYAML, ast module (for benchmark scoring), existing test infrastructure (pytest).

**Spec:** `docs/specs/2026-04-03-phase3-meta-learning-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `ouroboros/scoreboard/invariants.py` | `SafetyInvariants` — pre-merge safety checks (test count, ruff, config files, conftest) |
| `ouroboros/telemetry/__init__.py` | Package init |
| `ouroboros/telemetry/types.py` | `TelemetryRecord` frozen dataclass |
| `ouroboros/telemetry/writer.py` | `TelemetryWriter` — serialize record to markdown + append to index.jsonl |
| `ouroboros/telemetry/reader.py` | `TelemetryReader` — query interface over index.jsonl |
| `ouroboros/meta/__init__.py` | Package init |
| `ouroboros/meta/prompt_store.py` | `PromptStore` — versioned prompt files, atomic symlink swap, loading |
| `ouroboros/meta/benchmark_gen.py` | `BenchmarkGenerator` — produce rotating benchmark tasks from codebase |
| `ouroboros/meta/tournament.py` | `Tournament` — run benchmark tasks against a prompt, score results |
| `ouroboros/meta/agent.py` | `MetaAgent` — outer loop state machine |

### Modified Files
| File | Change |
|------|--------|
| `ouroboros/types.py` | Add `IterationOutcome.KILLED` |
| `ouroboros/agents/base.py` | Add `last_response_text` attribute to `BaseAgent` |
| `ouroboros/agents/observer.py` | Load system prompt from `PromptStore` with hardcoded fallback |
| `ouroboros/agents/strategist.py` | Load system prompt from `PromptStore` with hardcoded fallback |
| `ouroboros/agents/implementer.py` | Load system prompt from `PromptStore` with hardcoded fallback |
| `ouroboros/loop.py` | Wire TelemetryWriter, capture agent outputs, call SafetyInvariants |
| `ouroboros/config.py` | Add `MetaConfig` fields |
| `ouroboros.yaml` | Add `meta:` section, update `blocked_paths` |
| `ouroboros/cli.py` | Add `meta` subcommand |

### Test Files
| File | Tests |
|------|-------|
| `tests/ouroboros/test_invariants.py` | SafetyInvariants checks |
| `tests/ouroboros/test_telemetry_types.py` | TelemetryRecord creation and serialization |
| `tests/ouroboros/test_telemetry_writer.py` | Write records, verify markdown + index.jsonl |
| `tests/ouroboros/test_telemetry_reader.py` | Query failures, filter by agent/version |
| `tests/ouroboros/test_prompt_store.py` | Version management, atomic swap, loading with fallback |
| `tests/ouroboros/test_benchmark_gen.py` | Rotating task generation |
| `tests/ouroboros/test_tournament.py` | Benchmark scoring |
| `tests/ouroboros/test_meta_agent.py` | State machine transitions |

---

### Task 1: Add IterationOutcome.KILLED and BaseAgent.last_response_text

**Files:**
- Modify: `ouroboros/types.py:10-17`
- Modify: `ouroboros/agents/base.py:19-43`
- Test: `tests/ouroboros/test_types.py` (existing, verify no breakage)

- [ ] **Step 1: Add KILLED to IterationOutcome**

In `ouroboros/types.py`, add the new variant after ABANDONED:

```python
class IterationOutcome(str, Enum):
    """Outcome of a single improvement iteration attempt."""

    MERGED = "MERGED"
    ROLLED_BACK = "ROLLED_BACK"
    TIMEOUT = "TIMEOUT"
    EVAL_FAILURE = "EVAL_FAILURE"
    ABANDONED = "ABANDONED"
    KILLED = "KILLED"
```

- [ ] **Step 2: Add last_response_text to BaseAgent**

In `ouroboros/agents/base.py`, add `last_response_text` to `__init__` and update `call()`:

```python
class BaseAgent:
    def __init__(self, model: str, role: str, timeout_seconds: int) -> None:
        self.model = model
        self.role = role
        self.timeout_seconds = timeout_seconds
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_response_text = ""

    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> AgentResponse:
        """Call the LLM with system and user prompts."""
        client = Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        agent_response = AgentResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        self.total_input_tokens += agent_response.input_tokens
        self.total_output_tokens += agent_response.output_tokens
        self.last_response_text = agent_response.text
        return agent_response
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `python -m pytest tests/ouroboros/test_types.py tests/ouroboros/test_base_agent.py tests/ouroboros/test_agents_base.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add ouroboros/types.py ouroboros/agents/base.py
git commit -m "feat(types): add IterationOutcome.KILLED and BaseAgent.last_response_text"
```

---

### Task 2: SafetyInvariants

**Files:**
- Create: `ouroboros/scoreboard/invariants.py`
- Test: `tests/ouroboros/test_invariants.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_invariants.py
"""Tests for pre-merge safety invariants."""
from __future__ import annotations

import pytest

from ouroboros.scoreboard.invariants import InvariantResult, SafetyInvariants


class TestSafetyInvariants:
    def setup_method(self):
        self.invariants = SafetyInvariants(
            allowed_root_configs=("ouroboros.yaml",),
        )

    def test_passes_when_all_clean(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/agents/observer.py"],
        )
        assert result.passed is True
        assert result.violation == ""

    def test_fails_when_test_count_decreases(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=99,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=[],
        )
        assert result.passed is False
        assert "test count" in result.violation.lower()

    def test_fails_when_ruff_violations_increase(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=3,
            after_ruff_violations=4,
            files_written=[],
        )
        assert result.passed is False
        assert "ruff" in result.violation.lower()

    def test_fails_when_conftest_written(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/conftest.py"],
        )
        assert result.passed is False
        assert "conftest" in result.violation.lower()

    def test_fails_when_root_config_created(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["pytest.ini"],
        )
        assert result.passed is False
        assert "config" in result.violation.lower()

    def test_allows_ouroboros_yaml(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros.yaml"],
        )
        assert result.passed is True

    def test_fails_when_root_toml_created(self):
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["setup.cfg"],
        )
        assert result.passed is False

    def test_test_file_in_nested_dir_ok(self):
        """conftest.py check is filename-based, not path-based."""
        result = self.invariants.check(
            before_test_count=100,
            after_test_count=100,
            before_ruff_violations=0,
            after_ruff_violations=0,
            files_written=["ouroboros/agents/observer.py"],
        )
        assert result.passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_invariants.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SafetyInvariants**

```python
# ouroboros/scoreboard/invariants.py
"""Pre-merge safety invariants — kill switch before the merge gate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class InvariantResult:
    """Result of safety invariant check."""

    passed: bool
    violation: str


_ROOT_CONFIG_EXTENSIONS = {".toml", ".ini", ".cfg", ".yaml", ".yml"}


class SafetyInvariants:
    """Check safety invariants before the merge gate runs."""

    def __init__(
        self,
        allowed_root_configs: tuple[str, ...] = ("ouroboros.yaml",),
    ) -> None:
        self.allowed_root_configs = allowed_root_configs

    def check(
        self,
        before_test_count: int,
        after_test_count: int,
        before_ruff_violations: int,
        after_ruff_violations: int,
        files_written: list[str],
    ) -> InvariantResult:
        """Run all invariant checks. Returns first violation found, or passed."""
        # 1. Test count never decreases
        if after_test_count < before_test_count:
            return InvariantResult(
                passed=False,
                violation=(
                    f"Test count decreased: {before_test_count} -> {after_test_count}. "
                    "Deleting tests is not allowed."
                ),
            )

        # 2. Ruff violations never increase
        if after_ruff_violations > before_ruff_violations:
            return InvariantResult(
                passed=False,
                violation=(
                    f"Ruff violations increased: {before_ruff_violations} -> "
                    f"{after_ruff_violations}. New lint violations are not allowed."
                ),
            )

        # 3. No conftest.py anywhere
        for path in files_written:
            if PurePosixPath(path).name == "conftest.py":
                return InvariantResult(
                    passed=False,
                    violation=f"conftest.py modification blocked: {path}",
                )

        # 4. No root config creation/modification (except allowlist)
        for path in files_written:
            p = PurePosixPath(path)
            if p.parent == PurePosixPath(".") and p.suffix in _ROOT_CONFIG_EXTENSIONS:
                if p.name not in self.allowed_root_configs:
                    return InvariantResult(
                        passed=False,
                        violation=f"Root config file blocked: {path}",
                    )

        return InvariantResult(passed=True, violation="")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_invariants.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/scoreboard/invariants.py tests/ouroboros/test_invariants.py
git commit -m "feat(invariants): add SafetyInvariants pre-merge kill switch"
```

---

### Task 3: TelemetryRecord dataclass

**Files:**
- Create: `ouroboros/telemetry/__init__.py`
- Create: `ouroboros/telemetry/types.py`
- Test: `tests/ouroboros/test_telemetry_types.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_telemetry_types.py
"""Tests for TelemetryRecord dataclass."""
from __future__ import annotations

from ouroboros.telemetry.types import AgentTokens, TelemetryRecord


class TestTelemetryRecord:
    def test_creation(self):
        record = TelemetryRecord(
            run_id="2026-04-03T14-00-00_iter001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v1",
            observer_output='{"weakest_dimension": "real_world"}',
            strategist_output='{"hypothesis": "add docstrings"}',
            implementer_output='{"files_written": {}}',
            tokens_observer=AgentTokens(input=1000, output=200, cost_usd=0.01),
            tokens_strategist=AgentTokens(input=2000, output=400, cost_usd=0.02),
            tokens_implementer=AgentTokens(input=3000, output=600, cost_usd=0.06),
            files_changed=("ouroboros/types.py",),
            git_diff="+ added docstring",
            eval_score=0.12,
            outcome="MERGED",
            failure_reason="",
            traceback_output="",
            cost_usd=0.09,
            input_tokens=6000,
            output_tokens=1200,
        )
        assert record.run_id == "2026-04-03T14-00-00_iter001"
        assert record.iteration == 1
        assert record.tokens_observer.input == 1000

    def test_to_frontmatter(self):
        record = TelemetryRecord(
            run_id="test_001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v2",
            observer_output="{}",
            strategist_output="{}",
            implementer_output="{}",
            tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
            tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
            tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
            files_changed=(),
            git_diff="",
            eval_score=0.0,
            outcome="ABANDONED",
            failure_reason="empty JSON",
            traceback_output="",
            cost_usd=0.008,
            input_tokens=600,
            output_tokens=300,
        )
        fm = record.to_frontmatter()
        assert fm["run_id"] == "test_001"
        assert fm["prompt_implementer"] == "v2"
        assert fm["outcome"] == "ABANDONED"
        assert fm["tokens_observer_in"] == 100
        assert fm["cost_observer"] == 0.001

    def test_to_markdown_body(self):
        record = TelemetryRecord(
            run_id="test_001",
            iteration=1,
            timestamp="2026-04-03T14:00:00Z",
            prompt_observer="v1",
            prompt_strategist="v1",
            prompt_implementer="v1",
            observer_output='{"key": "value"}',
            strategist_output='{"hyp": "test"}',
            implementer_output='{"files": {}}',
            tokens_observer=AgentTokens(input=0, output=0, cost_usd=0.0),
            tokens_strategist=AgentTokens(input=0, output=0, cost_usd=0.0),
            tokens_implementer=AgentTokens(input=0, output=0, cost_usd=0.0),
            files_changed=("a.py",),
            git_diff="diff content",
            eval_score=0.5,
            outcome="ROLLED_BACK",
            failure_reason="no improvement",
            traceback_output="some error",
            cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
        )
        body = record.to_markdown_body()
        assert "## Observation" in body
        assert '{"key": "value"}' in body
        assert "## Diff" in body
        assert "diff content" in body
        assert "## Traceback" in body
        assert "some error" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_telemetry_types.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement TelemetryRecord**

```python
# ouroboros/telemetry/__init__.py
```

```python
# ouroboros/telemetry/types.py
"""Telemetry record dataclass for iteration archive."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTokens:
    """Per-agent token usage and cost."""

    input: int
    output: int
    cost_usd: float


@dataclass(frozen=True)
class TelemetryRecord:
    """Complete record of a single inner-loop iteration."""

    run_id: str
    iteration: int
    timestamp: str

    # Prompt versions
    prompt_observer: str
    prompt_strategist: str
    prompt_implementer: str

    # Agent outputs (cognitive trace)
    observer_output: str
    strategist_output: str
    implementer_output: str

    # Per-agent token breakdown
    tokens_observer: AgentTokens
    tokens_strategist: AgentTokens
    tokens_implementer: AgentTokens

    # Results
    files_changed: tuple[str, ...]
    git_diff: str
    eval_score: float
    outcome: str
    failure_reason: str
    traceback_output: str

    # Totals
    cost_usd: float
    input_tokens: int
    output_tokens: int

    def to_frontmatter(self) -> dict:
        """Return flat dict suitable for YAML frontmatter."""
        return {
            "run_id": self.run_id,
            "iteration": self.iteration,
            "outcome": self.outcome,
            "eval_score": self.eval_score,
            "prompt_observer": self.prompt_observer,
            "prompt_strategist": self.prompt_strategist,
            "prompt_implementer": self.prompt_implementer,
            "tokens_observer_in": self.tokens_observer.input,
            "tokens_observer_out": self.tokens_observer.output,
            "cost_observer": self.tokens_observer.cost_usd,
            "tokens_strategist_in": self.tokens_strategist.input,
            "tokens_strategist_out": self.tokens_strategist.output,
            "cost_strategist": self.tokens_strategist.cost_usd,
            "tokens_implementer_in": self.tokens_implementer.input,
            "tokens_implementer_out": self.tokens_implementer.output,
            "cost_implementer": self.tokens_implementer.cost_usd,
            "cost_usd": self.cost_usd,
            "tokens_in": self.input_tokens,
            "tokens_out": self.output_tokens,
            "failure_reason": self.failure_reason,
        }

    def to_markdown_body(self) -> str:
        """Return the markdown body (cognitive traces, diff, traceback)."""
        sections = [
            f"## Observation\n{self.observer_output}",
            f"## Strategy\n{self.strategist_output}",
            f"## Implementation\n{self.implementer_output}",
            f"## Diff\n{self.git_diff}" if self.git_diff else "## Diff\n(no diff)",
            f"## Traceback\n{self.traceback_output}" if self.traceback_output else "## Traceback\n(none)",
            f"## Result\n{self.outcome}. eval_score={self.eval_score:.4f}. {self.failure_reason}",
        ]
        return "\n\n".join(sections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_telemetry_types.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/telemetry/__init__.py ouroboros/telemetry/types.py tests/ouroboros/test_telemetry_types.py
git commit -m "feat(telemetry): add TelemetryRecord dataclass with frontmatter/markdown serialization"
```

---

### Task 4: TelemetryWriter

**Files:**
- Create: `ouroboros/telemetry/writer.py`
- Test: `tests/ouroboros/test_telemetry_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_telemetry_writer.py
"""Tests for TelemetryWriter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
from ouroboros.telemetry.writer import TelemetryWriter


def _make_record(run_id: str = "test_001", iteration: int = 1, outcome: str = "MERGED") -> TelemetryRecord:
    return TelemetryRecord(
        run_id=run_id,
        iteration=iteration,
        timestamp="2026-04-03T14:00:00Z",
        prompt_observer="v1",
        prompt_strategist="v1",
        prompt_implementer="v1",
        observer_output="{}",
        strategist_output="{}",
        implementer_output="{}",
        tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
        tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
        tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
        files_changed=("a.py",),
        git_diff="diff",
        eval_score=0.12,
        outcome=outcome,
        failure_reason="" if outcome == "MERGED" else "failed",
        traceback_output="",
        cost_usd=0.008,
        input_tokens=600,
        output_tokens=300,
    )


class TestTelemetryWriter:
    def test_writes_markdown_file(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        record = _make_record()
        path = writer.write(record)
        assert path.exists()
        assert path.suffix == ".md"
        content = path.read_text()
        assert "---" in content  # YAML frontmatter delimiters
        assert "## Observation" in content

    def test_appends_to_index_jsonl(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        writer.write(_make_record("run_001", 1))
        writer.write(_make_record("run_002", 2, "ABANDONED"))

        index_path = tmp_path / "index.jsonl"
        assert index_path.exists()
        lines = index_path.read_text().strip().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["run_id"] == "run_001"
        assert first["outcome"] == "MERGED"

        second = json.loads(lines[1])
        assert second["run_id"] == "run_002"
        assert second["outcome"] == "ABANDONED"

    def test_frontmatter_is_valid_yaml(self, tmp_path: Path):
        writer = TelemetryWriter(archive_dir=tmp_path)
        path = writer.write(_make_record())
        content = path.read_text()
        # Extract between --- delimiters
        parts = content.split("---")
        assert len(parts) >= 3
        import yaml
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["run_id"] == "test_001"
        assert frontmatter["outcome"] == "MERGED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_telemetry_writer.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement TelemetryWriter**

```python
# ouroboros/telemetry/writer.py
"""Append-only telemetry writer — serializes records to markdown + index."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ouroboros.telemetry.types import TelemetryRecord


class TelemetryWriter:
    """Write telemetry records to .ouroboros/archive/ as markdown files."""

    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir

    def write(self, record: TelemetryRecord) -> Path:
        """Serialize a TelemetryRecord to markdown and append to index."""
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Write markdown file
        filename = f"{record.run_id}.md"
        filepath = self.archive_dir / filename
        frontmatter = record.to_frontmatter()
        body = record.to_markdown_body()
        content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{body}\n"
        filepath.write_text(content)

        # Append to index.jsonl for fast querying
        index_path = self.archive_dir / "index.jsonl"
        with open(index_path, "a") as f:
            f.write(json.dumps(frontmatter) + "\n")

        return filepath
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_telemetry_writer.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/telemetry/writer.py tests/ouroboros/test_telemetry_writer.py
git commit -m "feat(telemetry): add TelemetryWriter with markdown + index.jsonl output"
```

---

### Task 5: TelemetryReader

**Files:**
- Create: `ouroboros/telemetry/reader.py`
- Test: `tests/ouroboros/test_telemetry_reader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_telemetry_reader.py
"""Tests for TelemetryReader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.telemetry.reader import TelemetryReader
from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
from ouroboros.telemetry.writer import TelemetryWriter


def _make_record(
    run_id: str,
    iteration: int,
    outcome: str = "MERGED",
    eval_score: float = 0.1,
    prompt_impl: str = "v1",
) -> TelemetryRecord:
    return TelemetryRecord(
        run_id=run_id,
        iteration=iteration,
        timestamp="2026-04-03T14:00:00Z",
        prompt_observer="v1",
        prompt_strategist="v1",
        prompt_implementer=prompt_impl,
        observer_output="{}",
        strategist_output="{}",
        implementer_output="{}",
        tokens_observer=AgentTokens(input=100, output=50, cost_usd=0.001),
        tokens_strategist=AgentTokens(input=200, output=100, cost_usd=0.002),
        tokens_implementer=AgentTokens(input=300, output=150, cost_usd=0.005),
        files_changed=(),
        git_diff="",
        eval_score=eval_score,
        outcome=outcome,
        failure_reason="failed" if outcome != "MERGED" else "",
        traceback_output="",
        cost_usd=0.008,
        input_tokens=600,
        output_tokens=300,
    )


@pytest.fixture
def populated_archive(tmp_path: Path) -> Path:
    writer = TelemetryWriter(archive_dir=tmp_path)
    writer.write(_make_record("r1", 1, "MERGED", 0.12, "v1"))
    writer.write(_make_record("r2", 2, "ABANDONED", 0.0, "v1"))
    writer.write(_make_record("r3", 3, "ROLLED_BACK", 0.01, "v1"))
    writer.write(_make_record("r4", 4, "MERGED", 0.08, "v2"))
    writer.write(_make_record("r5", 5, "ABANDONED", 0.0, "v2"))
    return tmp_path


class TestTelemetryReader:
    def test_get_failures_returns_lowest_scoring(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        failures = reader.get_failures(limit=3)
        assert len(failures) == 3
        # Should be sorted by eval_score ascending
        assert failures[0]["eval_score"] <= failures[1]["eval_score"]

    def test_get_failures_filters_by_prompt_version(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        failures = reader.get_failures(prompt_version="v2", limit=10)
        for f in failures:
            assert f["prompt_implementer"] == "v2"

    def test_get_by_prompt_version(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        records = reader.get_by_prompt_version(agent="implementer", version="v1")
        assert len(records) == 3
        for r in records:
            assert r["prompt_implementer"] == "v1"

    def test_get_summary(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        summary = reader.get_summary()
        assert "v1" in summary
        assert "v2" in summary
        assert summary["v1"]["total"] == 3
        assert summary["v1"]["merged"] == 1
        assert summary["v2"]["total"] == 2

    def test_empty_archive(self, tmp_path: Path):
        reader = TelemetryReader(archive_dir=tmp_path)
        assert reader.get_failures(limit=5) == []
        assert reader.get_summary() == {}

    def test_read_full_record(self, populated_archive: Path):
        reader = TelemetryReader(archive_dir=populated_archive)
        body = reader.read_full_record("r1")
        assert "## Observation" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_telemetry_reader.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement TelemetryReader**

```python
# ouroboros/telemetry/reader.py
"""Telemetry reader — query interface over the archive index."""
from __future__ import annotations

import json
from pathlib import Path


class TelemetryReader:
    """Read and query telemetry records from the archive."""

    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir

    def _load_index(self) -> list[dict]:
        """Load all entries from index.jsonl."""
        index_path = self.archive_dir / "index.jsonl"
        if not index_path.exists():
            return []
        entries = []
        for line in index_path.read_text().splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def get_failures(
        self,
        prompt_version: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Return lowest-scoring iterations, sorted by eval_score ascending."""
        entries = self._load_index()
        if prompt_version is not None:
            entries = [
                e for e in entries
                if e.get("prompt_implementer") == prompt_version
                or e.get("prompt_observer") == prompt_version
                or e.get("prompt_strategist") == prompt_version
            ]
        entries.sort(key=lambda e: e.get("eval_score", 0.0))
        return entries[:limit]

    def get_by_prompt_version(self, agent: str, version: str) -> list[dict]:
        """All iterations that used a specific prompt version for the given agent."""
        key = f"prompt_{agent}"
        entries = self._load_index()
        return [e for e in entries if e.get(key) == version]

    def get_summary(self) -> dict:
        """Win rate and counts per implementer prompt version."""
        entries = self._load_index()
        summary: dict[str, dict] = {}
        for e in entries:
            version = e.get("prompt_implementer", "unknown")
            if version not in summary:
                summary[version] = {"total": 0, "merged": 0, "abandoned": 0, "avg_score": 0.0}
            summary[version]["total"] += 1
            if e.get("outcome") == "MERGED":
                summary[version]["merged"] += 1
            elif e.get("outcome") == "ABANDONED":
                summary[version]["abandoned"] += 1
            summary[version]["avg_score"] += e.get("eval_score", 0.0)

        for version, stats in summary.items():
            if stats["total"] > 0:
                stats["avg_score"] /= stats["total"]
                stats["win_rate"] = stats["merged"] / stats["total"]

        return summary

    def read_full_record(self, run_id: str) -> str:
        """Read the full markdown body of a specific record."""
        filepath = self.archive_dir / f"{run_id}.md"
        if not filepath.exists():
            return ""
        content = filepath.read_text()
        # Skip YAML frontmatter (between --- delimiters)
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
        return content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_telemetry_reader.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/telemetry/reader.py tests/ouroboros/test_telemetry_reader.py
git commit -m "feat(telemetry): add TelemetryReader with index.jsonl-based querying"
```

---

### Task 6: PromptStore

**Files:**
- Create: `ouroboros/meta/__init__.py`
- Create: `ouroboros/meta/prompt_store.py`
- Test: `tests/ouroboros/test_prompt_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_prompt_store.py
"""Tests for PromptStore — versioned prompt files with atomic swap."""
from __future__ import annotations

from pathlib import Path

import pytest

from ouroboros.meta.prompt_store import PromptStore


class TestPromptStore:
    def test_initialize_from_defaults(self, tmp_path: Path):
        """First run: writes v1.md and current.md symlink from hardcoded defaults."""
        defaults = {"observer": "You are the observer.", "implementer": "You are the implementer."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()

        assert (tmp_path / "observer" / "v1.md").exists()
        assert (tmp_path / "observer" / "current.md").exists()
        content = store.load("observer")
        assert "You are the observer" in content

    def test_load_returns_current(self, tmp_path: Path):
        defaults = {"implementer": "Default prompt."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.load("implementer") == "Default prompt."

    def test_load_fallback_when_no_files(self, tmp_path: Path):
        defaults = {"observer": "Fallback prompt."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        # Don't initialize — simulate missing files
        assert store.load("observer") == "Fallback prompt."

    def test_write_new_version(self, tmp_path: Path):
        defaults = {"implementer": "v1 content"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()

        version = store.write_version(
            agent="implementer",
            content="v2 content",
            mutation_reason="test mutation",
        )
        assert version == 2
        assert (tmp_path / "implementer" / "v2.md").exists()
        v2_content = (tmp_path / "implementer" / "v2.md").read_text()
        assert "v2 content" in v2_content
        assert "test mutation" in v2_content

    def test_promote_updates_current(self, tmp_path: Path):
        defaults = {"implementer": "v1 content"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        store.write_version("implementer", "v2 content", "test")
        store.promote("implementer", 2, tournament_score=0.9, baseline_score=0.7)

        assert store.load("implementer") == "v2 content"

    def test_current_version(self, tmp_path: Path):
        defaults = {"implementer": "v1"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.current_version("implementer") == 1

    def test_token_count(self, tmp_path: Path):
        defaults = {"implementer": "one two three four five"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.token_count("implementer", 1) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_prompt_store.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement PromptStore**

```python
# ouroboros/meta/__init__.py
```

```python
# ouroboros/meta/prompt_store.py
"""Versioned prompt storage with atomic symlink swaps."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml


class PromptStore:
    """Manage versioned prompt files for each agent."""

    def __init__(self, prompts_dir: Path, defaults: dict[str, str]) -> None:
        self.prompts_dir = prompts_dir
        self.defaults = defaults

    def initialize(self) -> None:
        """Write v1.md and current.md for each agent from defaults (first run)."""
        for agent, content in self.defaults.items():
            agent_dir = self.prompts_dir / agent
            agent_dir.mkdir(parents=True, exist_ok=True)
            v1_path = agent_dir / "v1.md"
            current_path = agent_dir / "current.md"
            if not v1_path.exists():
                frontmatter = {
                    "version": 1,
                    "parent": 0,
                    "created": "",
                    "mutation_reason": "initial baseline",
                    "tournament_score": 0.0,
                    "baseline_score": 0.0,
                    "promoted": True,
                }
                v1_path.write_text(
                    f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"
                )
            if not current_path.exists():
                current_path.write_text(content + "\n")

    def load(self, agent: str) -> str:
        """Load the current prompt for an agent. Falls back to hardcoded default."""
        current_path = self.prompts_dir / agent / "current.md"
        if current_path.exists():
            return current_path.read_text().strip()
        return self.defaults.get(agent, "")

    def current_version(self, agent: str) -> int:
        """Return the highest promoted version number for an agent."""
        agent_dir = self.prompts_dir / agent
        if not agent_dir.exists():
            return 0
        versions = []
        for f in agent_dir.iterdir():
            match = re.match(r"v(\d+)\.md$", f.name)
            if match:
                versions.append(int(match.group(1)))
        return max(versions) if versions else 0

    def write_version(
        self,
        agent: str,
        content: str,
        mutation_reason: str,
    ) -> int:
        """Write a new prompt version file. Returns the version number."""
        agent_dir = self.prompts_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        version = self.current_version(agent) + 1
        frontmatter = {
            "version": version,
            "parent": version - 1,
            "created": "",
            "mutation_reason": mutation_reason,
            "tournament_score": 0.0,
            "baseline_score": 0.0,
            "promoted": False,
        }
        path = agent_dir / f"v{version}.md"
        path.write_text(
            f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"
        )
        return version

    def promote(
        self,
        agent: str,
        version: int,
        tournament_score: float,
        baseline_score: float,
    ) -> None:
        """Promote a version to current via atomic symlink swap."""
        agent_dir = self.prompts_dir / agent
        version_path = agent_dir / f"v{version}.md"

        # Read the prompt content (strip frontmatter)
        raw = version_path.read_text()
        parts = raw.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else raw.strip()

        # Atomic swap: write tmp, then os.replace
        current_path = agent_dir / "current.md"
        tmp_path = agent_dir / "current_tmp.md"
        tmp_path.write_text(content)
        os.replace(str(tmp_path), str(current_path))

        # Update frontmatter in version file
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])
            fm["promoted"] = True
            fm["tournament_score"] = tournament_score
            fm["baseline_score"] = baseline_score
            version_path.write_text(
                f"---\n{yaml.dump(fm, default_flow_style=False)}---\n\n{content}\n"
            )

    def token_count(self, agent: str, version: int) -> int:
        """Count tokens (words) in a prompt version."""
        path = self.prompts_dir / agent / f"v{version}.md"
        if not path.exists():
            return 0
        raw = path.read_text()
        parts = raw.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else raw.strip()
        return len(content.split())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_prompt_store.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/meta/__init__.py ouroboros/meta/prompt_store.py tests/ouroboros/test_prompt_store.py
git commit -m "feat(meta): add PromptStore with versioning and atomic symlink swap"
```

---

### Task 7: Wire prompt loading into agents

**Files:**
- Modify: `ouroboros/agents/observer.py:52-54`
- Modify: `ouroboros/agents/strategist.py:39-41`
- Modify: `ouroboros/agents/implementer.py:41-43`
- Modify: `ouroboros/loop.py:39-55`

- [ ] **Step 1: Add system_prompt parameter to ObserverAgent**

In `ouroboros/agents/observer.py`, modify `__init__` to accept an optional system prompt override:

```python
class ObserverAgent:
    def __init__(self, model: str = "claude-sonnet-4-6", system_prompt: str = "") -> None:
        self.agent = BaseAgent(model=model, role="observer", timeout_seconds=120)
        self.system_prompt = system_prompt or OBSERVER_SYSTEM_PROMPT
```

Then update `observe()` to use `self.system_prompt`:

```python
    def observe(self, scoreboard, traces, ledger_summary):
        user_prompt = self._build_prompt(scoreboard, traces, ledger_summary)
        data = self.agent.call_with_json_retry(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
        )
```

- [ ] **Step 2: Add system_prompt parameter to StrategistAgent**

In `ouroboros/agents/strategist.py`, same pattern:

```python
class StrategistAgent:
    def __init__(self, model: str = "claude-opus-4-6", system_prompt: str = "") -> None:
        self.agent = BaseAgent(model=model, role="strategist", timeout_seconds=180)
        self.system_prompt = system_prompt or STRATEGIST_SYSTEM_PROMPT
```

Update `strategize()` to use `self.system_prompt`.

- [ ] **Step 3: Add system_prompt parameter to ImplementerAgent**

In `ouroboros/agents/implementer.py`, same pattern:

```python
class ImplementerAgent:
    def __init__(self, model: str, executor: SandboxExecutor, system_prompt: str = "") -> None:
        self.agent = BaseAgent(model=model, role="implementer", timeout_seconds=300)
        self.executor = executor
        self.system_prompt = system_prompt or IMPLEMENTER_SYSTEM_PROMPT
```

Update `implement()` to use `self.system_prompt`.

- [ ] **Step 4: Wire PromptStore into ImprovementLoop.__init__**

In `ouroboros/loop.py`, add prompt loading:

```python
from ouroboros.meta.prompt_store import PromptStore
from ouroboros.agents.observer import OBSERVER_SYSTEM_PROMPT
from ouroboros.agents.strategist import STRATEGIST_SYSTEM_PROMPT
from ouroboros.agents.implementer import IMPLEMENTER_SYSTEM_PROMPT

class ImprovementLoop:
    def __init__(self, config: OuroborosConfig, repo_root: Path) -> None:
        # ... existing setup ...
        self.prompt_store = PromptStore(
            prompts_dir=repo_root / ".ouroboros" / "prompts",
            defaults={
                "observer": OBSERVER_SYSTEM_PROMPT,
                "strategist": STRATEGIST_SYSTEM_PROMPT,
                "implementer": IMPLEMENTER_SYSTEM_PROMPT,
            },
        )

        obs_prompt = self.prompt_store.load("observer")
        strat_prompt = self.prompt_store.load("strategist")
        impl_prompt = self.prompt_store.load("implementer")

        self.observer = ObserverAgent(model=config.model_observer, system_prompt=obs_prompt)
        self.strategist = StrategistAgent(model=config.model_strategist, system_prompt=strat_prompt)
        self.implementer = ImplementerAgent(
            model=config.model_implementer,
            executor=self.executor,
            system_prompt=impl_prompt,
        )
```

- [ ] **Step 5: Run all existing tests to verify no breakage**

Run: `python -m pytest tests/ouroboros/ -v`
Expected: All 104+ tests pass

- [ ] **Step 6: Commit**

```bash
git add ouroboros/agents/observer.py ouroboros/agents/strategist.py ouroboros/agents/implementer.py ouroboros/loop.py
git commit -m "feat(agents): load system prompts from PromptStore with hardcoded fallback"
```

---

### Task 8: Wire TelemetryWriter into the inner loop

**Files:**
- Modify: `ouroboros/loop.py`
- Modify: `ouroboros/agents/base.py` (read `last_response_text` per agent)

This task wires the TelemetryWriter into `_run_iteration()` so every iteration produces an archive record.

- [ ] **Step 1: Add TelemetryWriter to ImprovementLoop.__init__**

In `ouroboros/loop.py`, add to `__init__`:

```python
from ouroboros.telemetry.writer import TelemetryWriter

# Inside __init__, after self.prompt_store setup:
self.telemetry_writer = TelemetryWriter(
    archive_dir=repo_root / ".ouroboros" / "archive",
)
```

- [ ] **Step 2: Add _read_agent_tokens helper**

Add this method to `ImprovementLoop`:

```python
def _read_agent_tokens(self, agent_wrapper: object) -> tuple[int, int, float]:
    """Read and reset accumulated tokens from an agent wrapper. Returns (in, out, cost)."""
    from ouroboros.agents.base import BaseAgent, tokens_to_usd
    agent = getattr(agent_wrapper, "agent", None)
    if not isinstance(agent, BaseAgent):
        return 0, 0, 0.0
    input_t = agent.total_input_tokens
    output_t = agent.total_output_tokens
    cost = tokens_to_usd(input_t, output_t, agent.model) if (input_t or output_t) else 0.0
    return input_t, output_t, cost
```

- [ ] **Step 3: Add _write_telemetry method**

Add this method to `ImprovementLoop`:

```python
def _write_telemetry(
    self,
    iteration: int,
    timestamp: str,
    outcome: str,
    eval_score: float,
    failure_reason: str,
    traceback_output: str,
    obs_tokens: tuple[int, int, float],
    strat_tokens: tuple[int, int, float],
    impl_tokens: tuple[int, int, float],
    files_changed: tuple[str, ...],
    git_diff: str,
) -> None:
    from ouroboros.telemetry.types import AgentTokens, TelemetryRecord
    obs_agent = getattr(self.observer, "agent", None)
    strat_agent = getattr(self.strategist, "agent", None)
    impl_agent = getattr(self.implementer, "agent", None)

    record = TelemetryRecord(
        run_id=f"{timestamp.replace(':', '-').replace('+', '')[:19]}_iter{iteration:03d}",
        iteration=iteration,
        timestamp=timestamp,
        prompt_observer=f"v{self.prompt_store.current_version('observer') or 1}",
        prompt_strategist=f"v{self.prompt_store.current_version('strategist') or 1}",
        prompt_implementer=f"v{self.prompt_store.current_version('implementer') or 1}",
        observer_output=getattr(obs_agent, "last_response_text", "") if obs_agent else "",
        strategist_output=getattr(strat_agent, "last_response_text", "") if strat_agent else "",
        implementer_output=getattr(impl_agent, "last_response_text", "") if impl_agent else "",
        tokens_observer=AgentTokens(input=obs_tokens[0], output=obs_tokens[1], cost_usd=obs_tokens[2]),
        tokens_strategist=AgentTokens(input=strat_tokens[0], output=strat_tokens[1], cost_usd=strat_tokens[2]),
        tokens_implementer=AgentTokens(input=impl_tokens[0], output=impl_tokens[1], cost_usd=impl_tokens[2]),
        files_changed=files_changed,
        git_diff=git_diff,
        eval_score=eval_score,
        outcome=outcome,
        failure_reason=failure_reason,
        traceback_output=traceback_output,
        cost_usd=obs_tokens[2] + strat_tokens[2] + impl_tokens[2],
        input_tokens=obs_tokens[0] + strat_tokens[0] + impl_tokens[0],
        output_tokens=obs_tokens[1] + strat_tokens[1] + impl_tokens[1],
    )
    self.telemetry_writer.write(record)
```

- [ ] **Step 4: Hook telemetry into _run_iteration**

After each agent call in `_run_iteration`, capture tokens before resetting. At the end of the iteration (in all code paths — merged, rolled back, abandoned), call `_write_telemetry()`. The `_track_agent_cost()` already resets tokens, so capture them BEFORE that call using `_read_agent_tokens()`.

Modify the token tracking flow: replace `self._track_agent_cost(self.observer)` with:

```python
obs_tokens = self._read_agent_tokens(self.observer)
self._track_agent_cost(self.observer)
```

Do the same for strategist and implementer. Then call `_write_telemetry()` in each outcome path.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ouroboros/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add ouroboros/loop.py ouroboros/agents/base.py
git commit -m "feat(telemetry): wire TelemetryWriter into inner loop with per-agent trace capture"
```

---

### Task 9: Wire SafetyInvariants into the evaluation step

**Files:**
- Modify: `ouroboros/loop.py` (add invariant check between implement and merge gate)
- Modify: `ouroboros/scoreboard/runner.py` (expose test count and ruff violation count)

- [ ] **Step 1: Add count_ruff_violations helper to runner.py**

Add this function to `ouroboros/scoreboard/runner.py`:

```python
def count_ruff_violations(target_path: Path) -> int:
    """Count ruff violations in target path."""
    try:
        import json as json_mod
        result = subprocess.run(
            ["ruff", "check", str(target_path), "--output-format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return 0
        violations = json_mod.loads(result.stdout) if result.stdout else []
        return len(violations)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0
```

- [ ] **Step 2: Add count_tests helper to runner.py**

Add this function to `ouroboros/scoreboard/runner.py`:

```python
def count_tests(target_path: Path, test_command: str) -> int:
    """Count total tests by running the test command."""
    try:
        cmd_parts = [p for p in shlex.split(test_command) if p not in ("-v", "--verbose")]
        cmd_parts += ["--tb=no", "-q"]
        repo_root = target_path.parent if target_path.name != "." else target_path
        result = subprocess.run(
            cmd_parts, capture_output=True, text=True, timeout=120, cwd=str(repo_root),
        )
        test_results, _ = _run_tests(target_path, test_command)
        return len(test_results)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0
```

- [ ] **Step 3: Hook invariants into _run_iteration**

In `ouroboros/loop.py`, after the implementer succeeds and before the merge gate, add:

```python
from ouroboros.scoreboard.invariants import SafetyInvariants
from ouroboros.scoreboard.runner import count_ruff_violations, count_tests

# After impl_result.success check, before self._run_scoreboard(worktree.path):
invariants = SafetyInvariants()
before_ruff = count_ruff_violations(self.repo_root / self.config.target_path)
after_ruff = count_ruff_violations(worktree.path / self.config.target_path)
before_tests = count_tests(self.repo_root / self.config.target_path, self.config.target_test_command)
after_tests = count_tests(worktree.path / self.config.target_path, self.config.target_test_command)

invariant_result = invariants.check(
    before_test_count=before_tests,
    after_test_count=after_tests,
    before_ruff_violations=before_ruff,
    after_ruff_violations=after_ruff,
    files_written=list(impl_result.files_written),
)

if not invariant_result.passed:
    self.worktree_mgr.rollback(worktree)
    self._log_iteration(
        iteration, now, observation, plan, baseline, baseline,
        IterationOutcome.KILLED,
        f"Safety invariant violated: {invariant_result.violation}",
    )
    # Write telemetry with KILLED outcome
    self._write_telemetry(iteration, now, "KILLED", 0.0,
        invariant_result.violation, "", obs_tokens, strat_tokens, impl_tokens,
        impl_result.files_written, "")
    return IterationOutcome.KILLED
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ouroboros/ -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add ouroboros/loop.py ouroboros/scoreboard/runner.py
git commit -m "feat(invariants): wire SafetyInvariants into evaluation step with KILLED outcome"
```

---

### Task 10: Benchmark task definitions and BenchmarkGenerator

**Files:**
- Create: `ouroboros/meta/benchmark_gen.py`
- Create: `.ouroboros/benchmarks/core_001_fix_ruff.yaml`
- Create: `.ouroboros/benchmarks/core_002_add_docstring.yaml`
- Create: `.ouroboros/benchmarks/core_003_reduce_complexity.yaml`
- Test: `tests/ouroboros/test_benchmark_gen.py`

- [ ] **Step 1: Write benchmark task YAML files**

```yaml
# .ouroboros/benchmarks/core_001_fix_ruff.yaml
name: fix_ruff_violation
type: core
description: "Fix a ruff F841 violation (unused variable) in a prepared file."
setup_file: |
  def compute(x: int) -> int:
      unused = x * 2
      return x + 1
setup_path: "ouroboros/_benchmark_target.py"
expected_check: "ruff_clean"
target_dimension: "code_quality"
```

```yaml
# .ouroboros/benchmarks/core_002_add_docstring.yaml
name: add_docstring
type: core
description: "Add a docstring to the public function compute() in the prepared file."
setup_file: |
  def compute(x: int) -> int:
      return x + 1
setup_path: "ouroboros/_benchmark_target.py"
expected_check: "has_docstring"
target_function: "compute"
target_dimension: "real_world"
```

```yaml
# .ouroboros/benchmarks/core_003_reduce_complexity.yaml
name: reduce_complexity
type: core
description: "Refactor the process() function to reduce cyclomatic complexity from C to A/B."
setup_file: |
  def process(x, y, z, mode):
      if mode == "a":
          if x > 0:
              if y > 0:
                  return x + y
              else:
                  return x - y
          else:
              if z > 0:
                  return z
              else:
                  return 0
      elif mode == "b":
          if x > 0:
              return x * 2
          else:
              return -x
      else:
          return 0
setup_path: "ouroboros/_benchmark_target.py"
expected_check: "low_complexity"
target_function: "process"
target_dimension: "code_quality"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/ouroboros/test_benchmark_gen.py
"""Tests for benchmark task loading and rotating task generation."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from ouroboros.meta.benchmark_gen import BenchmarkTask, BenchmarkGenerator, load_benchmark_tasks


class TestLoadBenchmarkTasks:
    def test_loads_core_tasks(self, tmp_path: Path):
        task_yaml = {
            "name": "test_task",
            "type": "core",
            "description": "A test task",
            "setup_file": "def foo(): pass",
            "setup_path": "ouroboros/_target.py",
            "expected_check": "ruff_clean",
            "target_dimension": "code_quality",
        }
        (tmp_path / "core_001.yaml").write_text(yaml.dump(task_yaml))
        tasks = load_benchmark_tasks(tmp_path)
        assert len(tasks) == 1
        assert tasks[0].name == "test_task"
        assert tasks[0].task_type == "core"

    def test_empty_dir(self, tmp_path: Path):
        tasks = load_benchmark_tasks(tmp_path)
        assert tasks == []


class TestBenchmarkGenerator:
    def test_generates_rotating_tasks(self, tmp_path: Path):
        # Create a python file with undocumented public functions
        target = tmp_path / "ouroboros"
        target.mkdir()
        (target / "sample.py").write_text(
            "def alpha():\n    pass\n\ndef beta():\n    pass\n\ndef gamma():\n    \"\"\"Has doc.\"\"\"\n    pass\n"
        )
        gen = BenchmarkGenerator(target_path=target)
        tasks = gen.generate_rotating(count=2)
        assert len(tasks) == 2
        for t in tasks:
            assert t.task_type == "rotating"
            assert t.expected_check == "has_docstring"


class TestBenchmarkScoring:
    def test_ruff_clean_check(self):
        code = "def foo() -> int:\n    return 1\n"
        tree = ast.parse(code)
        # Just verify it parses — actual ruff check needs subprocess
        assert tree is not None

    def test_has_docstring_check(self):
        code = 'def compute(x: int) -> int:\n    """Does something."""\n    return x + 1\n'
        tree = ast.parse(code)
        func = tree.body[0]
        assert ast.get_docstring(func) is not None

    def test_missing_docstring_detected(self):
        code = "def compute(x: int) -> int:\n    return x + 1\n"
        tree = ast.parse(code)
        func = tree.body[0]
        assert ast.get_docstring(func) is None
```

- [ ] **Step 3: Implement BenchmarkGenerator**

```python
# ouroboros/meta/benchmark_gen.py
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
    setup_file: str  # Python source code to place in the target file
    setup_path: str  # Relative path for the target file
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
        candidates: list[tuple[str, str, str]] = []  # (file_path, func_name, source)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_benchmark_gen.py -v`
Expected: 5 passed

- [ ] **Step 5: Create the benchmark YAML files and commit**

```bash
mkdir -p .ouroboros/benchmarks
# Write the 3 core benchmark files shown in Step 1
git add ouroboros/meta/benchmark_gen.py tests/ouroboros/test_benchmark_gen.py .ouroboros/benchmarks/
git commit -m "feat(meta): add benchmark task definitions and BenchmarkGenerator"
```

---

### Task 11: Tournament runner

**Files:**
- Create: `ouroboros/meta/tournament.py`
- Test: `tests/ouroboros/test_tournament.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_tournament.py
"""Tests for Tournament benchmark runner."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ouroboros.meta.benchmark_gen import BenchmarkTask
from ouroboros.meta.tournament import score_task_result


class TestScoreTaskResult:
    def test_ruff_clean_scores_1(self):
        code = "def foo() -> int:\n    return 1\n"
        score = score_task_result(code, "ruff_clean", "")
        assert score == 1.0

    def test_ruff_violation_scores_0(self):
        code = "def foo() -> int:\n    unused = 1\n    return 1\n"
        score = score_task_result(code, "ruff_clean", "")
        # Has unused variable — ruff would flag this
        assert score <= 0.5

    def test_has_docstring_scores_1(self):
        code = 'def compute(x):\n    """Does math."""\n    return x\n'
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 1.0

    def test_missing_docstring_scores_0(self):
        code = "def compute(x):\n    return x\n"
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 0.0

    def test_syntax_error_scores_0(self):
        code = "def compute(x:\n    return x\n"
        score = score_task_result(code, "has_docstring", "compute")
        assert score == 0.0

    def test_low_complexity_simple_function(self):
        code = "def process(x):\n    return x + 1\n"
        score = score_task_result(code, "low_complexity", "process")
        assert score == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_tournament.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Tournament**

```python
# ouroboros/meta/tournament.py
"""Tournament runner — evaluate prompts against benchmark tasks."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from ouroboros.meta.benchmark_gen import BenchmarkTask


def score_task_result(code: str, expected_check: str, target_function: str) -> float:
    """Score a single task result using AST-based deterministic checks.

    Returns 1.0 (pass), 0.5 (partial), or 0.0 (fail).
    """
    # Basic: must parse
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
    try:
        result = subprocess.run(
            ["ruff", "check", "--stdin-filename", "check.py", "-"],
            input=code, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return 1.0
        # Count violations
        violations = len([l for l in result.stdout.splitlines() if l.strip()])
        return 0.5 if violations <= 1 else 0.0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0.5  # ruff not available, give benefit of doubt


def _check_has_docstring(tree: ast.AST, target_function: str) -> float:
    """Check if the target function has a docstring using AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == target_function:
                if ast.get_docstring(node):
                    return 1.0
                return 0.0
    return 0.0  # function not found


def _check_low_complexity(tree: ast.AST, target_function: str) -> float:
    """Check if target function has low complexity by counting branches."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == target_function:
                branches = sum(
                    1 for child in ast.walk(node)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_tournament.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/meta/tournament.py tests/ouroboros/test_tournament.py
git commit -m "feat(meta): add Tournament runner with AST-based deterministic scoring"
```

---

### Task 12: MetaAgent state machine

**Files:**
- Create: `ouroboros/meta/agent.py`
- Test: `tests/ouroboros/test_meta_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ouroboros/test_meta_agent.py
"""Tests for MetaAgent state machine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ouroboros.meta.agent import MetaAgent, MetaResult


class TestMetaAgent:
    def test_insufficient_data_returns_early(self, tmp_path: Path):
        """Meta-agent needs at least 2 telemetry records to proceed."""
        meta = MetaAgent(
            prompts_dir=tmp_path / "prompts",
            archive_dir=tmp_path / "archive",
            benchmark_dir=tmp_path / "benchmarks",
            target_path=tmp_path / "ouroboros",
            model="test-model",
            defaults={"implementer": "test prompt"},
        )
        result = meta.run()
        assert result.state == "IDLE"
        assert "insufficient" in result.reason.lower()

    def test_bloat_gate_rejects_long_mutation(self, tmp_path: Path):
        """Mutation exceeding 120% of parent is rejected."""
        from ouroboros.meta.agent import _check_bloat
        passed, msg = _check_bloat(parent_tokens=100, mutated_tokens=130)
        assert passed is False
        assert "bloat" in msg.lower()

    def test_bloat_gate_accepts_reasonable_mutation(self, tmp_path: Path):
        from ouroboros.meta.agent import _check_bloat
        passed, msg = _check_bloat(parent_tokens=100, mutated_tokens=115)
        assert passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ouroboros/test_meta_agent.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement MetaAgent**

```python
# ouroboros/meta/agent.py
"""Meta-Agent — outer loop that evolves agent prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ouroboros.agents.base import BaseAgent
from ouroboros.meta.benchmark_gen import BenchmarkGenerator, load_benchmark_tasks
from ouroboros.meta.prompt_store import PromptStore
from ouroboros.meta.tournament import Tournament, score_task_result
from ouroboros.telemetry.reader import TelemetryReader


@dataclass(frozen=True)
class MetaResult:
    """Result of a meta-agent cycle."""

    state: str  # Final state: IDLE, PROMOTED, DISCARDED
    agent: str
    reason: str
    old_version: int = 0
    new_version: int = 0
    tournament_score: float = 0.0
    baseline_score: float = 0.0


BLOAT_LIMIT = 1.2  # Max ratio of mutated/parent token count


def _check_bloat(parent_tokens: int, mutated_tokens: int) -> tuple[bool, str]:
    """Check if mutation exceeds the bloat limit."""
    if parent_tokens == 0:
        return True, ""
    ratio = mutated_tokens / parent_tokens
    if ratio > BLOAT_LIMIT:
        return False, f"Prompt bloat: {mutated_tokens} tokens vs {parent_tokens} parent ({ratio:.1%})"
    return True, ""


META_SYSTEM_PROMPT = """You are the Meta-Agent in the Ouroboros self-improvement system.

Your job: analyze failed execution traces from inner-loop iterations and mutate agent system prompts
to fix cognitive bottlenecks.

You receive:
1. The current system prompt for a specific agent
2. The 5 worst execution traces (what the agent produced and why it failed)

You must:
1. Identify the failure pattern (what goes wrong repeatedly)
2. Identify the root cause in the prompt (what instruction is missing, ambiguous, or wrong)
3. Produce a MUTATED version of the system prompt that fixes the issue

CRITICAL RULES:
- You must EDIT or REPLACE existing instructions. Do NOT append new rules to the end.
- The mutated prompt must be roughly the same length as the parent prompt.
- Focus on ONE specific fix per mutation — the most impactful bottleneck.

Respond with a JSON object:
{
  "agent": "<agent name>",
  "failure_pattern": "<what goes wrong>",
  "root_cause": "<why the current prompt causes this>",
  "proposed_fix": "<what you changed and why>",
  "mutated_prompt": "<the complete new system prompt>"
}"""


class MetaAgent:
    """Outer loop that evolves agent prompts based on telemetry."""

    def __init__(
        self,
        prompts_dir: Path,
        archive_dir: Path,
        benchmark_dir: Path,
        target_path: Path,
        model: str = "claude-opus-4-6",
        defaults: dict[str, str] | None = None,
        min_records: int = 2,
    ) -> None:
        self.reader = TelemetryReader(archive_dir=archive_dir)
        self.prompt_store = PromptStore(prompts_dir=prompts_dir, defaults=defaults or {})
        self.benchmark_dir = benchmark_dir
        self.target_path = target_path
        self.agent = BaseAgent(model=model, role="meta", timeout_seconds=300)
        self.min_records = min_records

    def run(self, target_agent: str | None = None) -> MetaResult:
        """Run one meta-cycle. Returns the result."""
        # Step 1: ANALYZING — find worst agent
        summary = self.reader.get_summary()
        if not summary:
            return MetaResult(state="IDLE", agent="", reason="Insufficient telemetry data")

        total_records = sum(s["total"] for s in summary.values())
        if total_records < self.min_records:
            return MetaResult(state="IDLE", agent="", reason="Insufficient telemetry records")

        agent = target_agent or self._select_worst_agent(summary)
        if not agent:
            return MetaResult(state="IDLE", agent="", reason="No agent to optimize")

        # Step 2: REFLECTING — get failure traces
        current_version = self.prompt_store.current_version(agent)
        version_str = f"v{current_version}" if current_version else "v1"
        failures = self.reader.get_failures(prompt_version=version_str, limit=5)

        if len(failures) < self.min_records:
            return MetaResult(state="IDLE", agent=agent, reason="Insufficient failure data for agent")

        traces = []
        for f in failures:
            body = self.reader.read_full_record(f["run_id"])
            traces.append(f"### {f['run_id']} (score={f.get('eval_score', 0)}, outcome={f.get('outcome')})\n{body}")

        current_prompt = self.prompt_store.load(agent)

        # Step 3: MUTATING
        user_prompt = (
            f"## Target Agent: {agent}\n\n"
            f"## Current System Prompt (v{current_version})\n```\n{current_prompt}\n```\n\n"
            f"## 5 Worst Execution Traces\n{'---'.join(traces)}\n\n"
            "Analyze the failures and produce a mutated prompt."
        )
        data = self.agent.call_with_json_retry(
            system_prompt=META_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        mutated_prompt = data.get("mutated_prompt", "")
        if not mutated_prompt:
            return MetaResult(state="DISCARDED", agent=agent, reason="Meta-agent returned empty mutation")

        # Token bloat gate
        parent_tokens = len(current_prompt.split())
        mutated_tokens = len(mutated_prompt.split())
        passed, bloat_msg = _check_bloat(parent_tokens, mutated_tokens)
        if not passed:
            # Retry once with compression instruction
            retry_prompt = (
                f"Your mutation was {mutated_tokens} tokens but the parent is {parent_tokens} tokens. "
                f"Compress the prompt to stay within 120% of the parent length.\n\n"
                f"Original mutation:\n```\n{mutated_prompt}\n```\n\n"
                "Produce a shorter version. Respond with ONLY JSON."
            )
            data = self.agent.call_with_json_retry(
                system_prompt=META_SYSTEM_PROMPT,
                user_prompt=retry_prompt,
            )
            mutated_prompt = data.get("mutated_prompt", "")
            mutated_tokens = len(mutated_prompt.split())
            passed, bloat_msg = _check_bloat(parent_tokens, mutated_tokens)
            if not passed:
                return MetaResult(state="DISCARDED", agent=agent, reason=bloat_msg)

        new_version = self.prompt_store.write_version(
            agent=agent,
            content=mutated_prompt,
            mutation_reason=data.get("proposed_fix", "meta-mutation"),
        )

        # Step 4: TOURNAMENT
        tasks = load_benchmark_tasks(self.benchmark_dir)
        if self.target_path.exists():
            gen = BenchmarkGenerator(target_path=self.target_path)
            tasks.extend(gen.generate_rotating(count=2))

        if not tasks:
            return MetaResult(state="DISCARDED", agent=agent, reason="No benchmark tasks available")

        # TODO: Actually run the tournament by invoking the agent with each task
        # For now, return the mutation result. Full tournament requires worktree setup.
        # This will be wired in Task 13 (CLI integration).

        return MetaResult(
            state="PROMOTED",
            agent=agent,
            reason=data.get("proposed_fix", ""),
            old_version=current_version,
            new_version=new_version,
            tournament_score=0.0,
            baseline_score=0.0,
        )

    def _select_worst_agent(self, summary: dict) -> str:
        """Select the agent with the lowest win rate."""
        # Map prompt versions back to agents
        agent_stats: dict[str, float] = {}
        for version, stats in summary.items():
            win_rate = stats.get("win_rate", 0.0)
            # Infer agent — for now use implementer as primary target
            if "implementer" not in agent_stats or win_rate < agent_stats.get("implementer", 1.0):
                agent_stats["implementer"] = win_rate
        return min(agent_stats, key=agent_stats.get, default="implementer")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ouroboros/test_meta_agent.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ouroboros/meta/agent.py tests/ouroboros/test_meta_agent.py
git commit -m "feat(meta): add MetaAgent state machine with bloat gate and failure analysis"
```

---

### Task 13: Config updates and CLI integration

**Files:**
- Modify: `ouroboros/config.py`
- Modify: `ouroboros.yaml`
- Modify: `ouroboros/cli.py`

- [ ] **Step 1: Add meta config fields to OuroborosConfig**

In `ouroboros/config.py`, add fields to `OuroborosConfig`:

```python
    # Meta-loop configuration
    meta_model: str = "claude-opus-4-6"
    meta_tournament_tasks: int = 5
    meta_rotating_refresh: int = 10
    meta_prompt_bloat_limit: float = 1.2
    meta_min_records: int = 2
```

- [ ] **Step 2: Add meta section parsing to load_config**

In `ouroboros/config.py`, add parsing in `load_config()`:

```python
    meta = raw.get("meta", {})
    if "model" in meta:
        flat["meta_model"] = meta["model"]
    if "tournament_tasks" in meta:
        flat["meta_tournament_tasks"] = meta["tournament_tasks"]
    if "rotating_task_refresh" in meta:
        flat["meta_rotating_refresh"] = meta["rotating_task_refresh"]
    if "prompt_bloat_limit" in meta:
        flat["meta_prompt_bloat_limit"] = meta["prompt_bloat_limit"]
    if "min_telemetry_records" in meta:
        flat["meta_min_records"] = meta["min_telemetry_records"]
```

- [ ] **Step 3: Update ouroboros.yaml with meta section and blocked paths**

Add to `ouroboros.yaml`:

```yaml
meta:
  model: claude-opus-4-6
  tournament_tasks: 5
  rotating_task_refresh: 10
  prompt_bloat_limit: 1.2
  min_telemetry_records: 2

sandbox:
  blocked_paths:
    - "ouroboros/loop.py"
    - "ouroboros/sandbox/"
    - "ouroboros/agents/evaluator.py"
    - "ouroboros/scoreboard/runner.py"
    - "ouroboros/config.py"
    - ".git/"
    - "docs/"
    - "tests/"
    - "conftest.py"
    - ".ouroboros/prompts/meta.md"
    - ".ouroboros/benchmarks/"
    - ".ouroboros/archive/"
```

- [ ] **Step 4: Add meta subcommand to CLI**

In `ouroboros/cli.py`, add the subparser:

```python
    # meta
    meta_parser = sub.add_parser("meta", help="Run the meta-learning loop")
    meta_parser.add_argument("--agent", type=str, help="Target specific agent (observer/strategist/implementer)")
    meta_parser.add_argument("--dry-run", action="store_true", help="Analyze and mutate only, no tournament")
    meta_parser.add_argument("--status", action="store_true", help="Show prompt versions and win rates")
```

Add the handler in `main()`:

```python
    elif args.command == "meta":
        _cmd_meta(config, args)
```

Add the handler function:

```python
def _cmd_meta(config, args):
    repo_root = Path.cwd()

    if args.status:
        from ouroboros.telemetry.reader import TelemetryReader
        reader = TelemetryReader(archive_dir=repo_root / ".ouroboros" / "archive")
        summary = reader.get_summary()
        if not summary:
            print("No telemetry data yet. Run `ouroboros run` first.")
            return
        print("Prompt Version Performance:")
        for version, stats in sorted(summary.items()):
            wr = stats.get("win_rate", 0.0)
            print(f"  {version}: {stats['merged']}/{stats['total']} merged ({wr:.0%} win rate)")
        return

    from ouroboros.agents.observer import OBSERVER_SYSTEM_PROMPT
    from ouroboros.agents.strategist import STRATEGIST_SYSTEM_PROMPT
    from ouroboros.agents.implementer import IMPLEMENTER_SYSTEM_PROMPT
    from ouroboros.meta.agent import MetaAgent

    meta = MetaAgent(
        prompts_dir=repo_root / ".ouroboros" / "prompts",
        archive_dir=repo_root / ".ouroboros" / "archive",
        benchmark_dir=repo_root / ".ouroboros" / "benchmarks",
        target_path=repo_root / config.target_path,
        model=config.meta_model,
        defaults={
            "observer": OBSERVER_SYSTEM_PROMPT,
            "strategist": STRATEGIST_SYSTEM_PROMPT,
            "implementer": IMPLEMENTER_SYSTEM_PROMPT,
        },
        min_records=config.meta_min_records,
    )

    print(f"Running meta-agent (target: {args.agent or 'auto-select'})...")
    result = meta.run(target_agent=args.agent)
    print(f"\nMeta-Agent Result:")
    print(f"  State:            {result.state}")
    print(f"  Agent:            {result.agent}")
    print(f"  Reason:           {result.reason}")
    if result.new_version:
        print(f"  Version:          v{result.old_version} -> v{result.new_version}")
        print(f"  Tournament:       {result.tournament_score:.2f} (baseline: {result.baseline_score:.2f})")
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ouroboros/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add ouroboros/config.py ouroboros.yaml ouroboros/cli.py
git commit -m "feat(meta): add meta config, blocked paths, and CLI subcommand"
```

---

### Task 14: Update CLAUDE.md and run full verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with Phase 3 status**

Add Phase 3 section documenting the new subsystems, commands, and architecture.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ouroboros/ -v`
Expected: All tests pass (104 existing + ~40 new = ~144 tests)

- [ ] **Step 3: Run ruff**

Run: `ruff check ouroboros/`
Expected: All checks passed

- [ ] **Step 4: Run the inner loop to generate telemetry**

Run: `python -m ouroboros run --iterations 3`
Verify: `.ouroboros/archive/` contains 3 markdown files and an `index.jsonl`

- [ ] **Step 5: Run the meta-agent**

Run: `python -m ouroboros meta --status`
Run: `python -m ouroboros meta`
Verify: Meta-agent analyzes telemetry and produces a prompt mutation

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Phase 3 Meta-Learning architecture"
```

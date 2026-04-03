# Phase 3: Meta-Learning Loop — Design Spec

## Goal

Add a second, outer loop to Ouroboros that evolves the agent prompts (Observer, Strategist, Implementer) based on execution telemetry. The inner loop improves the codebase; the outer loop improves the inner loop.

## Architecture

Two nested loops with a shared telemetry archive:

```
Meta-Loop (outer, on-demand or every N iterations):
  Analyze telemetry → Reflect on failures → Mutate prompt → Tournament → Promote/Discard

Inner Loop (existing, runs continuously):
  Observer → Strategist → Implementer → Evaluator
  (loads prompts from .ouroboros/prompts/<agent>/current.md)
```

The Meta-Agent's own prompt is immutable (`meta.md` in `blocked_paths`). The Meta-Agent cannot evolve itself — this is the recursion firewall.

## Tech Stack

Same as existing: Python 3.14, Anthropic SDK, PyYAML. No new dependencies.

---

## Subsystem 1: Immutable Harness

Safety invariants enforced before the merge gate. If any invariant fails, the iteration scores 0.0 and is killed immediately — the merge gate never runs.

### Invariants

| Invariant | Mechanism | Trigger |
|-----------|-----------|---------|
| Test count never decreases | `len(after_tests) >= len(before_tests)` | Checked in `SafetyInvariants.check()` |
| No test file modification | `tests/` in `sandbox_blocked_paths` | Existing blocked path rejection |
| No conftest.py anywhere | Block creation/modification of any `conftest.py` in repo | Blocked path check on all written files |
| No root config creation/modification | Block `*.toml`, `*.ini`, `*.cfg`, `*.yaml` at repo root except `ouroboros.yaml` | Blocked path check on all written files |
| Ruff violations never increase | `after_violations <= before_violations` | Checked in `SafetyInvariants.check()` |

### Implementation

New class `SafetyInvariants` in `ouroboros/scoreboard/invariants.py`.

```python
class SafetyInvariants:
    def check(self, before_test_count: int, after_test_count: int,
              before_ruff_violations: int, after_ruff_violations: int,
              files_written: list[str]) -> InvariantResult:
        """Returns (passed: bool, violation: str)."""
```

The evaluator calls `invariants.check()` before `merge_gate.can_merge()`. A failed invariant produces `IterationOutcome.KILLED` (new outcome type) with the violation reason logged.

### Blocked Paths Updates

Add to `sandbox_blocked_paths` in `ouroboros.yaml`:
- `tests/` (already partially covered, make explicit)
- `conftest.py` (match anywhere in repo)
- `.ouroboros/prompts/meta.md` (Meta-Agent's own prompt)
- `.ouroboros/benchmarks/` (benchmark definitions)
- `.ouroboros/archive/` (telemetry records — append-only, no modification)

### Root Config Allowlist

Only `ouroboros.yaml` is writable at repo root. All other `*.toml`, `*.ini`, `*.cfg`, `*.yaml` files at root level are blocked. Implemented as a check in `SafetyInvariants.check()` against `files_written`.

---

## Subsystem 2: Telemetry Engine

Every inner-loop iteration produces a structured telemetry record capturing the full cognitive trace, per-agent costs, and raw error output.

### TelemetryRecord Schema

```
run_id: str                          # "{ISO_timestamp}_iter{NNN}"
iteration: int
timestamp: str (ISO 8601)

# Prompt versioning
prompt_versions:
  observer: str                      # e.g., "v3"
  strategist: str                    # e.g., "v1"
  implementer: str                   # e.g., "v2"

# Agent outputs (cognitive trace)
observer_output: str                 # Raw JSON response
strategist_output: str               # Raw JSON response
implementer_output: str              # Raw JSON response

# Per-agent token/cost breakdown
tokens_observer: {in: int, out: int, cost_usd: float}
tokens_strategist: {in: int, out: int, cost_usd: float}
tokens_implementer: {in: int, out: int, cost_usd: float}

# Results
files_changed: list[str]
git_diff: str
eval_score: float                    # Composite scoreboard delta
outcome: str                         # MERGED / ROLLED_BACK / ABANDONED / KILLED
failure_reason: str                  # High-level summary
traceback_output: str                # Raw stderr/stdout from eval sandbox

# Totals
cost_usd: float
input_tokens: int
output_tokens: int
```

### Storage Format

One markdown file per iteration in `.ouroboros/archive/`:

```
.ouroboros/archive/
  2026-04-03T14-22-00_iter013.md
  2026-04-03T14-23-10_iter014.md
  ...
```

Each file has YAML frontmatter (all scalar fields for fast filtering) and markdown body (cognitive traces, diff, traceback). Example:

```markdown
---
run_id: "2026-04-03T14-22-00_iter013"
iteration: 13
outcome: MERGED
eval_score: 0.131
prompt_observer: observer_v1
prompt_strategist: strategist_v1
prompt_implementer: implementer_v2
tokens_observer_in: 4200
tokens_observer_out: 380
cost_observer: 0.018
tokens_strategist_in: 8100
tokens_strategist_out: 620
cost_strategist: 0.034
tokens_implementer_in: 8188
tokens_implementer_out: 562
cost_implementer: 0.078
cost_usd: 0.13
tokens_in: 20488
tokens_out: 1562
failure_reason: ""
---

## Observation
{"weakest_dimension": "real_world", "current_score": 0.35, ...}

## Strategy
{"hypothesis": "Adding docstrings to types.py...", ...}

## Implementation
{"files_written": {"ouroboros/types.py": "..."}}

## Diff
<git diff output>

## Traceback
<empty for successful iterations>

## Result
Merged. real_world: 0.3452 -> 0.4762 (+0.131)
```

### TelemetryWriter

New class in `ouroboros/telemetry/writer.py`. Append-only — telemetry is never modified or deleted.

```python
class TelemetryWriter:
    def __init__(self, archive_dir: Path) -> None: ...
    def write(self, record: TelemetryRecord) -> Path: ...
```

Hooks into `_run_iteration()` in `loop.py`. After each iteration completes (any outcome), the writer serializes the full record. Agent outputs are captured by storing the raw response text from each `call_with_json_retry()` call.

### TelemetryReader

New class in `ouroboros/telemetry/reader.py`. Provides filtered access for the Meta-Agent.

```python
class TelemetryReader:
    def __init__(self, archive_dir: Path) -> None: ...

    def get_failures(self, agent: str, prompt_version: str | None = None,
                     limit: int = 5) -> list[TelemetryRecord]:
        """Return lowest-scoring iterations for a given agent, sorted by eval_score ascending."""

    def get_by_prompt_version(self, agent: str, version: str) -> list[TelemetryRecord]:
        """All iterations that used a specific prompt version."""

    def get_summary(self) -> dict:
        """Win rate, abandon rate, average score per prompt version per agent."""
```

The reader parses YAML frontmatter for filtering (cheap — no need to read body). Full body is loaded on-demand when the Meta-Agent requests cognitive traces.

---

## Subsystem 3: Prompt Mutator (Meta-Agent)

The outer loop that evolves agent prompts through failure analysis, targeted mutation, and tournament evaluation.

### Prompt Storage

Prompts move from hardcoded Python constants to versioned files:

```
.ouroboros/prompts/
  observer/
    v1.md            # Original baseline
    v2.md            # First mutation
    current.md       # Symlink -> best performing version
  strategist/
    v1.md
    current.md
  implementer/
    v1.md
    current.md
  meta.md            # Meta-Agent's own prompt (IMMUTABLE, in blocked_paths)
```

Each prompt file has YAML frontmatter:

```yaml
---
version: 2
parent: 1
created: "2026-04-04T03:00:00Z"
mutation_reason: "Implementer kept returning empty JSON — added explicit format enforcement"
tournament_score: 0.82
baseline_score: 0.64
promoted: true
---

<system prompt content>
```

### Prompt Loading

Agent classes (Observer, Strategist, Implementer) load their system prompt from `.ouroboros/prompts/<agent>/current.md` at the start of each iteration. The prompt content is read into memory once per iteration — no mid-execution file reads.

Fallback: if the prompt file doesn't exist (first run, or `.ouroboros/` is clean), the agent uses its hardcoded default constant. On first `ouroboros meta` run, the defaults are written to `v1.md` and `current.md` is symlinked.

### Meta-Agent Workflow

The Meta-Agent runs one cycle per invocation. It targets the worst-performing agent (or a specific agent via `--agent` flag).

#### Step 1: Failure Analysis

Query `TelemetryReader.get_failures(agent=<target>, limit=5)` for the 5 lowest-scoring iterations using the current prompt version. If fewer than 5 records exist, use all available. Minimum 2 records required to proceed (otherwise: "insufficient data, run more inner iterations first").

#### Step 2: Reflection

The Meta-Agent receives the 5 failure traces (cognitive traces + diffs + tracebacks) and produces a structured diagnosis:

```json
{
  "agent": "implementer",
  "current_version": "v2",
  "failure_pattern": "Returns empty JSON when asked to modify >3 files simultaneously",
  "root_cause": "Prompt says 'write complete file content' but doesn't constrain scope",
  "proposed_fix": "Add instruction to implement files one at a time, starting with smallest"
}
```

#### Step 3: Mutation

The Meta-Agent reads the current prompt and the diagnosis, then produces a modified prompt. Critically, the `meta.md` prompt instructs:

> "You must edit or replace existing instructions to address the diagnosed bottleneck. Do not append new rules to the end. The mutated prompt must not exceed 120% of the parent prompt's token count."

**Token bloat gate:** After writing the new version, count tokens via `len(content.split())`. If the mutation exceeds the parent by >20%, reject and retry once with feedback: "Your mutation was {n} tokens, parent was {m}. Compress." If it fails again, discard with reason "prompt bloat".

The new version is written to `.ouroboros/prompts/<agent>/v{N}.md` with `promoted: false`.

#### Step 4: Tournament

The new prompt runs against the micro-benchmark: 5 tasks (3 core + 2 rotating) executed in a fresh git worktree.

**Core tasks (3, permanent):**
1. Fix a specific ruff violation in a prepared file
2. Add a docstring to a specific undocumented function
3. Refactor a high-complexity function to reduce cyclomatic complexity

**Rotating tasks (2, regenerated every K meta-iterations):**
Generated from current codebase state. Examples: "pick 2 random undocumented public functions", "pick 2 files with highest per-function complexity". A `BenchmarkGenerator` class produces these.

**Scoring per task:**
- **1.0** — Correct solution: all invariants pass, code compiles, target metric improved, tests pass
- **0.5** — Partial: code compiles and invariants pass, but target metric did not improve (e.g., docstring added but to wrong function, or ruff violation fixed but a new one introduced)
- **0.0** — Failed: empty output, syntax error, invariant violation, or wrong files modified

**Aggregate score** = mean across all 5 tasks. The baseline prompt's tournament score is cached and only re-computed when rotating tasks change.

Both new and baseline prompts are evaluated in isolated worktrees to prevent cross-contamination.

#### Step 5: Survival

If `new_score > baseline_score`:
1. Write `current_tmp.md` as symlink to new version
2. `os.replace("current_tmp.md", "current.md")` — atomic POSIX swap
3. Update new version's frontmatter: `promoted: true`, `tournament_score`, `baseline_score`
4. Log promotion to telemetry

If `new_score <= baseline_score`:
1. Update version's frontmatter: `promoted: false`, scores
2. Log discard reason

### State Machine

```
IDLE
  | triggered (CLI command or after N inner iterations)
  v
ANALYZING
  | query telemetry for failures
  | select worst-performing agent (lowest win rate)
  | GATE: minimum 2 telemetry records required
  |-- insufficient data --> IDLE (log "need more iterations")
  v
REFLECTING
  | read 5 failure traces (full cognitive traces + tracebacks)
  | produce structured diagnosis JSON
  v
MUTATING
  | read current prompt + diagnosis
  | write new version file
  | TOKEN GATE: reject if >120% of parent token count
  |-- bloat (retry once) --> re-mutate with compression feedback
  |-- bloat (second fail) --> DISCARDING (reason: "prompt bloat")
  v
TOURNAMENT
  | create fresh worktree
  | run 5 benchmark tasks with new prompt
  | run 5 benchmark tasks with baseline (if not cached)
  | score each task: 1.0 / 0.5 / 0.0
  | aggregate = mean of 5
  v
EVALUATING
  |-- new > baseline --> PROMOTING
  |-- new <= baseline --> DISCARDING
  v
PROMOTING                           DISCARDING
  | write current_tmp.md symlink      | mark not promoted
  | os.replace() atomic swap          | log reason + scores
  | mark promoted in frontmatter      --> IDLE
  | log to telemetry
  --> IDLE
```

### Model Selection

The Meta-Agent uses Opus. It must read failure traces, diagnose cognitive patterns across multiple iterations, and write precise, compressed prompt mutations. This is judgment-heavy work.

---

## Configuration

New fields in `ouroboros.yaml`:

```yaml
meta:
  model: claude-opus-4-6
  tournament_tasks: 5              # 3 core + 2 rotating
  rotating_task_refresh: 10        # Regenerate rotating tasks every N meta-cycles
  prompt_bloat_limit: 1.2          # Max ratio of mutated/parent token count
  min_telemetry_records: 2         # Minimum records before meta-agent can run
  benchmark_dir: .ouroboros/benchmarks/
  prompts_dir: .ouroboros/prompts/
  archive_dir: .ouroboros/archive/
```

New `blocked_paths` additions:

```yaml
sandbox:
  blocked_paths:
    # Existing
    - "ouroboros/loop.py"
    - "ouroboros/sandbox/"
    - "ouroboros/agents/evaluator.py"
    - "ouroboros/scoreboard/runner.py"
    - "ouroboros/config.py"
    - ".git/"
    - "docs/"
    # Phase 3 additions
    - "tests/"
    - "conftest.py"
    - ".ouroboros/prompts/meta.md"
    - ".ouroboros/benchmarks/"
    - ".ouroboros/archive/"
```

---

## CLI Integration

New `meta` subcommand:

```bash
python -m ouroboros meta                    # Run one meta-cycle (auto-select worst agent)
python -m ouroboros meta --agent implementer # Target specific agent
python -m ouroboros meta --dry-run          # Steps 1-3 only (analyze, reflect, mutate — no tournament)
python -m ouroboros meta --status           # Show current prompt versions + win rates
```

---

## New Files

| File | Purpose |
|------|---------|
| `ouroboros/scoreboard/invariants.py` | `SafetyInvariants` class — pre-merge-gate safety checks |
| `ouroboros/telemetry/__init__.py` | Package init |
| `ouroboros/telemetry/writer.py` | `TelemetryWriter` — append-only archive writer |
| `ouroboros/telemetry/reader.py` | `TelemetryReader` — filtered query interface |
| `ouroboros/telemetry/types.py` | `TelemetryRecord` dataclass |
| `ouroboros/meta/__init__.py` | Package init |
| `ouroboros/meta/agent.py` | `MetaAgent` — outer loop orchestration + state machine |
| `ouroboros/meta/tournament.py` | `Tournament` — benchmark runner + scoring |
| `ouroboros/meta/prompt_store.py` | `PromptStore` — versioned prompt files + atomic swap |
| `ouroboros/meta/benchmark_gen.py` | `BenchmarkGenerator` — rotating task generation |
| `.ouroboros/benchmarks/core_001_fix_ruff.yaml` | Core benchmark: fix ruff violation |
| `.ouroboros/benchmarks/core_002_add_docstring.yaml` | Core benchmark: add docstring |
| `.ouroboros/benchmarks/core_003_reduce_complexity.yaml` | Core benchmark: refactor complexity |

## Modified Files

| File | Change |
|------|--------|
| `ouroboros/loop.py` | Hook TelemetryWriter, load prompts from PromptStore, capture agent outputs |
| `ouroboros/agents/observer.py` | Load system prompt from file (fallback to hardcoded default) |
| `ouroboros/agents/strategist.py` | Load system prompt from file (fallback to hardcoded default) |
| `ouroboros/agents/implementer.py` | Load system prompt from file (fallback to hardcoded default) |
| `ouroboros/agents/base.py` | Expose last raw response text for telemetry capture |
| `ouroboros/config.py` | Add meta-loop config fields |
| `ouroboros.yaml` | Add `meta:` section and updated `blocked_paths` |
| `ouroboros/cli.py` | Add `meta` subcommand |
| `ouroboros/types.py` | Add `IterationOutcome.KILLED` variant |

---

## Data Flow

```
Inner Loop Iteration:
  1. Load prompts from .ouroboros/prompts/<agent>/current.md
  2. Run OBSERVE → HYPOTHESIZE → IMPLEMENT
  3. SafetyInvariants.check() — kill if violated
  4. MergeGate.can_merge() — merge or rollback
  5. TelemetryWriter.write() — save full record to .ouroboros/archive/

Meta-Agent Cycle:
  1. TelemetryReader.get_failures() — find worst agent
  2. TelemetryReader loads full traces for that agent
  3. Meta-Agent reflects → diagnosis JSON
  4. Meta-Agent reads current prompt + diagnosis → writes mutated prompt
  5. Token bloat gate — reject if >120% parent
  6. Tournament runs new vs baseline on 5 benchmark tasks
  7. If better: atomic symlink swap → next inner loop uses new prompt
```

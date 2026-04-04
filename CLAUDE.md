# Ouroboros — Project Instructions

## What This Is
Self-improving agent engine that runs on and improves its own codebase.
Repo: github.com/rahilsinghi/ouroboros

## Tech Stack
- Python 3.14, Anthropic SDK, PyYAML, mypy, ruff, radon, pytest
- Venv: `.venv/` — always `source .venv/bin/activate` before running
- Config: `ouroboros.yaml` (YAML → flat dataclass in config.py)
- Entry: `python -m ouroboros run --iterations N`

## Architecture
Four-agent loop: OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE
- **Observer** (Sonnet): reads scoreboard + traces, identifies weakest dimension
- **Strategist** (Sonnet): proposes one hypothesis + change plan
- **Implementer** (Sonnet): writes code in git worktree
- **Evaluator** (Sonnet): runs merge gate (before/after scoreboard comparison)

All models currently set to Sonnet for cost ($0.10/iteration).

## 6-Dimension Scoreboard (as of Phase 2)
| Dimension | Scorer | Score | Status |
|-----------|--------|-------|--------|
| code_quality | ruff (60%) + radon (40%) | 1.00 | Fixed: radon flag bug + all ruff violations resolved |
| correctness | pytest pass rate | 1.00 | 104/104 tests pass |
| efficiency | source char count vs baseline | 1.00 | Auto-calibrated (baseline=0 means self-referential) |
| regression | previously-passing still pass | 1.00 | Working |
| tool_selection | routing accuracy | 1.00 | Placeholder |
| real_world | docstring coverage (public callables) | 0.51 | Active — agents improving via autonomous merges |

## Safety-Critical Files (blocked_paths in config)
These files CANNOT be modified by the improvement loop:
- `ouroboros/loop.py` — core orchestration
- `ouroboros/sandbox/` — isolation layer
- `ouroboros/agents/evaluator.py` — merge gate decisions
- `ouroboros/scoreboard/runner.py` — scoring orchestration
- `ouroboros/config.py` — configuration loading
- `.git/`, `docs/`, `tests/`, `conftest.py`
- `.ouroboros/prompts/meta.md`, `.ouroboros/benchmarks/`, `.ouroboros/archive/`

## Current Phase: 3 — META-LEARNING
Phase 3 adds an outer Meta-Agent loop that evolves agent system prompts based on execution telemetry.

### Architecture
**Inner loop** (Phase 2): OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE
**Outer loop** (Phase 3): ANALYZE → REFLECT → MUTATE → TOURNAMENT → EVALUATE → PROMOTE/DISCARD

### Three Subsystems

**1. Immutable Harness** (`ouroboros/scoreboard/invariants.py`)
Pre-merge kill switch. Checks: test count never decreases, ruff violations never increase, no conftest.py creation, no root config creation (except ouroboros.yaml). Violations produce `IterationOutcome.KILLED`.

**2. Telemetry Engine** (`ouroboros/telemetry/`)
- `TelemetryRecord` — frozen dataclass with per-agent token breakdown
- `TelemetryWriter` — serializes to YAML-frontmatter markdown + `index.jsonl`
- `TelemetryReader` — queries failures, filters by prompt version, win rate summaries
- Archive at `.ouroboros/archive/`

**3. Prompt Mutator** (`ouroboros/meta/`)
- `PromptStore` — versioned prompt files (`.ouroboros/prompts/<agent>/v{N}.md`), atomic swap via `os.replace()`
- `BenchmarkGenerator` — 3 core tasks + 2 rotating (undocumented public functions)
- `Tournament` — AST-based deterministic scoring (ruff_clean, has_docstring, low_complexity)
- `MetaAgent` — Opus-powered state machine: analyzes failures, mutates prompts, 120% bloat gate

### Safety Controls
- Blocked paths expanded: `tests/`, `conftest.py`, `.ouroboros/archive/`, `.ouroboros/benchmarks/`, `.ouroboros/prompts/meta.md`
- Prompt bloat gate: mutations capped at 120% of parent token count
- Meta.md instruction: "EDIT or REPLACE, do NOT append"

### Phase 2 Recap
- 4 autonomous merges, real_world 0.35 → 0.51
- Radon flag fix, CostTracker wired, Implementer hardened
- 104 tests passing, 0 ruff violations

## Key Commands
```bash
source .venv/bin/activate
python -m pytest tests/ouroboros/ -v          # Run all tests (125+ tests)
python -m ouroboros run --iterations 5        # Run inner improvement loop
python -m ouroboros meta --status             # View prompt version win rates
python -m ouroboros meta                      # Run meta-agent (prompt evolution)
python -m ouroboros meta --agent implementer  # Target specific agent
python -m ouroboros scoreboard                # View scores (from ledger history)
python -m ouroboros ledger                    # View improvement history
ruff check ouroboros/                         # Lint check (should be 0 violations)
```

## Code Rules (Python-specific overrides)
- Python 3.14, type hints everywhere, `from __future__ import annotations`
- Dataclasses with `frozen=True` for all value objects
- Tests in `tests/ouroboros/` (mirror package structure)
- Run `python -m pytest tests/ouroboros/ -v` before every commit
- Conventional commits: feat/fix/chore/refactor(scope): message

## Git
- Main branch: `main`
- Remote: `origin` → github.com/rahilsinghi/ouroboros
- `.ouroboros/` and `.worktrees/` are gitignored (runtime data)
- Don't push without asking

## Docs
- Design spec: `docs/specs/2026-03-31-ouroboros-design.md`
- Phase 1 plan: `docs/plans/2026-04-02-ouroboros-phase1.md`
- Phase 3 spec: `docs/specs/2026-04-03-phase3-meta-learning-design.md`
- Phase 3 plan: `docs/plans/2026-04-03-phase3-meta-learning-plan.md`

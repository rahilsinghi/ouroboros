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

## 6-Dimension Scoreboard
| Dimension | Scorer | Status |
|-----------|--------|--------|
| code_quality | ruff (60%) + radon (40%) | Working, scores 0.24 |
| correctness | pytest pass rate | Broken — 0.0 (test path misconfigured) |
| efficiency | token count vs baseline | Working, scores 1.0 |
| regression | previously-passing still pass | Working, scores 1.0 (no history) |
| tool_selection | routing accuracy | Placeholder 1.0 |
| real_world | LLM-graded eval | Placeholder 0.5 |

## Safety-Critical Files (blocked_paths in config)
These files CANNOT be modified by the improvement loop:
- `ouroboros/loop.py` — core orchestration
- `ouroboros/sandbox/` — isolation layer
- `ouroboros/agents/evaluator.py` — merge gate decisions
- `ouroboros/scoreboard/runner.py` — scoring orchestration
- `ouroboros/config.py` — configuration loading
- `.git/`, `docs/`

## Current Phase: 1.5 (Fix Feedback Loop + Smarter Agents)
Phase 1 complete (84/84 tests pass, 2 real iterations ran, loop works end-to-end).

### Phase 1.5A — Fix Feedback Loop (NEXT)
The self-improvement loop can't merge anything because:
1. **Correctness = 0.0**: `_run_tests()` runs pytest against wrong path. Tests are in `tests/ouroboros/`, not inside `ouroboros/` dir
2. **Agents target blocked files**: Strategist now gets blocked_paths list but still sometimes proposes blocked changes
3. **JSON parsing fragility**: Truncated LLM responses crash iterations (partial fix: JSON repair in base.py)

### Phase 1.5C — Smarter Agents (AFTER A)
Better strategist prompts, multi-step planning, test-before-merge, chain-of-thought.

## Key Commands
```bash
source .venv/bin/activate
python -m pytest tests/ouroboros/ -v          # Run all tests (84 tests)
python -m ouroboros run --iterations 1        # Run one improvement iteration
python -m ouroboros scoreboard                # View current scores
python -m ouroboros ledger                    # View improvement history
ruff check ouroboros/                         # Lint check
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
- Phase 1.5 spec: (to be created)
- Phase 1.5 plan: (to be created)

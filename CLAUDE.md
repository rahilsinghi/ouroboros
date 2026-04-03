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

## 6-Dimension Scoreboard (baseline as of Phase 1.5)
| Dimension | Scorer | Score | Status |
|-----------|--------|-------|--------|
| code_quality | ruff (60%) + radon (40%) | 0.30 | Working — ruff violations dragging it down |
| correctness | pytest pass rate | 1.00 | Fixed in Phase 1.5A — 102/102 tests pass |
| efficiency | source char count vs baseline | 1.00 | Auto-calibrated (baseline=0 means self-referential) |
| regression | previously-passing still pass | 1.00 | Working (no history = no regressions) |
| tool_selection | routing accuracy | 1.00 | Placeholder |
| real_world | LLM-graded eval | 0.50 | Placeholder |

## Safety-Critical Files (blocked_paths in config)
These files CANNOT be modified by the improvement loop:
- `ouroboros/loop.py` — core orchestration
- `ouroboros/sandbox/` — isolation layer
- `ouroboros/agents/evaluator.py` — merge gate decisions
- `ouroboros/scoreboard/runner.py` — scoring orchestration
- `ouroboros/config.py` — configuration loading
- `.git/`, `docs/`

## Current Phase: 1.5 COMPLETE
Phase 1.5 complete (102/102 tests pass, 5 real iterations ran across 2 runs).

### Phase 1.5A — Fix Feedback Loop (DONE)
- Fixed correctness scoring (was 0.0, now 1.0) — test runner uses configured command
- Blocked files filtered from strategist context
- JSON retry with error feedback on parse failure
- Cost tracking infrastructure (CostTracker + tokens_to_usd)
- Efficiency baseline auto-calibrated

### Phase 1.5C — Smarter Agents (DONE)
- Strategist receives ruff violation details and radon complexity per-function
- Implementer validates syntax (ast.parse) before committing
- Observer has dimension-specific guidance in system prompt
- Ledger summary includes failed hypothesis DO NOT REPEAT list

### Remaining Gap
No successful merges yet. Agents propose valid improvements but:
- Merge gate requires improvement beyond 0.02 noise tolerance
- Sonnet implementer sometimes returns empty JSON (abandoned iterations)
- code_quality is the main improvable dimension (0.30)
- Next step: try with Opus implementer, or lower noise tolerance

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

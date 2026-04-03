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
- `.git/`, `docs/`

## Current Phase: 2 — SELF-IMPROVING
Phase 2 complete. Ouroboros is autonomously improving its own codebase.

### Phase 2 Fixes (2026-04-03)
- **Radon flag bug fixed**: `_complexity_score()` used `-nc` (C-grade-only filter), averaging 6 functions at 15.17 instead of 129 at 3.38. Changed to `-s`. code_quality: 0.30 → 1.00.
- **Cost tracking wired**: BaseAgent accumulates tokens; loop feeds them to CostTracker after each agent call. Costs now reported accurately (~$0.13/iteration).
- **Implementer upgraded to Opus**: Hardened prompt (explicit JSON format), empty response handling, max_tokens 8192→16384.
- **All ruff violations fixed**: 5 violations in cli.py/loop.py → 0. ruff_score: 0.5 → 1.0.
- **real_world dimension activated**: Replaced 0.5 placeholder with docstring coverage scorer (public callables). Score: 0.35 → 0.51 via autonomous merges.
- **Noise tolerance lowered**: 0.02 → 0.005. Enables merging smaller improvements like single-file docstring additions.

### Results
- **4 successful autonomous merges** in first 5 iterations after fixes
- real_world score: 0.35 → 0.51 (+46% improvement)
- 104/104 tests passing after autonomous changes
- Cost: ~$0.64 for 5 iterations ($0.13/iteration avg)

### Remaining Opportunities
- real_world at 0.51 — ~43 more public callables need docstrings
- Implementer still occasionally returns empty JSON (~20% abandon rate)
- tool_selection dimension is still a placeholder

## Key Commands
```bash
source .venv/bin/activate
python -m pytest tests/ouroboros/ -v          # Run all tests (104 tests)
python -m ouroboros run --iterations 5        # Run improvement iterations
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
- Phase 1.5 spec: (to be created)
- Phase 1.5 plan: (to be created)

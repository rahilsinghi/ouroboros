# Ouroboros

A self-improving agent engine that runs on — and improves — its own codebase.

Four LLM agents (Observer, Strategist, Implementer, Evaluator) form a closed loop: they read the codebase, identify weaknesses, write improvements, test them in isolated git worktrees, and merge only when scores improve. An outer Meta-Agent loop evolves the agents' own system prompts based on execution telemetry.

## Architecture

```
Inner Loop (Phase 2):   OBSERVE → HYPOTHESIZE → IMPLEMENT → EVALUATE → MERGE/ROLLBACK
Outer Loop (Phase 3):   ANALYZE failures → MUTATE prompts → TOURNAMENT → PROMOTE/DISCARD
```

### Inner Loop — 4-Agent Improvement Cycle

| Agent | Model | Role |
|-------|-------|------|
| Observer | Sonnet | Reads scoreboard + traces, identifies weakest dimension |
| Strategist | Sonnet | Proposes one hypothesis + change plan |
| Implementer | Opus | Writes code changes in an isolated git worktree |
| Evaluator | Sonnet | Runs merge gate (before/after scoreboard comparison) |

### Outer Loop — Meta-Learning

The Meta-Agent (Opus) analyzes execution telemetry, identifies which agent causes the most failures, mutates that agent's system prompt, and promotes improvements via tournament scoring.

### 6-Dimension Scoreboard

| Dimension | What it measures |
|-----------|-----------------|
| code_quality | ruff lint (60%) + radon complexity (40%) |
| correctness | pytest pass rate |
| efficiency | Source char count vs baseline |
| regression | Previously-passing tests still pass |
| tool_selection | Routing accuracy (placeholder) |
| real_world | Docstring coverage of public callables |

### Safety Controls

- **Blocked paths**: Core loop, sandbox, evaluator, config, tests, and git internals cannot be modified by the improvement loop
- **Safety invariants**: Pre-merge kill switch checks test count, ruff violations, config file creation
- **Prompt bloat gate**: Mutations capped at 120% of parent token count
- **Git worktree isolation**: All changes happen in disposable worktrees; only merged on score improvement

## Results

**Phase 2** — First autonomous merges:
- 4/5 iterations merged, real_world 0.35 → 0.51
- Cost: ~$0.13/iteration

**Phase 3** — Meta-learning loop:
- Meta-agent identified Strategist as worst agent (80% of failures)
- Evolved Strategist prompt improved win rate: 0% → 40%
- real_world: 0.51 → 0.67 via autonomous prompt evolution
- 146 tests passing, 0 ruff violations

## Quick Start

```bash
# Clone and setup
git clone https://github.com/rahilsinghi/ouroboros.git
cd ouroboros
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-..."

# Run the inner improvement loop
python -m ouroboros run --iterations 5

# Check scoreboard
python -m ouroboros scoreboard

# Run the meta-agent (prompt evolution)
python -m ouroboros meta

# View prompt version win rates
python -m ouroboros meta --status

# View improvement history
python -m ouroboros ledger
```

## Tech Stack

- Python 3.14, Anthropic SDK, PyYAML
- Linting: ruff, radon
- Testing: pytest (146+ tests)
- Config: `ouroboros.yaml`

## Project Structure

```
ouroboros/
├── agents/          # Observer, Strategist, Implementer, Evaluator
├── meta/            # MetaAgent, PromptStore, Tournament, BenchmarkGenerator
├── telemetry/       # TelemetryRecord, Writer, Reader
├── scoreboard/      # 6-dimension scoring + SafetyInvariants
├── sandbox/         # Worktree isolation + command execution
├── history/         # Ledger + dashboard
├── loop.py          # Core improvement loop orchestration
├── config.py        # YAML config loading
├── cli.py           # CLI entry point
└── types.py         # Shared types and enums
```

## Docs

- [Design Spec](docs/specs/2026-03-31-ouroboros-design.md)
- [Phase 3 Meta-Learning Spec](docs/specs/2026-04-03-phase3-meta-learning-design.md)
- [Phase 3 Implementation Plan](docs/plans/2026-04-03-phase3-meta-learning-plan.md)

## License

Private repository.

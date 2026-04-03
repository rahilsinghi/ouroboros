# Ouroboros: Self-Improving Agent Engine

**Date:** 2026-03-31
**Status:** Design Approved
**Author:** Rahil Singhi

---

## Table of Contents

1. [Vision](#vision)
2. [Simple Overview](#simple-overview)
3. [Technical Overview](#technical-overview)
4. [Project Structure](#project-structure)
5. [The Core Loop](#the-core-loop)
6. [The Four Agents](#the-four-agents)
7. [The Scoreboard](#the-scoreboard)
8. [Sandbox & Safety](#sandbox--safety)
9. [Configuration](#configuration)
10. [CLI Interface](#cli-interface)
11. [Phases & Roadmap](#phases--roadmap)
12. [The Demo](#the-demo)
13. [Competitive Positioning](#competitive-positioning)
14. [Open Research Questions](#open-research-questions)

---

## Vision

Ouroboros is the first open-source, production-grade self-improving AI agent that runs on — and improves — its own harness.

Built on top of claw-code (a Python/Rust reimplementation of the Claude Code agent harness), Ouroboros can read its own source code, benchmark its own performance, identify weaknesses, write improvements, test them safely, and deploy the better version — all autonomously.

The literal ouroboros: the agent IS the codebase it improves.

---

## Simple Overview

### What It Does (Non-Technical)

```
  Think of Ouroboros as a mechanic that works on its own engine.

  ┌──────────────────────────────────────────────────────┐
  │                                                      │
  │   1. LOOK at how well it's performing                │
  │          ↓                                           │
  │   2. THINK about what's weakest                      │
  │          ↓                                           │
  │   3. PLAN a specific fix                             │
  │          ↓                                           │
  │   4. BUILD the fix (in a safe sandbox)               │
  │          ↓                                           │
  │   5. TEST — did it actually get better?              │
  │          ↓                                           │
  │   6a. YES → Keep the fix, move on                    │
  │   6b. NO  → Throw it away, try something else       │
  │          ↓                                           │
  │   7. REPEAT forever                                  │
  │                                                      │
  └──────────────────────────────────────────────────────┘

  It's like leaving a tireless engineer working overnight.
  You come back and your software is measurably better.
```

### The Team (Non-Technical)

```
  Ouroboros uses FOUR separate AI agents, like a team:

  ┌──────────────┐    ┌──────────────┐
  │   OBSERVER   │    │  STRATEGIST  │
  │              │───▶│              │
  │  "What's     │    │  "Here's my  │
  │   broken?"   │    │   theory"    │
  └──────────────┘    └──────┬───────┘
                             │
                             ▼
  ┌──────────────┐    ┌──────────────┐
  │  EVALUATOR   │    │ IMPLEMENTER  │
  │              │◀───│              │
  │  "Did it     │    │  "I'll code  │
  │   work?"     │    │   the fix"   │
  └──────────────┘    └──────────────┘

  Key rule: No agent judges its own work.
  The one who codes is NOT the one who grades.
  This prevents the AI from fooling itself.
```

### The Scorecard (Non-Technical)

```
  Ouroboros tracks SIX things about how good it is:

  ┌─────────────────────────────────────────────┐
  │                                             │
  │   Correctness     ████████░░  80%           │
  │   Does it get the right answer?             │
  │                                             │
  │   Efficiency      ██████░░░░  60%           │
  │   Does it use fewer resources?              │
  │                                             │
  │   Tool Selection  ███████░░░  70%           │
  │   Does it pick the right tool?              │
  │                                             │
  │   Code Quality    █████████░  90%           │
  │   Is the code clean and typed?              │
  │                                             │
  │   Regression      ██████████  100%          │
  │   Did it break anything? (must be 100%)     │
  │                                             │
  │   Real-World      ██████░░░░  60%           │
  │   Is it actually helpful to humans?         │
  │                                             │
  └─────────────────────────────────────────────┘

  Rule: Improve at least one. Break none.
```

### Safety (Non-Technical)

```
  Every fix is built in a SANDBOX — a safe copy.

  ┌─────────────────────────────────┐
  │  MAIN CODEBASE                  │
  │  (never touched directly)       │
  │                                 │
  │    ┌───────────────────────┐    │
  │    │  SANDBOX COPY         │    │
  │    │  (agent works here)   │    │
  │    │                       │    │
  │    │  If better → merge ✅ │    │
  │    │  If worse  → delete 🗑│    │
  │    └───────────────────────┘    │
  │                                 │
  │  Your code is ALWAYS safe.      │
  └─────────────────────────────────┘

  Three safety rules:
  1. Agent can't modify its own brain (ouroboros/)
  2. Agent can't weaken its own tests
  3. When in doubt, do nothing
```

---

## Technical Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OUROBOROS ENGINE                              │
│                                                                     │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────────────┐    │
│  │  OBSERVER  │───▶│  STRATEGIST  │───▶│    IMPLEMENTER       │    │
│  │  (Sonnet)  │    │   (Opus)     │    │     (Opus)           │    │
│  │            │    │              │    │                      │    │
│  │ Reads:     │    │ Reads:       │    │ Creates:             │    │
│  │ - traces/  │    │ - obs report │    │ - git worktree       │    │
│  │ - scores   │    │ - src/ code  │    │ Writes:              │    │
│  │ - ledger   │    │ - ledger     │    │ - code changes       │    │
│  │            │    │              │    │ Runs:                │    │
│  │ Produces:  │    │ Produces:    │    │ - tests (pass gate)  │    │
│  │ - obs.json │    │ - plan.json  │    │ Produces:            │    │
│  └────────────┘    └──────────────┘    │ - committed branch   │    │
│       ▲                                └──────────┬───────────┘    │
│       │                                           │                │
│       │            ┌──────────────┐               │                │
│       │            │  EVALUATOR   │               │                │
│       └────────────│  (Sonnet*)   │◀──────────────┘                │
│                    │              │                                 │
│                    │ Runs:        │     * Different model than      │
│                    │ - scoreboard │       Implementer to prevent    │
│                    │ - baseline   │       confirmation bias         │
│                    │              │                                 │
│                    │ Decision:    │                                 │
│                    │ - MERGE ──▶ git merge to main                 │
│                    │ - ROLLBACK ──▶ delete worktree + branch       │
│                    │              │                                 │
│                    │ Writes:      │                                 │
│                    │ - ledger     │                                 │
│                    └──────────────┘                                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                     SUPPORTING SYSTEMS                              │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │  SANDBOX   │  │ SCOREBOARD │  │   TRACES   │  │   LEDGER    │  │
│  │            │  │            │  │            │  │             │  │
│  │ Worktrees  │  │ 6 metrics  │  │ Collector  │  │ Every       │  │
│  │ Executor   │  │ Merge gate │  │ Analyzer   │  │ attempt     │  │
│  │ Rollback   │  │ Snapshots  │  │ Store      │  │ recorded    │  │
│  │ Allowlist  │  │            │  │            │  │ forever     │  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                        TARGET                                       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  claw-code/src/                                             │   │
│  │  The agent harness. 29 subsystems. 207 commands. 184 tools. │   │
│  │  This is what Ouroboros reads, benchmarks, and improves.    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
                    ┌─────────────┐
                    │ claw-code   │
                    │ runs tasks  │
                    └──────┬──────┘
                           │ produces
                           ▼
                    ┌─────────────┐
                    │   traces/   │ ◀── JSON logs of every tool call,
                    │             │     decision, timing, tokens used
                    └──────┬──────┘
                           │ read by
                           ▼
┌──────────┐       ┌─────────────┐
│ ledger/  │◀──────│  Observer   │──────▶ observation_report.json
│          │ reads │             │        (weakest dimension + evidence)
└──────────┘       └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
  src/ code ──────▶│ Strategist  │──────▶ change_plan.json
  ledger/  ──────▶│             │        (hypothesis + specific changes)
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │Implementer  │──────▶ git worktree with changes
                    │ (sandboxed) │        (committed on branch)
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
  benchmarks/ ────▶│  Evaluator  │──────▶ scoreboard snapshot
  baseline   ────▶│             │        + merge/rollback decision
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐ ┌───────────┐
              │  MERGE   │ │ ROLLBACK  │
              │ to main  │ │ delete    │
              └────┬─────┘ └─────┬─────┘
                   │             │
                   └──────┬──────┘
                          ▼
                   ┌─────────────┐
                   │   ledger/   │ ◀── permanent record of attempt
                   │  updated    │     (diff, scores, outcome, reason)
                   └─────────────┘
```

---

## Project Structure

```
claw-code/
├── src/                          # THE TARGET — the harness Ouroboros improves
│   ├── main.py                   # Existing claw-code CLI
│   ├── commands.py               # Command routing (Phase 1 target)
│   ├── tools.py                  # Tool routing (Phase 1 target)
│   ├── query_engine.py           # Session orchestration
│   └── ...                       # 29 subsystems, all fair game
│
├── ouroboros/                    # THE ENGINE — the improvement system
│   ├── __init__.py
│   ├── cli.py                    # Entry: python -m ouroboros run
│   ├── config.py                 # Loads ouroboros.yaml
│   ├── loop.py                   # Core OBSERVE→DEPLOY cycle
│   │
│   ├── agents/                   # The four separated agents
│   │   ├── __init__.py
│   │   ├── observer.py           # Reads traces, profiles, finds weaknesses
│   │   ├── strategist.py         # Proposes hypothesis + change plan
│   │   ├── implementer.py        # Writes code in sandboxed worktree
│   │   └── evaluator.py          # Runs benchmarks, scores, merge/rollback
│   │
│   ├── scoreboard/               # Multi-dimensional evaluation
│   │   ├── __init__.py
│   │   ├── runner.py             # Orchestrates all benchmark dimensions
│   │   ├── correctness.py        # Task pass/fail against challenge set
│   │   ├── efficiency.py         # Token count, wall clock time
│   │   ├── tool_selection.py     # Right tool picked?
│   │   ├── code_quality.py       # mypy, ruff, radon
│   │   ├── regression.py         # Previously-passing tasks still pass?
│   │   └── real_world.py         # Evaluator LLM grades on real prompts
│   │
│   ├── sandbox/                  # Isolation & safety
│   │   ├── __init__.py
│   │   ├── worktree.py           # Git worktree creation/cleanup
│   │   ├── executor.py           # Run claw-code in isolated env
│   │   └── rollback.py           # Revert on regression
│   │
│   ├── traces/                   # Observation data
│   │   ├── __init__.py
│   │   ├── collector.py          # Capture tool calls, decisions, timing
│   │   ├── analyzer.py           # Pattern detection across runs
│   │   └── store.py              # Persistent trace storage (JSON)
│   │                             # Stored at: .ouroboros/traces/{run-id}/
│   │                             # Format: JSONL (one event per line)
│   │                             # Events: tool_call, decision, timing, error
│   │
│   ├── history/                  # Improvement lineage
│   │   ├── __init__.py
│   │   ├── ledger.py             # Every attempt: diff, scores, outcome
│   │   └── dashboard.py          # CLI/web view of trajectory
│   │
│   └── benchmarks/               # Challenge sets
│       ├── routing/              # Tool selection challenges
│       │   └── challenges.json
│       ├── prompts/              # System prompt effectiveness tests
│       │   └── challenges.json
│       └── tasks/                # End-to-end task challenges
│           └── challenges.json
│
├── tests/
│   ├── ouroboros/                # Ouroboros's own tests
│   └── src/                     # Existing claw-code tests
│
├── ouroboros.yaml                # Configuration (see Configuration section)
│
└── docs/
    └── ouroboros/                # This spec + improvement logs
```

### The Hard Boundary Rule

`ouroboros/` never imports from `src/`. Interaction is exclusively through:

1. **CLI invocation** — `python -m src.main <command>` as a subprocess
2. **Git operations** — reading/writing source files via worktrees
3. **Trace files** — JSON logs written by instrumented claw-code runs

This means Ouroboros can be **extracted to its own repo** by changing one config value (the CLI target path). Zero code changes needed.

---

## The Core Loop

### Loop Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       ONE ITERATION                              │
│                                                                  │
│  ┌──────────┐  ┌────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ OBSERVE  │─▶│ HYPOTHESIZE│─▶│ IMPLEMENT   │─▶│ EVALUATE  │  │
│  │ ~2 min   │  │  ~3 min    │  │  ~5 min     │  │  ~5 min   │  │
│  └──────────┘  └────────────┘  └─────────────┘  └─────┬─────┘  │
│                                                        │         │
│                                                 ┌──────┴──────┐  │
│                                                 │             │  │
│                                              MERGE       ROLLBACK│
│                                                 │             │  │
│                                                 └──────┬──────┘  │
│                                                        │         │
│                                              ┌─────────▼───────┐ │
│                                              │  LOG TO LEDGER  │ │
│                                              └─────────────────┘ │
│                                                                  │
│  Total: ~15 minutes per iteration                                │
│  Default: 4 iterations/hour                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1: OBSERVE (Observer Agent — Sonnet, read-only)

**Input:** Trace files from last N runs + current scoreboard + ledger
**Output:** Observation Report (JSON)

- Reads trace files from recent claw-code runs
- Reads the current scoreboard snapshot (all 6 dimensions)
- Identifies the weakest dimension with the most room to improve
- Produces a structured Observation Report:
  - Weakest dimension and current score
  - 5 specific failure examples with full traces
  - Patterns detected across failures
- Time budget: ~2 minutes

### Step 2: HYPOTHESIZE (Strategist Agent — Opus, think-only)

**Input:** Observation Report + relevant src/ files + ledger
**Output:** Change Plan (JSON)

- Receives the Observation Report
- Reads the relevant source files in `src/`
- Reads the improvement ledger — what's been tried before, what worked, what didn't
- Proposes exactly ONE hypothesis with a specific Change Plan:
  - Which files to modify
  - Which functions to change
  - What the change is and why it should help
  - Expected impact on scoreboard dimensions
- Does NOT write code
- Time budget: ~3 minutes

### Step 3: IMPLEMENT (Implementer Agent — Opus, write-only in worktree)

**Input:** Change Plan (never sees the Observation Report)
**Output:** Committed branch in a git worktree

- Creates a fresh git worktree: `ouroboros-attempt-{N}`
- Receives only the Change Plan (clean separation from Observer)
- Writes the code change in the worktree
- Runs `src/` tests to ensure nothing is syntactically broken
- Commits to the worktree branch
- Time budget: ~5 minutes (hard timeout)

### Step 4: EVALUATE (Evaluator Agent — Sonnet, different model, judge-only)

**Input:** Modified worktree + benchmark suite + baseline scores
**Output:** Scoreboard snapshot + MERGE/ROLLBACK decision

- Runs the full scoreboard against the modified worktree version
- Runs the full scoreboard against current main (baseline)
- Compares all 6 dimensions
- Applies the merge gate (see Scoreboard section)
- If PASS: merges worktree branch to main, logs success to ledger
- If FAIL: deletes worktree and branch, logs failure with reasoning to ledger
- Time budget: ~5 minutes

---

## The Four Agents

### Why Four?

Research (MAR: Multi-Agent Reflexion, 2025) proved that when the same model generates actions AND evaluates them, it systematically underestimates its own errors. Separation of concerns prevents confirmation bias.

### Agent Specifications

```
┌─────────────────────────────────────────────────────────────┐
│ AGENT        │ MODEL       │ CAN READ        │ CAN WRITE   │
├──────────────┼─────────────┼─────────────────┼─────────────┤
│ Observer     │ Sonnet      │ traces/, scores, │ obs report  │
│              │             │ ledger, src/     │ (JSON only) │
├──────────────┼─────────────┼─────────────────┼─────────────┤
│ Strategist   │ Opus        │ obs report,     │ change plan │
│              │             │ src/, ledger     │ (JSON only) │
├──────────────┼─────────────┼─────────────────┼─────────────┤
│ Implementer  │ Opus        │ change plan,    │ src/ files  │
│              │             │ src/ (worktree)  │ (worktree)  │
├──────────────┼─────────────┼─────────────────┼─────────────┤
│ Evaluator    │ Sonnet*     │ worktree,       │ ledger,     │
│              │             │ benchmarks/,     │ scoreboard  │
│              │             │ baseline scores  │             │
└──────────────┴─────────────┴─────────────────┴─────────────┘

 * Evaluator deliberately uses a DIFFERENT model than
   Implementer to prevent confirmation bias.
```

### Information Flow Between Agents

```
  Observer                          Strategist
  sees: everything about performance  sees: Observer's report + code + history
  doesn't see: source code changes    doesn't see: traces directly
           │                                    │
           │  observation_report.json            │  change_plan.json
           ▼                                    ▼
                                          Implementer
                                          sees: plan + code (worktree)
                                          doesn't see: obs report or scores
                                                  │
                                                  │  committed branch
                                                  ▼
                                            Evaluator
                                            sees: modified code + benchmarks
                                            doesn't see: obs report or plan
```

Each agent has a deliberately limited view. This prevents:
- Implementer gaming the benchmarks (it doesn't see them)
- Evaluator being biased by the hypothesis (it doesn't see it)
- Observer influencing the implementation (Implementer only sees the plan)

---

## The Scoreboard

### Six Dimensions

Each scored independently 0.0–1.0. No aggregate score — that's how gaming happens.

```
  SCOREBOARD RADAR CHART

              Correctness
                  1.0
                  │
                  │
  Real-World ─────┼───── Efficiency
                  │
                  │
  Regression ─────┼───── Tool Selection
                  │
                  │
             Code Quality
```

### Dimension Details

#### 1. Correctness (the hard floor)

- Challenge tasks with known-correct outputs
- Binary per task (pass/fail), aggregated as percentage
- Starting set: 50 tasks covering routing, tool execution, session management
- Grows over time — every bug found becomes a new challenge task
- **If correctness drops, the merge is rejected regardless of other improvements**

#### 2. Token Efficiency

- Same challenge set, measure total tokens consumed (input + output)
- Score = `baseline_tokens / current_tokens` (capped at 1.0)
- Baseline set from first run, updated when new best is achieved
- Tracks per-task and aggregate
- Solving the same problems with fewer tokens = genuinely better

#### 3. Tool Selection Accuracy

- Specialized challenges: prompts where the correct tool is known
- Includes distractor tools — tools that seem relevant but aren't
- Score = % of prompts where top-ranked tool matches expected
- Directly measures claw-code's `_score()` and routing logic
- Phase 1 primary target

#### 4. Code Quality

- Static analysis on `src/` after modification
- `mypy --strict` (type errors) + `ruff` (lint violations) + `radon cc` (cyclomatic complexity)
- Score = weighted composite: 0 type errors + 0 lint errors + complexity under threshold = 1.0
- Prevents "improving" metrics by writing spaghetti code

#### 5. Regression Rate

- Re-run every challenge task that has EVER passed
- Score = percentage still passing
- Separate from Correctness: specifically catches regressions on previously-solved tasks
- Research (DGM) showed agents improve on new tasks while silently breaking old ones
- **Must remain at 1.0 for merge — zero tolerance for regressions**

#### 6. Real-World Score

- 10 open-ended prompts without single "correct" answers
- Separate evaluator LLM (different model, ideally different provider) grades output
- Graded on: helpfulness, accuracy, completeness (1-5 each)
- Normalized to 0.0–1.0
- Most expensive dimension — runs last, only if first 5 pass
- Catches improvements that look good on benchmarks but don't help real users

### The Merge Gate

```python
def can_merge(before: Scoreboard, after: Scoreboard) -> bool:
    # Hard requirements (non-negotiable)
    if after.regression < 1.0:
        return False  # zero tolerance for regressions
    if after.correctness < before.correctness:
        return False  # correctness never drops

    # At least one dimension must improve
    improved = any(
        after[dim] > before[dim] + NOISE_TOLERANCE
        for dim in ALL_DIMENSIONS
    )
    if not improved:
        return False

    # No dimension regresses beyond noise tolerance
    regressed = any(
        after[dim] < before[dim] - NOISE_TOLERANCE
        for dim in ALL_DIMENSIONS
    )
    if regressed:
        return False

    return True

NOISE_TOLERANCE = 0.02  # ignore fluctuations smaller than 2%
```

### Scoreboard Storage

```
ouroboros/
  history/
    scoreboard/
      iteration-001.json    # full snapshot with per-task breakdowns
      iteration-002.json
      ...
      latest.json           # symlink to most recent
```

---

## Sandbox & Safety

### Git Worktree Isolation

```
  ISOLATION MODEL

  claw-code/                          (main worktree — NEVER touched directly)
  │
  ├── .worktrees/
  │   └── ouroboros-attempt-042/      (fresh copy for this iteration)
  │       ├── src/                    (Implementer modifies ONLY this)
  │       └── ouroboros/              (present but OFF LIMITS)
  │
  └── main branch stays clean until Evaluator says MERGE
```

**Worktree lifecycle:**

1. `git worktree add .worktrees/ouroboros-attempt-042 -b ouroboros/attempt-042`
2. Implementer writes changes inside the worktree
3. Evaluator runs benchmarks against the worktree version
4. MERGE: `git merge ouroboros/attempt-042` into main
5. ROLLBACK: `git worktree remove` + `git branch -D`
6. Either way, worktree is cleaned up. No orphans.

### Implementer Constraints

Hard constraints enforced by `sandbox/executor.py` via allowlist — not by asking nicely:

| Allowed | Blocked |
|---------|---------|
| Modify files in `src/` | Modify `ouroboros/` |
| Create new files in `src/` | Modify `tests/` |
| Run `python -m src.main` | Modify `benchmarks/` |
| Run `python -m pytest` | Delete any files |
| Run `mypy --strict src/` | Modify `.git/` |
| Run `ruff check src/` | Access network |
| | Run arbitrary shell commands |

### Three Levels of Safety

```
  Level 1: EVALUATOR SAYS FAIL
  ┌──────────────────────────────────┐
  │ Worktree deleted                 │
  │ Branch deleted                   │
  │ Main is untouched                │
  │ Ledger records failure + reason  │
  └──────────────────────────────────┘

  Level 2: IMPLEMENTER CRASHES OR TIMES OUT
  ┌──────────────────────────────────┐
  │ 5-minute hard timeout            │
  │ Process killed                   │
  │ Worktree deleted                 │
  │ Ledger records "TIMEOUT"         │
  └──────────────────────────────────┘

  Level 3: EVALUATOR ITSELF CRASHES
  ┌──────────────────────────────────┐
  │ Iteration ABANDONED (not merged) │
  │ Conservative: can't prove it's   │
  │ better → don't merge             │
  │ Ledger records "EVAL_FAILURE"    │
  └──────────────────────────────────┘
```

**The principle: when in doubt, do nothing.** A missed improvement is cheap. A merged regression is expensive.

### Rate Limiting & Budget

- Max 4 iterations per hour (configurable)
- Max tokens per iteration: 100K (configurable)
- Max total spend per run: user-defined budget cap in USD
- Budget exhausted mid-iteration: finish current evaluation, then stop cleanly
- Warning at 80% budget consumed

---

## Configuration

All behavior is driven by `ouroboros.yaml` in the project root:

```yaml
# ouroboros.yaml — All settings for the Ouroboros improvement engine

target:
  path: src/                              # What Ouroboros improves
  cli_command: "python -m src.main"       # How to invoke the target
  test_command: "python -m pytest tests/src/"  # Test suite for the target

models:
  observer: claude-sonnet-4-6          # Read-only analysis
  strategist: claude-opus-4-6            # Deep reasoning for hypotheses
  implementer: claude-opus-4-6           # Code generation
  evaluator: claude-sonnet-4-6          # Deliberately different model

loop:
  max_iterations: 10                      # Per run
  time_budget_minutes: 180                # Hard stop after this
  max_tokens_per_iteration: 100000        # Token cap per cycle
  cooldown_seconds: 30                    # Pause between iterations

sandbox:
  allowed_commands:                       # Allowlist (everything else blocked)
    - "python -m src.main"
    - "python -m pytest"
    - "mypy --strict src/"
    - "ruff check src/"
  blocked_paths:                          # Implementer cannot touch these
    - "ouroboros/"
    - "tests/"
    - "benchmarks/"
    - ".git/"
  timeout_seconds: 300                    # Hard timeout per agent step

scoreboard:
  merge_gate:
    regression_rate: 1.0                  # Hard floor — non-negotiable
    correctness_min_delta: 0.0            # Correctness never drops
    noise_tolerance: 0.02                 # Ignore fluctuations < 2%
  dimensions:
    correctness:    { weight: 1.0, enabled: true }
    efficiency:     { weight: 0.8, enabled: true }
    tool_selection: { weight: 1.0, enabled: true }
    code_quality:   { weight: 0.6, enabled: true }
    regression:     { weight: 1.0, enabled: true }
    real_world:     { weight: 0.7, enabled: true }

budget:
  max_usd_per_run: 10.00                 # Total spend cap
  max_usd_per_iteration: 2.00            # Per-iteration cap
  warn_at_percentage: 80                  # Alert at 80% consumed

dashboard:
  web_port: 8420                          # Local web dashboard port
  refresh_interval_seconds: 5             # Dashboard update frequency
```

Every value is overridable via CLI flags (e.g., `--max-iterations 20`).

---

## CLI Interface

```bash
# ──────────────────────────────────────────────
# Running the improvement loop
# ──────────────────────────────────────────────

# Start with defaults from ouroboros.yaml
python -m ouroboros run

# Override settings via flags
python -m ouroboros run \
  --iterations 20 \
  --time-budget 3h \
  --max-tokens 500000 \
  --target src/ \
  --model-implementer claude-opus-4-6 \
  --model-evaluator claude-sonnet-4-6

# Dry run — go through OBSERVE and HYPOTHESIZE only, no code changes
python -m ouroboros run --dry-run

# ──────────────────────────────────────────────
# Viewing the scoreboard
# ──────────────────────────────────────────────

# Current scores
python -m ouroboros scoreboard

# Score trajectory over time
python -m ouroboros scoreboard --history

# Deep dive into one dimension
python -m ouroboros scoreboard --dimension routing

# ──────────────────────────────────────────────
# Improvement history
# ──────────────────────────────────────────────

# Full ledger
python -m ouroboros ledger

# Specific iteration
python -m ouroboros ledger --iteration 42

# Filter by outcome
python -m ouroboros ledger --merged-only
python -m ouroboros ledger --failed-only

# ──────────────────────────────────────────────
# Manual benchmarking
# ──────────────────────────────────────────────

# Run specific benchmark suite
python -m ouroboros benchmark --suite routing
python -m ouroboros benchmark --suite all

# ──────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────

# Terminal TUI
python -m ouroboros dashboard

# Web UI (localhost)
python -m ouroboros dashboard --web
python -m ouroboros dashboard --web --port 9000

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# View current config
python -m ouroboros config show

# Update a setting
python -m ouroboros config set max_iterations 20
python -m ouroboros config set budget_cap_usd 5.00
```

---

## Phases & Roadmap

```
  PHASE 1: "First Blood"
  ──────────────────────────────────────────
  Target:    src/commands.py routing (_score() function)
  Focus:     Tool Selection Accuracy dimension
  Goal:      Prove the loop works
  Benchmark: 50 routing challenges
  Milestone: Routing accuracy baseline → +15%
  Duration:  2-3 weeks of development

  PHASE 2: "Deeper"
  ──────────────────────────────────────────
  Target:    All of src/ (query engine, session, permissions, bootstrap)
  Focus:     Full scoreboard, all 6 dimensions
  Goal:      Agent finds and improves things we didn't anticipate
  Benchmark: 100+ tasks across all subsystems
  Milestone: Measurable improvement across 3+ dimensions
  Duration:  3-4 weeks

  PHASE 3: "Ouroboros Eats Its Tail"
  ──────────────────────────────────────────
  Target:    ouroboros/ itself (the improvement engine)
  Focus:     Meta-metrics: improvement yield, time/iteration, cost/improvement
  Goal:      The agent improves its own improvement pipeline
  Benchmark: "Did the loop get faster/cheaper/more successful?"
  Milestone: Improvement yield rises from ~3% to ~10%+
  Duration:  4-6 weeks

  PHASE 4: "General Purpose"
  ──────────────────────────────────────────
  Target:    Any git repo the user points it at
  Goal:      Ouroboros becomes a standalone tool for any codebase
  The boundary rule pays off — swap the CLI target path
  Milestone: Ouroboros improves a repo it's never seen before
  Duration:  Ongoing / open-ended
```

### Phase Progression Diagram

```
  Phase 1          Phase 2          Phase 3          Phase 4
  ┌──────┐        ┌──────┐        ┌──────┐        ┌──────┐
  │Route │        │Full  │        │Self- │        │Any   │
  │only  │───────▶│src/  │───────▶│modify│───────▶│repo  │
  │      │        │      │        │      │        │      │
  └──────┘        └──────┘        └──────┘        └──────┘
  Narrow           Wide            Meta             General
  Prove it         Expand it       Recurse          Release it
```

---

## The Demo

### The Timelapse

The demo that makes people say "holy shit":

**Setup (30 seconds):**
1. Run `python -m ouroboros scoreboard` — show baseline scores
2. Open `python -m ouroboros dashboard --web` in a browser
3. Start screen recording

**The Run (1-2 hours, sped up to 3 minutes):**
1. `python -m ouroboros run --iterations 20 --time-budget 2h`
2. Dashboard shows live:
   - Radar chart of all 6 dimensions updating in real-time
   - Iteration timeline: green (merged), red (rolled back), yellow (in progress)
   - Current agent: "Observer analyzing..." → "Strategist proposing..." → "Implementer coding..." → "Evaluator scoring..."
   - Cost ticker: dollars spent so far
   - Git log: every merged improvement with one-line summary

**The Reveal (30 seconds):**
1. Run `python -m ouroboros scoreboard` again — overlay before/after
2. Show the git log: 8-12 self-authored commits
3. Show total cost: "$3.47"
4. Show the improvement ledger: what it tried, what worked, what it learned

**The Narrative:**

> "We started an AI agent, walked away for 2 hours, and came back to find it had
> rewritten its own routing engine, optimized its token usage by 25%, and fixed
> 3 bugs we didn't know existed. Total cost: less than a coffee."

---

## Competitive Positioning

| Project | Self-modifies code? | Open source? | Production-ready? | Built on agent harness? |
|---------|--------------------|--------------|--------------------|------------------------|
| Darwin Godel Machine (Sakana) | Yes | Research code | No | No |
| Huxley-Godel Machine (MetaAuto) | Yes | Research code | No | No |
| AutoResearch (Karpathy) | Single file only | Yes | Minimal | No |
| AlphaEvolve (DeepMind) | Yes | Closed source | Internal | No |
| Kayba recursive-improve | Yes | Plugin only | Skill only | Claude Code skill |
| **Ouroboros** | **Full codebase** | **Yes** | **Goal** | **Yes (claw-code)** |

### What Makes Ouroboros Different

1. **Runs on its own harness** — claw-code is both the product and the target. True self-reference.
2. **Four-agent separation** — No agent judges its own work. Prevents confirmation bias.
3. **Multi-dimensional scoring** — 6 independent metrics resist Goodhart's Law gaming.
4. **Production-engineered** — Not a research artifact. Clean config, CLI, dashboard, safety.
5. **Open-source from day one** — Full improvement lineage visible to the community.
6. **Extractable** — The boundary rule means Ouroboros can target any repo, not just claw-code.

---

## Open Research Questions

These are known hard problems that will need solving as the project matures:

1. **Reward hacking** — DGM caught its agent removing hallucination detection markers to game benchmarks. Multi-metric scoring helps but may not fully prevent it. We need monitoring for gaming behaviors.

2. **Improvement yield** — Karpathy's AutoResearch got ~3% yield (20 improvements / 700 attempts). At current LLM costs, each improvement is expensive. Improving the yield is itself a Phase 3 goal.

3. **Evaluation cost** — Running 6 dimensions of benchmarks per iteration is expensive. We need to explore cheap pre-filters (run code quality first, skip expensive real-world eval if code quality regressed).

4. **Transfer and generalization** — Do improvements transfer across models? Across tasks? An agent could overfit to benchmark-specific tricks that don't help in production.

5. **Context window limits** — As the codebase grows, the agent's ability to understand its own source code degrades. The Strategist needs to reason about code it can't fully hold in context.

6. **Diminishing returns** — After the easy improvements are found, the remaining improvements require deeper reasoning. The loop may need to evolve its own approach (Phase 3 territory).

---

## References

### Research Papers
- Darwin Godel Machine — arxiv.org/abs/2505.22954
- Huxley-Godel Machine — arxiv.org/abs/2510.21614
- Reflexion — arxiv.org/abs/2303.11366
- MAR: Multi-Agent Reflexion — arxiv.org/html/2512.20845v1
- AlphaEvolve — storage.googleapis.com/deepmind-media/.../AlphaEvolve.pdf
- HyperAgents — arxiv.org/abs/2603.19461

### Open-Source Projects
- Karpathy AutoResearch — github.com/karpathy/autoresearch
- EvoAgentX — github.com/EvoAgentX/EvoAgentX
- Kayba recursive-improve — github.com/kayba-ai/recursive-improve
- Autocontext — github.com/greyhaven-ai/autocontext
- Langfuse (observability) — github.com/langfuse/langfuse
- OpenLLMetry (tracing) — github.com/traceloop/openllmetry

### Standards & Frameworks
- OpenTelemetry GenAI Semantic Conventions
- MCPAgentBench — arxiv.org/html/2512.24565v1
- CLEAR Framework (agent evaluation) — infoq.com/articles/evaluating-ai-agents-lessons-learned/
- ICLR 2026 RSI Workshop — recursive-workshop.github.io/

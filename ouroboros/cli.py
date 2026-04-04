"""CLI entry point for Ouroboros."""

from __future__ import annotations

import argparse
from pathlib import Path

from ouroboros.config import load_config


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

    # meta
    meta_parser = sub.add_parser("meta", help="Run the meta-learning loop")
    meta_parser.add_argument("--agent", type=str, help="Target specific agent (observer/strategist/implementer)")
    meta_parser.add_argument("--dry-run", action="store_true", help="Analyze and mutate only, no tournament")
    meta_parser.add_argument("--status", action="store_true", help="Show prompt versions and win rates")

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
    elif args.command == "meta":
        _cmd_meta(config, args)
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
    print("\nLoop complete:")
    print(f"  Iterations run:       {result.iterations_run}")
    print(f"  Merged:               {result.iterations_merged}")
    print(f"  Rolled back:          {result.iterations_rolled_back}")
    print(f"  Duration:             {result.total_duration_seconds:.1f}s")
    print(f"  Stop reason:          {result.stop_reason}")
    print(f"  Cost:                 ${result.total_cost_usd:.4f}")
    print(f"  Tokens:               {result.total_input_tokens:,} in / {result.total_output_tokens:,} out")


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
    print("\nMeta-Agent Result:")
    print(f"  State:            {result.state}")
    print(f"  Agent:            {result.agent}")
    print(f"  Reason:           {result.reason}")
    if result.new_version:
        print(f"  Version:          v{result.old_version} -> v{result.new_version}")
        print(f"  Tournament:       {result.tournament_score:.2f} (baseline: {result.baseline_score:.2f})")


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

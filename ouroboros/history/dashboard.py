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

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
        if after_test_count < before_test_count:
            return InvariantResult(
                passed=False,
                violation=(
                    f"Test count decreased: {before_test_count} -> {after_test_count}. "
                    "Deleting tests is not allowed."
                ),
            )

        if after_ruff_violations > before_ruff_violations:
            return InvariantResult(
                passed=False,
                violation=(
                    f"Ruff violations increased: {before_ruff_violations} -> "
                    f"{after_ruff_violations}. New lint violations are not allowed."
                ),
            )

        for path in files_written:
            if PurePosixPath(path).name == "conftest.py":
                return InvariantResult(
                    passed=False,
                    violation=f"conftest.py modification blocked: {path}",
                )

        for path in files_written:
            p = PurePosixPath(path)
            if p.parent == PurePosixPath(".") and p.suffix in _ROOT_CONFIG_EXTENSIONS:
                if p.name not in self.allowed_root_configs:
                    return InvariantResult(
                        passed=False,
                        violation=f"Root config file blocked: {path}",
                    )

        return InvariantResult(passed=True, violation="")

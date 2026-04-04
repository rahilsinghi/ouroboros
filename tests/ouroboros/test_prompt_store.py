"""Tests for PromptStore — versioned prompt files with atomic swap."""
from __future__ import annotations

from pathlib import Path

import pytest

from ouroboros.meta.prompt_store import PromptStore


class TestPromptStore:
    def test_initialize_from_defaults(self, tmp_path: Path):
        defaults = {"observer": "You are the observer.", "implementer": "You are the implementer."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()

        assert (tmp_path / "observer" / "v1.md").exists()
        assert (tmp_path / "observer" / "current.md").exists()
        content = store.load("observer")
        assert "You are the observer" in content

    def test_load_returns_current(self, tmp_path: Path):
        defaults = {"implementer": "Default prompt."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.load("implementer") == "Default prompt."

    def test_load_fallback_when_no_files(self, tmp_path: Path):
        defaults = {"observer": "Fallback prompt."}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        assert store.load("observer") == "Fallback prompt."

    def test_write_new_version(self, tmp_path: Path):
        defaults = {"implementer": "v1 content"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()

        version = store.write_version(
            agent="implementer",
            content="v2 content",
            mutation_reason="test mutation",
        )
        assert version == 2
        assert (tmp_path / "implementer" / "v2.md").exists()
        v2_content = (tmp_path / "implementer" / "v2.md").read_text()
        assert "v2 content" in v2_content
        assert "test mutation" in v2_content

    def test_promote_updates_current(self, tmp_path: Path):
        defaults = {"implementer": "v1 content"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        store.write_version("implementer", "v2 content", "test")
        store.promote("implementer", 2, tournament_score=0.9, baseline_score=0.7)

        assert store.load("implementer") == "v2 content"

    def test_current_version(self, tmp_path: Path):
        defaults = {"implementer": "v1"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.current_version("implementer") == 1

    def test_token_count(self, tmp_path: Path):
        defaults = {"implementer": "one two three four five"}
        store = PromptStore(prompts_dir=tmp_path, defaults=defaults)
        store.initialize()
        assert store.token_count("implementer", 1) == 5

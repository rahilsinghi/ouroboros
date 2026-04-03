"""Tests for BaseAgent JSON parsing and retry logic."""
import json
from unittest.mock import patch

import pytest

from ouroboros.agents.base import AgentResponse, BaseAgent


class TestParseJson:
    def setup_method(self):
        self.agent = BaseAgent(model="test", role="test", timeout_seconds=10)

    def test_parses_clean_json(self):
        result = self.agent.parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_fenced_json(self):
        result = self.agent.parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_repairs_truncated_brackets(self):
        result = self.agent.parse_json('{"key": "value"')
        assert result == {"key": "value"}


class TestCallWithJsonRetry:
    def setup_method(self):
        self.agent = BaseAgent(model="test", role="test", timeout_seconds=10)

    @patch.object(BaseAgent, "call")
    def test_succeeds_on_first_try(self, mock_call):
        mock_call.return_value = AgentResponse(
            text='{"result": "ok"}', input_tokens=10, output_tokens=5
        )
        result = self.agent.call_with_json_retry(
            system_prompt="sys", user_prompt="user"
        )
        assert result == {"result": "ok"}
        assert mock_call.call_count == 1

    @patch.object(BaseAgent, "call")
    def test_retries_on_bad_json(self, mock_call):
        mock_call.side_effect = [
            AgentResponse(text="not json at all", input_tokens=10, output_tokens=5),
            AgentResponse(text='{"result": "ok"}', input_tokens=10, output_tokens=5),
        ]
        result = self.agent.call_with_json_retry(
            system_prompt="sys", user_prompt="user"
        )
        assert result == {"result": "ok"}
        assert mock_call.call_count == 2

    @patch.object(BaseAgent, "call")
    def test_raises_after_two_failures(self, mock_call):
        mock_call.side_effect = [
            AgentResponse(text="bad1", input_tokens=10, output_tokens=5),
            AgentResponse(text="bad2", input_tokens=10, output_tokens=5),
        ]
        with pytest.raises(json.JSONDecodeError):
            self.agent.call_with_json_retry(
                system_prompt="sys", user_prompt="user"
            )

from unittest.mock import MagicMock, patch

import pytest

from ouroboros.agents.base import BaseAgent, AgentResponse


class TestBaseAgent:
    def test_creation(self):
        agent = BaseAgent(model="claude-sonnet-4-6", role="observer", timeout_seconds=120)
        assert agent.model == "claude-sonnet-4-6"
        assert agent.role == "observer"
        assert agent.timeout_seconds == 120

    @patch("ouroboros.agents.base.Anthropic")
    def test_call_llm(self, mock_anthropic_cls: MagicMock):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"result": "test"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        agent = BaseAgent(model="claude-sonnet-4-6", role="test", timeout_seconds=60)
        response = agent.call(
            system_prompt="You are a test agent.",
            user_prompt="Do something.",
        )
        assert response.text == '{"result": "test"}'
        assert response.input_tokens == 100
        assert response.output_tokens == 50

        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="You are a test agent.",
            messages=[{"role": "user", "content": "Do something."}],
        )

    def test_parse_json_response(self):
        agent = BaseAgent(model="test", role="test", timeout_seconds=60)
        raw = '{"hypothesis": "test", "files": ["a.py"]}'
        parsed = agent.parse_json(raw)
        assert parsed["hypothesis"] == "test"
        assert parsed["files"] == ["a.py"]

    def test_parse_json_with_markdown_fences(self):
        agent = BaseAgent(model="test", role="test", timeout_seconds=60)
        raw = '```json\n{"key": "value"}\n```'
        parsed = agent.parse_json(raw)
        assert parsed["key"] == "value"

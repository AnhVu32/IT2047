import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.llm.llm_model import LLModel


class LLModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_compatible_uses_configured_model_and_prompts(self):
        llm = LLModel(
            provider="openai-compatible",
            model_name="local-model",
            base_url="http://localhost:11434/v1",
            api_key="test-key",
        )
        completion = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )
        )
        llm._openai_clients = [
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
        ]

        success, content, error = await llm.ask_llm("system", "user", retries=1)

        self.assertTrue(success)
        self.assertEqual(content, '{"ok": true}')
        self.assertIsNone(error)
        kwargs = completion.await_args.kwargs
        self.assertEqual(kwargs["model"], "local-model")
        self.assertEqual(kwargs["messages"][0], {"role": "system", "content": "system"})
        self.assertEqual(kwargs["messages"][1], {"role": "user", "content": "user"})

    async def test_openai_compatible_returns_error_after_retries(self):
        llm = LLModel(
            provider="openai",
            model_name="test-model",
            api_key="test-key",
        )
        completion = AsyncMock(side_effect=RuntimeError("endpoint unavailable"))
        llm._openai_clients = [
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
        ]

        success, content, error = await llm.ask_llm("system", "user", retries=2)

        self.assertFalse(success)
        self.assertIsNone(content)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(completion.await_count, 2)


if __name__ == "__main__":
    unittest.main()

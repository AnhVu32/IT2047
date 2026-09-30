import os
import unittest
from unittest.mock import AsyncMock, patch

from src.search.llm_answer import LLMSearchAnswerGenerator


class LLMSearchAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_merges_answer_and_property_insights_by_listing_id(self):
        llm = AsyncMock()
        llm.ask_llm.return_value = (
            True,
            """```json
            {"answer":"Có một căn phù hợp.","properties":[
              {"listing_id":"123","explanation":"Phù hợp ngân sách.","comparison":"Giá tốt nhất."}
            ]}
            ```""",
            None,
        )
        generator = LLMSearchAnswerGenerator(llm)
        results = [{"listing_id": 123, "explanation": "fallback"}]

        with patch.dict(os.environ, {"SEARCH_USE_LLM_ANSWER": "true"}):
            answer, generated = await generator.generate("dưới 5 tỷ", {}, results)

        self.assertTrue(generated)
        self.assertEqual(answer, "Có một căn phù hợp.")
        self.assertEqual(results[0]["explanation"], "Phù hợp ngân sách.")
        self.assertEqual(results[0]["comparison"], "Giá tốt nhất.")

    async def test_marks_llm_insight_on_merged_listing(self):
        llm = AsyncMock()
        llm.ask_llm.return_value = (
            True,
            '{"answer":"ok","properties":[{"listing_id":"123","explanation":"x","comparison":"y"}]}',
            None,
        )
        generator = LLMSearchAnswerGenerator(llm)
        results = [{"listing_id": 123, "explanation": "fallback"}]

        with patch.dict(os.environ, {"SEARCH_USE_LLM_ANSWER": "true"}):
            await generator.generate("q", {}, results)

        self.assertTrue(results[0].get("llm_insight"))

    async def test_malformed_properties_still_returns_answer(self):
        llm = AsyncMock()
        # 'properties' is a string, not a list — the answer must still survive.
        llm.ask_llm.return_value = (True, '{"answer":"Tổng quan ổn.","properties":"oops"}', None)
        generator = LLMSearchAnswerGenerator(llm)
        results = [{"listing_id": 123, "explanation": "fallback"}]

        with patch.dict(os.environ, {"SEARCH_USE_LLM_ANSWER": "true"}):
            answer, generated = await generator.generate("q", {}, results)

        self.assertTrue(generated)
        self.assertEqual(answer, "Tổng quan ổn.")
        self.assertEqual(results[0]["explanation"], "fallback")
        self.assertNotIn("llm_insight", results[0])

    async def test_requests_json_mode_and_low_temperature(self):
        llm = AsyncMock()
        llm.ask_llm.return_value = (True, '{"answer":"ok","properties":[]}', None)
        generator = LLMSearchAnswerGenerator(llm)

        with patch.dict(os.environ, {"SEARCH_USE_LLM_ANSWER": "true"}):
            await generator.generate("q", {}, [{"listing_id": 1}])

        kwargs = llm.ask_llm.await_args.kwargs
        self.assertTrue(kwargs.get("json_mode"))
        self.assertLessEqual(kwargs.get("temperature"), 0.2)

    async def test_keeps_deterministic_results_when_llm_fails(self):
        llm = AsyncMock()
        llm.ask_llm.return_value = (False, None, RuntimeError("offline"))
        generator = LLMSearchAnswerGenerator(llm)
        results = [{"listing_id": 123, "explanation": "fallback"}]

        with patch.dict(os.environ, {"SEARCH_USE_LLM_ANSWER": "true"}):
            answer, generated = await generator.generate("query", {}, results)

        self.assertFalse(generated)
        self.assertIsNone(answer)
        self.assertEqual(results[0]["explanation"], "fallback")


if __name__ == "__main__":
    unittest.main()

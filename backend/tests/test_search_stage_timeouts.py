import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from src.search.service import HybridSearchService


class SearchStageTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_llm_parser_falls_back_to_deterministic_parse(self):
        service = HybridSearchService()

        async def slow_parse(query, fallback):
            await asyncio.sleep(5)
            return fallback

        service.llm_parser.parse = slow_parse
        deterministic = service.rule_parser.parse("căn hộ quận 7 dưới 3 tỷ", top_k=3)
        with patch.dict(os.environ, {"SEARCH_PARSER_TIMEOUT_SECONDS": "0.05"}):
            parsed = await service.parse("căn hộ quận 7 dưới 3 tỷ", top_k=3)
        self.assertEqual(parsed.model_dump(), deterministic.model_dump())

    async def test_fast_llm_parser_result_is_used(self):
        service = HybridSearchService()
        sentinel = service.rule_parser.parse("nhà phố", top_k=3)
        service.llm_parser.parse = AsyncMock(return_value=sentinel)
        parsed = await service.parse("nhà phố", top_k=3)
        self.assertIs(parsed, sentinel)


if __name__ == "__main__":
    unittest.main()

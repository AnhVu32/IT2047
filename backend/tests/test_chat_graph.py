import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.services.agent.chat_graph import ChatAgentService, _fallback_route, _has_meaningful_filters


class ChatGraphRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = ChatAgentService()

    def test_greeting_never_routes_to_consultant(self):
        decision = _fallback_route("Xin chào")
        self.assertEqual(decision.mode, "chat")
        self.assertFalse(decision.context_reference)

    def test_general_real_estate_question_never_routes_to_search(self):
        decision = _fallback_route("Thủ tục sang tên sổ hồng gồm những gì?")
        self.assertEqual(decision.mode, "real_estate_qa")

    def test_ambiguous_consultation_requires_clarification(self):
        decision = _fallback_route("Tư vấn giúp tôi mua nhà")
        self.assertEqual(decision.mode, "consult")
        self.assertTrue(decision.needs_clarification)

    def test_meaningful_ui_filters_ignore_empty_default_values(self):
        self.assertFalse(_has_meaningful_filters({"min_price": 0, "district": "", "pool": False}))
        self.assertTrue(_has_meaningful_filters({"min_price": 0, "district": "Quận 7"}))

    async def test_ui_filters_satisfy_supervisor_clarification(self):
        with patch.object(
            self.service,
            "_route",
            new=AsyncMock(return_value=_fallback_route("Tư vấn giúp tôi mua nhà")),
        ):
            update = await self.service._supervisor(
                {"messages": [HumanMessage(content="Tư vấn giúp tôi mua nhà")], "filters": {"district": "Quận 7"}}
            )

        self.assertEqual(update["mode"], "consult")
        self.assertFalse(update["needs_clarification"])

    async def test_supervisor_uses_json_mode_without_tool_choice(self):
        class FakeRouter:
            structured_output_kwargs = None

            def with_structured_output(self, *_args, **kwargs):
                self.structured_output_kwargs = kwargs
                return self

            async def ainvoke(self, _messages):
                from src.services.agent.chat_graph import RouteDecision

                return RouteDecision(mode="chat")

        router = FakeRouter()
        self.service._model = lambda *_args, **_kwargs: router

        decision = await self.service._route({"messages": [HumanMessage(content="Xin chào")]})

        self.assertEqual(decision.mode, "chat")
        self.assertEqual(router.structured_output_kwargs, {"method": "json_mode"})

    def test_consultant_routes_one_native_tool_call_to_tool_node(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "search_properties", "args": {"query": "Q7"}, "id": "call-1"}],
                )
            ]
        }
        self.assertEqual(self.service._route_after_consultant(state), "tools")

    async def test_parallel_tool_calls_are_rejected_without_execution(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "search_properties", "args": {"query": "Q7"}, "id": "call-1"},
                        {"name": "inspect_previous_recommendations", "args": {"references": ["2"]}, "id": "call-2"},
                    ],
                )
            ]
        }
        self.assertEqual(self.service._route_after_consultant(state), "reject_tools")
        update = await self.service._reject_tools(state)
        self.assertIsInstance(update["messages"][0], ToolMessage)
        self.assertIn("một yêu cầu", update["assistant_answer"])

    async def test_search_tool_returns_command_with_graph_state_update(self):
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_properties",
                            "args": {"query": "căn hộ Quận 7 dưới 5 tỷ"},
                            "id": "call-search",
                        }
                    ],
                )
            ],
            "top_k": 3,
            "filters": {},
            "user_id": None,
        }
        search_result = {
            "results": [{"listing_id": 123, "title": "Căn hộ kiểm thử", "explanation": "Phù hợp."}],
            "parsed_query": {
                "intent": "property_search",
                "hard_filters": {"districts": ["Quận 7"], "property_types": ["Căn hộ"]},
            },
            "total_candidates": 1,
            "relaxations": [],
            "llm_answer_enabled": True,
            "llm_answer_generated": True,
        }
        with patch(
            "src.services.agent.chat_graph.hybrid_search_service.search",
            new=AsyncMock(return_value=search_result),
        ) as search_mock:
            command = await self.service._search_properties_impl(
                "căn hộ Quận 7 dưới 5 tỷ",
                SimpleNamespace(state=state, tool_call_id="call-search"),
            )

        update = command.update
        self.assertTrue(update["search_performed"])
        self.assertEqual(update["tool_name"], "search_properties")
        self.assertEqual(update["latest_results"][0]["listing_id"], 123)
        self.assertTrue(update["llm_answer_enabled"])
        self.assertTrue(update["llm_answer_generated"])
        self.assertTrue(search_mock.await_args.kwargs["generate_llm_answer"])
        self.assertIsInstance(update["messages"][0], ToolMessage)
        observation = update["messages"][0].content
        self.assertIn('"applied_filters":{"districts":["Quận 7"]', observation)

    async def test_greeting_runs_chat_branch_without_constructing_tools(self):
        class FakeRouter:
            def with_structured_output(self, *_args, **_kwargs):
                return self

            async def ainvoke(self, _messages):
                from src.services.agent.chat_graph import RouteDecision

                return RouteDecision(mode="chat")

        class FakeChatModel:
            async def ainvoke(self, _messages):
                return AIMessage(content="Xin chào! Tôi có thể hỗ trợ gì về nhà đất?")

        def fake_model(temperature, *, with_tools=False):
            self.assertFalse(with_tools, "greeting must never bind consultant tools")
            return FakeRouter() if temperature == 0 else FakeChatModel()

        self.service._model = fake_model
        self.service._guest_graph = self.service._build_graph(checkpointer=None)
        result = await self.service.run(
            message="Xin chào",
            history=[],
            latest_results=[],
            latest_parsed_query=None,
            filters={"district": "Quận 7"},
            top_k=3,
        )

        self.assertEqual(result["mode"], "chat")
        self.assertFalse(result["search_performed"])
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()

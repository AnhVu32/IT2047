from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict

from loguru import logger
from starlette.concurrency import run_in_threadpool

from src.search.embedding import embedding_model
from src.search.explanation import attach_explanation
from src.search.graph_repository import graph_repository
from src.search.llm_answer import LLMSearchAnswerGenerator
from src.search.query_parser import LLMQueryParser, RuleBasedQueryParser
from src.search.ranker import diversify, rank_candidates
from src.search.repository import search_repository
from src.search.schemas import ParsedSearchQuery, SearchRequest
from src.settings.event import llm_model


class HybridSearchService:
    def __init__(self):
        self.rule_parser = RuleBasedQueryParser()
        self.llm_parser = LLMQueryParser(llm_model)
        self.llm_answer = LLMSearchAnswerGenerator(llm_model)

    async def parse(self, query: str, top_k: int = 20, filters: Dict[str, Any] | None = None) -> ParsedSearchQuery:
        # Parse natural language without UI filters so the LLM can never mistake
        # their source. Only the explicit filter payload is strict.
        deterministic = self.rule_parser.parse(query, top_k=top_k)
        parsed = await self.llm_parser.parse(query, deterministic)
        # Explicit UI/API filters have the highest priority, including over an LLM
        # location correction.
        self.rule_parser.apply_explicit_filters(parsed, filters or {})
        return parsed

    async def search(
        self,
        request: SearchRequest,
        generate_llm_answer: bool = True,
        history: list[dict] | None = None,
        user_id: int | None = None,
    ) -> dict:
        started = time.perf_counter()
        parsed = await self.parse(request.query, request.top_k, request.filters)
        embedded_count, property_count = await run_in_threadpool(search_repository.embedding_coverage)
        vector = None
        if property_count > 0 and embedded_count == property_count:
            vector = await run_in_threadpool(embedding_model.encode_query, parsed.semantic_query)
        query_embedding = None if vector is None else vector.tolist()
        candidate_limit = max(500, request.top_k * request.page * 5)
        postgres_task = run_in_threadpool(search_repository.search, parsed, query_embedding, candidate_limit)
        graph_task = run_in_threadpool(graph_repository.search, parsed, candidate_limit)
        candidates, graph_response = await asyncio.gather(postgres_task, graph_task)

        graph_by_listing = {}
        for candidate in graph_response.candidates:
            current = graph_by_listing.get(candidate["listing_id"])
            if current is None or candidate["graph_score"] > current["graph_score"]:
                graph_by_listing[candidate["listing_id"]] = candidate
        if graph_by_listing:
            graph_items = await run_in_threadpool(
                search_repository.fetch_graph_candidates,
                parsed,
                list(graph_by_listing),
                query_embedding,
            )
            by_property_id = {str(item["id"]): item for item in candidates}
            for item in graph_items:
                by_property_id.setdefault(str(item["id"]), item)
            candidates = list(by_property_id.values())
        for item in candidates:
            graph_candidate = graph_by_listing.get(str(item.get("listing_id")))
            if graph_candidate:
                item["graph_score"] = graph_candidate["graph_score"]
                item["graph_evidence"] = graph_candidate["graph_evidence"]
                item["graph_matched"] = True
            else:
                # Neutral contribution avoids penalizing listings not yet represented
                # in a partially populated graph.
                item["graph_score"] = 0.5
                item["graph_evidence"] = {}
                item["graph_matched"] = False
        total_candidates = await run_in_threadpool(search_repository.count, parsed)
        if parsed.hard_filters.districts or parsed.hard_filters.former_admin_areas:
            total_candidates = max(total_candidates, len(graph_by_listing))
        # Natural-language criteria are already soft, while explicit UI filters
        # must remain strict. There is therefore no automatic constraint widening.
        relaxations: list[str] = []
        applied = parsed

        user_profile = None
        if user_id is not None:
            from src.search.personalization import build_user_profile

            user_profile = await run_in_threadpool(build_user_profile, user_id)
        ranked = rank_candidates(candidates, applied, user_profile)
        start = (request.page - 1) * request.top_k
        selected = diversify(ranked, start + request.top_k)[start:start + request.top_k]
        results = [attach_explanation(item, applied) for item in selected]
        assistant_answer, llm_answer_generated = (None, False)
        # Skip the LLM round-trip (and its retries) when disabled or no key is set,
        # so keyless deployments fall back cleanly to the deterministic explanation.
        if generate_llm_answer and self.llm_answer.enabled() and llm_model.has_credentials():
            assistant_answer, llm_answer_generated = await self.llm_answer.generate(
                request.query,
                parsed.model_dump(mode="json"),
                results,
                history=history,
            )
        # Log impressions for authenticated users only, so the anonymous /v1/search
        # path is unchanged. Best-effort: never let logging break a search response.
        if user_id is not None and results:
            await run_in_threadpool(
                self._log_impressions, request, results, user_id
            )
        response = {
            "query": request.query,
            "parsed_query": parsed.model_dump(mode="json"),
            "total_candidates": total_candidates,
            "page": request.page,
            "top_k": request.top_k,
            "results": results,
            "assistant_answer": assistant_answer,
            "llm_answer_enabled": generate_llm_answer and self.llm_answer.enabled(),
            "llm_answer_generated": llm_answer_generated,
            "relaxations": relaxations,
            "semantic_enabled": query_embedding is not None,
            "graph_enabled": graph_response.available,
            "graph_candidates": len(graph_response.candidates),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        if request.debug:
            response["debug"] = {
                "retrieved_candidates": len(candidates),
                "ranking_profile": applied.ranking_profile.value,
                "embedding_provider": embedding_model.provider,
                "embedding_model": embedding_model.model_name if query_embedding is not None else None,
                "embedding_device": embedding_model.device_name,
                "embedding_gpu": embedding_model.is_gpu,
                "embedding_coverage": {"embedded": embedded_count, "total": property_count},
                "numeric_bands": self._numeric_bands(applied),
                "graph": {
                    "available": graph_response.available,
                    "candidates": len(graph_response.candidates),
                    "latency_ms": graph_response.latency_ms,
                    "error": graph_response.error,
                },
            }
        return response

    @staticmethod
    def _numeric_bands(parsed: ParsedSearchQuery) -> dict:
        """Effective price/area filter bounds after fuzzy-target expansion (debug only)."""
        from src.search.schemas import numeric_bounds

        bands: dict = {}
        for name, rng in (("price", parsed.hard_filters.price), ("area", parsed.hard_filters.area)):
            lower, upper = numeric_bounds(rng)
            if lower is not None or upper is not None or rng.target is not None:
                bands[name] = {
                    "min": round(lower, 4) if lower is not None else None,
                    "max": round(upper, 4) if upper is not None else None,
                    "target": rng.target,
                }
        return bands

    @staticmethod
    def _log_impressions(request: SearchRequest, results: list, user_id: int) -> None:
        """Persist one recommendation_events row per shown listing (best-effort)."""
        try:
            from src.services.feedback import repository as feedback_repository

            result_set_id = uuid.uuid4().hex
            rows = []
            for rank, item in enumerate(results, start=1):
                listing_id = item.get("listing_id")
                if listing_id is None:
                    continue
                # The deterministic path always sets 'explanation', so it is not a
                # signal. 'llm_insight' is set only when the LLM actually chose this listing.
                chosen = bool(item.get("llm_insight"))
                rows.append(
                    {
                        "result_set_id": result_set_id,
                        "user_id": user_id,
                        "session_id": None,
                        "conversation_id": None,
                        "raw_query": request.query,
                        "algorithm_version": "hybrid_v1",
                        "listing_id": int(listing_id),
                        "retrieval_rank": rank,
                        "score": float(item.get("final_score") or 0.0),
                        "llm_chosen": chosen,
                        "llm_rank": rank if chosen else None,
                    }
                )
            feedback_repository.insert_recommendation_events(rows)
        except Exception as exc:  # noqa: BLE001 - impressions are non-critical
            logger.warning("Impression logging failed: {}", exc)

    async def similar(self, listing_id: str, top_k: int = 10) -> dict:
        embedded_count, property_count = await run_in_threadpool(search_repository.embedding_coverage)
        vector_available = property_count > 0 and embedded_count == property_count
        # The detail page accepts both the PostgreSQL ``properties.id`` and the
        # source ``listing_id``.  Neo4j only knows the latter, so resolve the
        # identifier once before starting the graph traversal.  Without this
        # normalization a URL such as /chi-tiet/236 would still get vector
        # recommendations, but Neo4j would search for a non-existent listing
        # node named "236" and return no shared graph evidence.
        source_property = await run_in_threadpool(search_repository.get_property, listing_id)
        graph_listing_id = str(source_property["listing_id"]) if source_property else str(listing_id)
        graph_task = run_in_threadpool(graph_repository.similar, graph_listing_id, top_k)
        if vector_available:
            vector_task = run_in_threadpool(search_repository.similar, listing_id, top_k * 2)
            vector_items, graph_response = await asyncio.gather(vector_task, graph_task)
        else:
            graph_response = await graph_task
            vector_items = []

        graph_by_listing = {item["listing_id"]: item for item in graph_response.candidates}
        vector_by_listing = {str(item["listing_id"]): item for item in vector_items}
        missing_ids = [listing for listing in graph_by_listing if listing not in vector_by_listing]
        if missing_ids:
            hydrated = await run_in_threadpool(search_repository.get_by_listing_ids, missing_ids)
            for item in hydrated:
                vector_by_listing.setdefault(str(item["listing_id"]), item)

        results = []
        for candidate_id, item in vector_by_listing.items():
            graph_candidate = graph_by_listing.get(candidate_id)
            semantic = max(0.0, min(1.0, float(item.get("semantic_score") or 0.0)))
            if graph_candidate:
                item["graph_score"] = graph_candidate["graph_score"]
                item["graph_evidence"] = graph_candidate["graph_evidence"]
                item["similarity_score"] = round(
                    .65 * semantic + .35 * graph_candidate["graph_score"]
                    if vector_available
                    else graph_candidate["graph_score"],
                    4,
                )
            else:
                item["graph_score"] = 0.0
                item["graph_evidence"] = {}
                item["similarity_score"] = round(semantic, 4)
            results.append(item)
        results.sort(key=lambda item: item["similarity_score"], reverse=True)
        results = results[:top_k]
        return {
            "listing_id": listing_id,
            "results": results,
            "total": len(results),
            "available": vector_available or graph_response.available,
            "semantic_enabled": vector_available,
            "graph_enabled": graph_response.available,
            "embedding_coverage": {"embedded": embedded_count, "total": property_count},
        }

    async def get_property(self, property_id: str):
        return await run_in_threadpool(search_repository.get_property, property_id)

    async def property_graph(self, property_id: str) -> dict | None:
        """Resolve a property through PostgreSQL, then fetch its Neo4j subgraph."""

        property_item = await run_in_threadpool(search_repository.get_property, property_id)
        if property_item is None:
            return None
        listing_id = str(property_item.get("listing_id"))
        graph = await run_in_threadpool(graph_repository.subgraph, listing_id)
        return {
            "property_id": str(property_item.get("id")),
            "listing_id": listing_id,
            "state": graph.state,
            "nodes": graph.nodes,
            "edges": graph.edges,
            "amenity_categories": graph.amenity_categories,
        }


hybrid_search_service = HybridSearchService()

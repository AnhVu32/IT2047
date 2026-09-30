from fastapi import APIRouter, HTTPException

from src.search.schemas import ParseRequest, SearchRequest, SimilarRequest
from src.search.service import hybrid_search_service


router = APIRouter()


@router.post("/parse", summary="Parse a Vietnamese real-estate query")
async def parse_search(data: ParseRequest):
    parsed = await hybrid_search_service.parse(data.query, data.top_k)
    return {"data": parsed.model_dump(mode="json"), "errors": [], "status": "success"}


@router.post("", summary="Hybrid PostgreSQL/pgvector real-estate search")
async def hybrid_search(data: SearchRequest):
    try:
        result = await hybrid_search_service.search(data)
        return {"data": result, "errors": [], "status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@router.post("/similar/{listing_id}", summary="Find semantically similar listings")
async def similar_listings(listing_id: str, data: SimilarRequest):
    try:
        result = await hybrid_search_service.similar(listing_id, data.top_k)
        return {"data": result, "errors": [], "status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Similar search failed: {exc}") from exc


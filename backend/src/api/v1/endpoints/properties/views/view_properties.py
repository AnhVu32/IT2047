from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from minio import S3Error
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from src.api.v1.endpoints.properties.controllers.controller_properties import (
    PropertiesController,
)
from src.api.v1.endpoints.properties.schemas.properties import (
    AISearchRequestModel,
)
from src.search.service import hybrid_search_service
from src.settings.event import minio_client

router = APIRouter()


@router.get("/image", summary="Read a property image from private MinIO storage")
async def view_get_property_image(path: str = Query(..., min_length=1)):
    """Stream a DB-backed property image without exposing MinIO credentials."""
    try:
        image = await run_in_threadpool(minio_client.minio_get_object, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except S3Error as exc:
        status_code = 404 if exc.code in {"NoSuchKey", "NoSuchObject"} else 502
        raise HTTPException(
            status_code=status_code,
            detail="Property image is unavailable",
        ) from exc

    content_type = image.headers.get("Content-Type", "application/octet-stream")
    if not content_type.lower().startswith("image/"):
        image.close()
        image.release_conn()
        raise HTTPException(status_code=415, detail="MinIO object is not an image")
    content_length = image.headers.get("Content-Length")
    headers = {
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"
    }
    if content_length:
        headers["Content-Length"] = content_length

    def stream_image():
        try:
            yield from image.stream(64 * 1024)
        finally:
            image.close()
            image.release_conn()

    return StreamingResponse(stream_image(), media_type=content_type, headers=headers)


@router.get("", summary="Get all properties", description="Get all properties")
async def view_get_properties(
    request: Request,
    query: str = Query(
        default=None,
        description="Search keyword in title, description or address",
    ),
    min_price: float = Query(
        default=None,
        description="Minimum price (billion VND)",
    ),
    max_price: float = Query(
        default=None,
        description="Maximum price (billion VND)",
    ),
    min_area: float = Query(
        default=None,
        description="Minimum area (square meters)",
    ),
    max_area: float = Query(
        default=None,
        description="Maximum area (square meters)",
    ),
    bedrooms: int = Query(
        default=None,
        description="Number of bedrooms",
    ),
    bathrooms: int = Query(
        default=None,
        description="Number of bathrooms",
    ),
    legal_status: str = Query(
        default=None,
        description="Legal status of property (e.g. pink book, notarized contract)",
    ),
    furniture: str = Query(
        default=None,
        description="Furniture status (e.g. fully furnished, basic, unfurnished)",
    ),
    house_direction: str = Query(
        default=None,
        description="Main house direction (e.g. North, South, East, West)",
    ),
    balcony_direction: str = Query(
        default=None,
        description="Balcony direction",
    ),
    min_frontage: float = Query(
        default=None,
        description="Minimum frontage width (meters)",
    ),
    min_road_width: float = Query(
        default=None,
        description="Minimum access road width (meters)",
    ),
    sort_by: str = Query(
        default="newest",
        description="Sort by (newest, oldest, price_asc, price_desc)",
    ),
    sort_order: str = Query(
        default="asc",
        description="Sort order (asc, desc)",
    ),
    page: int = Query(
        default=1,
        description="Page number",
    ),
    property_type: str = Query(
        default=None,
        description="Property type (e.g. apartment, house, land)",
    ),
    limit: int = Query(
        default=10,
        description="Limit",
    ),
    district: str = Query(
        default=None,
        description="District name (e.g. District 1, Binh Thanh)",
    ),
    pool: bool = Query(default=None, description="Filter by pool availability"),
    gym: bool = Query(default=None, description="Filter by gym availability"),
    park: bool = Query(default=None, description="Filter by park availability"),
    bbq: bool = Query(default=None, description="Filter by BBQ area availability"),
    kids_playground: bool = Query(default=None, description="Filter by kids playground availability"),
    sports_court: bool = Query(default=None, description="Filter by sports court availability"),
    security_24h: bool = Query(default=None, description="Filter by 24h security availability"),
    reception: bool = Query(default=None, description="Filter by reception availability"),
    elevator: bool = Query(default=None, description="Filter by elevator availability"),
    parking: bool = Query(default=None, description="Filter by parking availability"),
    near_metro: bool = Query(default=None, description="Filter by near metro"),
    near_bus: bool = Query(default=None, description="Filter by near bus"),
    near_highway: bool = Query(default=None, description="Filter by near highway"),
    near_school: bool = Query(default=None, description="Filter by near school"),
    near_hospital: bool = Query(default=None, description="Filter by near hospital"),
    near_mall: bool = Query(default=None, description="Filter by near mall"),
    near_market: bool = Query(default=None, description="Filter by near market"),
    near_park: bool = Query(default=None, description="Filter by near park"),
    river_view: bool = Query(default=None, description="Filter by river view"),
    park_view: bool = Query(default=None, description="Filter by park view"),
    city_view: bool = Query(default=None, description="Filter by city view"),
    balcony: bool = Query(default=None, description="Filter by balcony availability"),
    garden: bool = Query(default=None, description="Filter by garden availability"),
    garage: bool = Query(default=None, description="Filter by garage availability"),
    terrace: bool = Query(default=None, description="Filter by terrace availability"),
):
    return await PropertiesController(
        request=request,
    ).ctr_get_properties(
        query=query,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        legal_status=legal_status,
        furniture=furniture,
        house_direction=house_direction,
        balcony_direction=balcony_direction,
        min_frontage=min_frontage,
        min_road_width=min_road_width,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
        property_type=property_type,
        district=district,
        pool=pool,
        gym=gym,
        park=park,
        bbq=bbq,
        kids_playground=kids_playground,
        sports_court=sports_court,
        security_24h=security_24h,
        reception=reception,
        elevator=elevator,
        parking=parking,
        near_metro=near_metro,
        near_bus=near_bus,
        near_highway=near_highway,
        near_school=near_school,
        near_hospital=near_hospital,
        near_mall=near_mall,
        near_market=near_market,
        near_park=near_park,
        river_view=river_view,
        park_view=park_view,
        city_view=city_view,
        balcony=balcony,
        garden=garden,
        garage=garage,
        terrace=terrace,
    )


@router.post("/ai-search", summary="Get AI search", description="Get AI search")
async def view_get_ai_search(
    request: Request,
    data: AISearchRequestModel,
):
    return await PropertiesController(
        request=request,
    ).ctr_ai_search(
        question=data.question,
        min_price=data.min_price,
        max_price=data.max_price,
        min_area=data.min_area,
        max_area=data.max_area,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        legal_status=data.legal_status,
        furniture=data.furniture,
        house_direction=data.house_direction,
        balcony_direction=data.balcony_direction,
        length_road_entrance=data.length_road_entrance,
        district=data.district,
        pool=data.pool,
        gym=data.gym,
        park=data.park,
        bbq=data.bbq,
        kids_playground=data.kids_playground,
        sports_court=data.sports_court,
        security_24h=data.security_24h,
        reception=data.reception,
        elevator=data.elevator,
        parking=data.parking,
        near_metro=data.near_metro,
        near_bus=data.near_bus,
        near_highway=data.near_highway,
        near_school=data.near_school,
        near_hospital=data.near_hospital,
        near_mall=data.near_mall,
        near_market=data.near_market,
        near_park=data.near_park,
        river_view=data.river_view,
        park_view=data.park_view,
        city_view=data.city_view,
        balcony=data.balcony,
        garden=data.garden,
        garage=data.garage,
        terrace=data.terrace,
    )


@router.get("/{property_id}/similar", summary="Get similar properties from pgvector")
async def view_get_similar_properties(property_id: str, limit: int = Query(default=10, ge=1, le=50)):
    result = await hybrid_search_service.similar(property_id, limit)
    return {"data": result, "errors": [], "status": "success"}


@router.get("/{property_id}/graph", summary="Get the Neo4j subgraph for a property")
async def view_get_property_graph(property_id: str):
    result = await hybrid_search_service.property_graph(property_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"data": result, "errors": [], "status": "success"}


@router.get("/{property_id}", summary="Get a property by internal or listing ID")
async def view_get_property(property_id: str):
    item = await hybrid_search_service.get_property(property_id)
    if item is None:
        return {"data": None, "errors": [{"detail": "Property not found"}], "status": "failed"}
    return {"data": item, "errors": [], "status": "success"}

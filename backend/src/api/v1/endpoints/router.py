from fastapi import APIRouter

from src.api.v1.endpoints.auth import view_auth
from src.api.v1.endpoints.chat import view_chat
from src.api.v1.endpoints.feedback import view_feedback
from src.api.v1.endpoints.properties.views import view_properties
from src.api.v1.endpoints.search import view_search

router = APIRouter()

router.include_router(router=view_auth.router, prefix="/auth", tags=["Auth"])
router.include_router(router=view_chat.router, prefix="/chat", tags=["Chat"])
router.include_router(router=view_feedback.router, prefix="/feedback", tags=["Feedback"])
router.include_router(router=view_properties.router, prefix="/properties", tags=["Properties"],)
router.include_router(router=view_search.router, prefix="/search", tags=["Search"])

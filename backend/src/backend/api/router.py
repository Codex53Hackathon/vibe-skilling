from fastapi import APIRouter

from backend.api.routes.conversation import router as conversation_router
from backend.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(conversation_router, tags=["conversation"])

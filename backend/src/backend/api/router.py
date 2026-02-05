from fastapi import APIRouter

from backend.api.routes.codex import router as codex_router
from backend.api.routes.health import router as health_router
from backend.api.routes.orchestrator import router as orchestrator_router
from backend.api.routes.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(codex_router, tags=["codex"])
api_router.include_router(sessions_router, tags=["codex-sessions"])
api_router.include_router(orchestrator_router, tags=["codex-orchestrator"])
